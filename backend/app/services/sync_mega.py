"""Sincronização com o Mega (§7, P01/P04): saldo + preço médio por código de MP e cópia dos movimentos da filial 3;
verificação dos SAs aguardando confirmação (a cada 30 min).

Desenho (mapeado em 2026-11-03, ver docs/integracao_mega.md "Sincronização"):
- **Saldo e preço médio:** leitura completa a cada sincronização (≈ 8 mil códigos, 1,3 s) e troca de `mega_saldo`.
- **Movimentos:** o Mega altera lançamentos depois (≈ 3 %) e o estorno some da visão. Então cada sincronização relê
  a JANELA (movimentos dos últimos `JANELA_DIAS`, os alterados desde a última sincronização e os lançamentos novos)
  e substitui a cópia local da janela. Fora da janela, só entram alterações (upsert).
- **Agendamento:** o cron do servidor chama `python -m app.jobs.agendador` a cada 5 min; ele decide se é hora
  (horários do parâmetro SYNC_MEGA_HORARIOS, padrão 06:00 e 13:00; intervalo VERIFICACAO_SA_MIN para os SAs).
- **Concorrência:** no PostgreSQL, trava consultiva (`pg_try_advisory_xact_lock`): se já houver uma rodando, a
  segunda desiste e devolve a situação "OCUPADO" sem gravar nada.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.integrations.mega import fabrica
from app.models import CadastroSa, MegaMovimento, MegaSaldo, SyncMega

from . import entradas_mega
from . import sas as sas_srv
from .base import agora, notificar, parametro, parametro_texto

log = logging.getLogger(__name__)

FUSO = ZoneInfo("America/Sao_Paulo")
JANELA_DIAS = 120                         # movimentos relidos a cada sincronização
PRIMEIRA_CARGA_DESDE = date(2025, 1, 1)   # 1ª sincronização (tabela vazia)
TRAVA = {"ESTOQUE": 734501, "SA": 734502}


def _local(dt: datetime) -> datetime:
    """Horário no fuso de SP (o SQLite dos testes devolve datetime sem fuso, gravado em UTC)."""
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).astimezone(FUSO)


def _travar(db: Session, tipo: str) -> bool:
    if db.get_bind().dialect.name != "postgresql":
        return True
    return bool(db.execute(text("SELECT pg_try_advisory_xact_lock(:k)"), {"k": TRAVA[tipo]}).scalar())


def ultima(db: Session, tipo: str, situacao: str | None = "OK") -> SyncMega | None:
    q = select(SyncMega).where(SyncMega.tipo == tipo)
    if situacao:
        q = q.where(SyncMega.situacao == situacao)
    return db.scalar(q.order_by(SyncMega.iniciado_em.desc(), SyncMega.id.desc()).limit(1))


def _registrar_erro(db: Session, tipo: str, gatilho: str, usuario_id: int | None, inicio: datetime,
                    erro: str) -> SyncMega:
    db.rollback()
    s = SyncMega(tipo=tipo, gatilho=gatilho, usuario_id=usuario_id, iniciado_em=inicio, terminado_em=agora(),
                 situacao="ERRO", detalhes={"erro": erro[:500]})
    db.add(s)
    notificar(db, perfis=("ADMIN",), tipo="SYNC_MEGA_FALHOU",
              texto=f"Falha na sincronização com o Mega ({tipo.lower()}): {erro[:200]}", link="/mega")
    db.commit()
    return s


def sincronizar_estoque(db: Session, *, gatilho: str = "AGENDADA", usuario_id: int | None = None) -> SyncMega:
    inicio = agora()
    if not _travar(db, "ESTOQUE"):
        return SyncMega(tipo="ESTOQUE", gatilho=gatilho, situacao="OCUPADO", iniciado_em=inicio,
                        detalhes={"erro": "Já existe uma sincronização rodando."})
    try:
        g = fabrica.obter()
        saldos = g.saldos_mp()
        precos = g.precos_medios_mp()
        anterior = ultima(db, "ESTOQUE")
        hoje_ = datetime.now(FUSO).date()
        vazio = db.scalar(select(MegaMovimento.lancamento).limit(1)) is None
        desde = PRIMEIRA_CARGA_DESDE if vazio else hoje_ - timedelta(days=JANELA_DIAS)
        alterado_desde = (_local(anterior.iniciado_em).date() - timedelta(days=1)) if anterior else desde
        ultimo = (anterior.ultimo_lancamento or 0) if anterior else 0
        movs = g.movimentos_janela(desde, alterado_desde, ultimo)
    except Exception as e:  # noqa: BLE001 — Mega fora do ar: registra, avisa o Admin e segue
        log.warning("sync Mega falhou: %s", e)
        return _registrar_erro(db, "ESTOQUE", gatilho, usuario_id, inicio, f"{type(e).__name__}: {e}")

    # saldo + preço médio: troca completa (só códigos com saldo ou com preço)
    db.execute(delete(MegaSaldo))
    gravados = 0
    for s in saldos:
        pm = precos.get(s.codigo)
        if abs(s.saldo_fisico) < 0.0005 and pm is None:
            continue
        db.add(MegaSaldo(codigo=s.codigo, descricao=s.descricao, saldo_kg=round(s.saldo_fisico, 3),
                         um=s.um, peso_especifico=s.peso_especifico,
                         preco_medio=round(pm[0], 6) if pm else None, preco_medio_data=pm[1] if pm else None,
                         atualizado_em=inicio))
        gravados += 1

    # movimentos: substitui a janela e faz upsert do que veio de fora dela
    antes = db.scalar(select(text("count(*)")).select_from(MegaMovimento)) or 0
    db.execute(delete(MegaMovimento).where(MegaMovimento.data >= desde))
    db.flush()
    vistos: set[int] = set()
    for m in movs:
        if m.lancamento in vistos:
            continue
        vistos.add(m.lancamento)
        db.merge(MegaMovimento(lancamento=m.lancamento, codigo=m.codigo, data=m.data, entrada_saida=m.entrada_saida,
                               tpm=m.tpm, tpm_descricao=(m.tpm_descricao or "")[:80] or None,
                               documento=(m.documento or "")[:40] or None, kg=round(m.kg, 3),
                               codigo_destino=m.codigo_destino, estorno=m.estorno, incluido_em=m.incluido_em,
                               alterado_em=m.alterado_em.replace(tzinfo=FUSO) if m.alterado_em else None,
                               usuario_mega=m.usuario))
    db.flush()
    depois = db.scalar(select(text("count(*)")).select_from(MegaMovimento)) or 0
    maior = max([m.lancamento for m in movs], default=ultimo)
    s = SyncMega(tipo="ESTOQUE", gatilho=gatilho, usuario_id=usuario_id, iniciado_em=inicio, terminado_em=agora(),
                 situacao="OK", ultimo_lancamento=max(maior, ultimo),
                 detalhes={"codigos": gravados, "movimentos_lidos": len(vistos), "janela_desde": desde.isoformat(),
                           "alterados_desde": alterado_desde.isoformat(), "movimentos_antes": int(antes),
                           "movimentos_depois": int(depois), "primeira_carga": vazio})
    db.add(s)
    db.flush()
    s.detalhes = {**s.detalhes, "t15": entradas_mega.atualizar(db)}     # T15: pendências por código (spec v3.4)
    db.commit()
    return s


def verificar_sas(db: Session, *, gatilho: str = "AGENDADA", usuario_id: int | None = None) -> SyncMega:
    """Verificação dos SAs 'Aguardando Mega' (§7, a cada VERIFICACAO_SA_MIN)."""
    inicio = agora()
    if not _travar(db, "SA"):
        return SyncMega(tipo="SA", gatilho=gatilho, situacao="OCUPADO", iniciado_em=inicio)
    aguardando = list(db.scalars(select(CadastroSa).where(CadastroSa.situacao == "AGUARDANDO_MEGA")
                                 .with_for_update(skip_locked=True)))
    r: dict[str, Any] = sas_srv.verificar(db, aguardando)
    if r.get("erro"):
        return _registrar_erro(db, "SA", gatilho, usuario_id, inicio, r["erro"])
    s = SyncMega(tipo="SA", gatilho=gatilho, usuario_id=usuario_id, iniciado_em=inicio, terminado_em=agora(),
                 situacao="OK", detalhes=r)
    db.add(s)
    db.commit()
    return s


def horarios(db: Session) -> list[time]:
    out = []
    for h in parametro_texto(db, "SYNC_MEGA_HORARIOS", "06:00,13:00").split(","):
        try:
            hh, mm = h.strip().split(":")
            out.append(time(int(hh), int(mm)))
        except ValueError:
            continue
    return sorted(out) or [time(6), time(13)]


def ultimo_horario_previsto(db: Session, agora_local: datetime) -> datetime:
    """Último horário agendado (06:00/13:00 de hoje ou de ontem) que já passou."""
    hs = horarios(db)
    for dia in (agora_local.date(), agora_local.date() - timedelta(days=1)):
        for h in reversed(hs):
            t = datetime.combine(dia, h, tzinfo=FUSO)
            if t <= agora_local:
                return t
    return datetime.combine(agora_local.date() - timedelta(days=1), hs[0], tzinfo=FUSO)


def rodar_agendado(db: Session, agora_local: datetime | None = None) -> dict[str, str]:
    """Chamado pelo cron a cada 5 min. Roda o que estiver vencido."""
    agora_local = agora_local or datetime.now(FUSO)
    feito: dict[str, str] = {}
    try:
        fabrica.obter()
    except fabrica.MegaIndisponivel:
        from app.core.config import get_config
        if not get_config().mega_habilitado:
            return {"mega": "DESLIGADO"}       # ambiente sem Mega: não agenda nem avisa
    previsto = ultimo_horario_previsto(db, agora_local)
    ult = ultima(db, "ESTOQUE", situacao=None)
    # roda se a última tentativa (ok ou erro) é anterior ao horário previsto; erro tenta de novo em 30 min
    tentar = ult is None or _local(ult.iniciado_em) < previsto or (
        ult.situacao == "ERRO" and agora_local - _local(ult.iniciado_em) >= timedelta(minutes=30))
    if tentar:
        feito["estoque"] = sincronizar_estoque(db).situacao
    intervalo = timedelta(minutes=parametro(db, "VERIFICACAO_SA_MIN"))
    ult_sa = ultima(db, "SA", situacao=None)
    if ult_sa is None or agora_local - _local(ult_sa.iniciado_em) >= intervalo:
        tem = db.scalar(select(CadastroSa.id).where(CadastroSa.situacao == "AGUARDANDO_MEGA").limit(1))
        if tem:
            feito["sa"] = verificar_sas(db).situacao
    return feito


def para_dict(s: SyncMega) -> dict[str, Any]:
    return {"id": s.id, "tipo": s.tipo, "gatilho": s.gatilho, "situacao": s.situacao,
            "iniciado_em": s.iniciado_em.isoformat() if s.iniciado_em else None,
            "terminado_em": s.terminado_em.isoformat() if s.terminado_em else None,
            "ultimo_lancamento": s.ultimo_lancamento, "detalhes": s.detalhes}
