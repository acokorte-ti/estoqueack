"""Avisos automáticos do sino (§6), rodados pelo agendador a cada 5 min. Cada aviso sai uma vez só por documento.

- SA sem confirmação no Mega depois do prazo (PRAZO_CONFIRMACAO_SA_H, 48 h) → Estoque Itu e Admin.
- Solicitação que passou para Atrasado (> ATRASO_ATRASADO_DIAS, 15 dias) → Estoque Itu e Operação RJ.
- Reserva/restrição vencendo em AVISO_RESERVA_DIAS (7 dias) → quem criou (ou Análise).
- Resumo diário das exceções de tolerância justificadas (dia anterior) → Admin, a partir das 07h.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CadastroSa, Destinacao, Movimento, Notificacao, SolicitacaoCorte

from . import sas as svc_sas
from . import solicitacoes as svc_sol
from .base import hoje, notificar, parametro

TZ = ZoneInfo("America/Sao_Paulo")


def _ja_avisado(db: Session, tipo: str, link: str) -> bool:
    return db.scalar(select(Notificacao.id).where(Notificacao.tipo == tipo, Notificacao.link == link).limit(1)) \
        is not None


def rodar(db: Session, agora_local: datetime | None = None) -> dict[str, int]:
    agora_local = agora_local or datetime.now(TZ)
    n = {"sa_48h": 0, "atrasadas": 0, "reservas": 0, "resumo_excecoes": 0}

    horas = int(parametro(db, "PRAZO_CONFIRMACAO_SA_H"))
    for sa in db.scalars(select(CadastroSa).where(CadastroSa.situacao != "CONFIRMADO", CadastroSa.origem != "CARGA")):
        link = f"/sa?id={sa.id}"
        if svc_sas.atrasado(db, sa) and not _ja_avisado(db, "SA_SEM_CONFIRMACAO", link):
            notificar(db, perfis=("ESTOQUE", "ADMIN"), tipo="SA_SEM_CONFIRMACAO", link=link,
                      texto=f"SA da OP {sa.op} sem confirmação no Mega há mais de {horas} h"
                            + (f" (código {sa.sa_codigo})." if sa.sa_codigo else "."))
            n["sa_48h"] += 1

    for s in db.scalars(select(SolicitacaoCorte).where(SolicitacaoCorte.situacao.in_(
            ("ENVIADA", "CORTADA_PARCIAL", "MATERIAL_INSUFICIENTE")))):
        dias, faixa = svc_sol.faixa_atraso(db, s)
        link = f"/solicitacoes/{s.id}"
        if faixa == "ATRASADO" and not _ja_avisado(db, "SOLICITACAO_ATRASADA", link):
            notificar(db, perfis=("ESTOQUE", "OPERACAO_RJ"), tipo="SOLICITACAO_ATRASADA", link=link,
                      texto=f"Solicitação da OP {s.op} passou para Atrasado ({dias} dias em aberto).")
            n["atrasadas"] += 1

    dias_res = int(parametro(db, "AVISO_RESERVA_DIAS"))
    for d in db.scalars(select(Destinacao).where(Destinacao.ativa.is_(True), Destinacao.validade.is_not(None),
                                                 Destinacao.validade >= hoje(),
                                                 Destinacao.validade <= hoje() + timedelta(days=dias_res))):
        link = f"/lotes/{d.lote_id}?destinacao={d.id}"
        if not _ja_avisado(db, "RESERVA_VENCENDO", link):
            tipo = "Reserva" if d.tipo == "RESERVA" else "Restrição"
            texto = f"{tipo} \"{d.descricao[:120]}\" vence em {d.validade.strftime('%d/%m/%Y')}."
            if d.criado_por_id:
                notificar(db, usuarios=(d.criado_por_id,), tipo="RESERVA_VENCENDO", link=link, texto=texto)
            else:
                notificar(db, perfis=("ANALISE",), tipo="RESERVA_VENCENDO", link=link, texto=texto)
            n["reservas"] += 1

    if agora_local.hour >= 7:
        ontem = (agora_local - timedelta(days=1)).date()
        link = f"/relatorios/excecoes?dia={ontem.isoformat()}"
        if not _ja_avisado(db, "RESUMO_EXCECOES", link):
            ini = datetime(ontem.year, ontem.month, ontem.day, tzinfo=TZ).astimezone(timezone.utc)
            fim = ini + timedelta(days=1)
            qtd = sum(1 for m in db.scalars(select(Movimento).where(Movimento.criado_em >= ini,
                                                                    Movimento.criado_em < fim,
                                                                    Movimento.origem_ref.is_(None)))  # fora a carga
                      if m.confirmacoes or m.tipo in ("AJUSTE_INVENTARIO", "ESTORNO"))
            if qtd:
                notificar(db, perfis=("ADMIN",), tipo="RESUMO_EXCECOES", link=link,
                          texto=f"{qtd} exceção(ões) de tolerância, ajuste ou estorno em "
                                f"{ontem.strftime('%d/%m/%Y')}.")
                n["resumo_excecoes"] = qtd
    db.commit()
    return n
