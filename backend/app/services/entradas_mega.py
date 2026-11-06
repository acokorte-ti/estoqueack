"""T15 Entradas Mega a classificar (versão mínima, F1; spec v3.4 §T15).

Quando uma NF de MP entra no Mega em Itu, o saldo do código sobe e o sistema ainda não tem o lote. Para cada
código: `diferença = saldo Mega − soma dos lotes ITU/ITU − diferenças já explicadas ("Não é entrada")`. Acima de
`DIVERGENCIA_MEGA_KG` existe UMA pendência ABERTA por código, criada/atualizada na sincronização
(`atualizar`, chamada ao fim de `sync_mega.sincronizar_estoque`) e depois de cada ação.

Estados: ABERTA → RESOLVIDA (lote criado e diferença dentro da tolerância) | DESCARTADA ("Não é entrada": os kg
ficam como diferença explicada e saem do cálculo) | ENCERRADA (a diferença voltou para dentro da tolerância sem
ação, p. ex. o Mega estornou a NF). Só o Admin reabre uma DESCARTADA.

Escolhas da especificação marcadas como proposta (P25) ou que o código precisou decidir:
- Código que o Mega tem e o catálogo não tem ("Código novo") só gera pendência se teve ENTRADA (ED, sem estorno)
  nos movimentos copiados (janela de 120 dias). Sem isso, os ~8 mil códigos do Mega que a carga deixou fora
  (sem movimento em 2 anos, §10.7) apareceriam todos como pendência logo depois da carga.
- Liga lida da descrição que não existe na tabela de ligas bloqueia como "não consegui ler" (não cria liga:
  a densidade é decisão do Admin no T22).
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.formato import kg_br
from app.domain.validacao import Nivel
from app.models import (Conteiner, ItemMP, Liga, Lote, MegaMovimento, MegaSaldo, PendenciaMega, Usuario)

from . import auditoria
from . import movimentos as mov
from .base import (ErroNegocio, NaoEncontrado, Previa, agora, exigir_sem_pendencias, hoje, parametro)

MOTIVOS = {
    "ESTORNO_BAIXA_MEGA": "Estorno de baixa no Mega",
    "ACERTO_INVENTARIO_MEGA": "Acerto de inventário no Mega",
    "TRANSFERENCIA_CODIGOS": "Transferência entre códigos",
    "OUTRO": "Outro",
}
JANELA_CODIGO_NOVO_DIAS = 120
TOLERANCIA_EXTRA_PESO_KG = None            # o teto do lote é "diferença + DIVERGENCIA_MEGA_KG" (spec)
MSG_ILEGIVEL = ("Não consegui ler liga e bitola desta descrição. Peça ao Admin para cadastrar o item no "
                "Catálogo (T22).")
RE_CONTEINER = re.compile(r"^[A-Z]{1,4}\d{1,4}[A-Z0-9]{0,4}$")      # CH11EA, CH33K, CH40SH…


# ---------------- cálculo ----------------

def _local(dt: datetime | None) -> datetime | None:
    return dt


def _explicadas(db: Session) -> dict[int, float]:
    q = (select(PendenciaMega.codigo, func.coalesce(func.sum(PendenciaMega.kg), 0))
         .where(PendenciaMega.tipo == "ENTRADA", PendenciaMega.situacao == "DESCARTADA")
         .group_by(PendenciaMega.codigo))
    return {c: round(float(k), 3) for c, k in db.execute(q)}


def _soma_lotes(db: Session) -> dict[int, float]:
    q = (select(ItemMP.codigo_mega, func.coalesce(func.sum(Lote.saldo_kg), 0)).join(Lote, Lote.item_mp_id == ItemMP.id)
         .where(Lote.planta_fiscal == "ITU", Lote.local_fisico == "ITU", ItemMP.codigo_mega.is_not(None))
         .group_by(ItemMP.codigo_mega))
    return {c: round(float(k), 3) for c, k in db.execute(q)}


def _com_entrada_recente(db: Session) -> set[int]:
    desde = hoje() - timedelta(days=JANELA_CODIGO_NOVO_DIAS)
    return set(db.scalars(select(MegaMovimento.codigo).where(
        MegaMovimento.entrada_saida == "ED", MegaMovimento.estorno.is_(False), MegaMovimento.data >= desde).distinct()))


def diferencas(db: Session, codigo: int | None = None) -> dict[int, dict[str, Any]]:
    """{codigo: {mega, lotes, explicada, diferenca, no_catalogo}} só dos códigos que podem ter entrada a classificar."""
    catalogo = {c for (c,) in db.execute(select(ItemMP.codigo_mega).where(ItemMP.codigo_mega.is_not(None)))}
    q = select(MegaSaldo)
    if codigo is not None:
        q = q.where(MegaSaldo.codigo == codigo)
    mega = {m.codigo: m for m in db.scalars(q)}
    lotes, expl = _soma_lotes(db), _explicadas(db)
    novos = {c for c in mega if c not in catalogo}
    recentes = _com_entrada_recente(db) if novos else set()
    out: dict[int, dict[str, Any]] = {}
    for cod, m in mega.items():
        if cod in novos and cod not in recentes:
            continue
        sm, sl, ex = round(float(m.saldo_kg), 3), lotes.get(cod, 0.0), expl.get(cod, 0.0)
        out[cod] = {"mega": sm, "lotes": sl, "explicada": ex, "diferenca": round(sm - sl - ex, 3),
                    "no_catalogo": cod in catalogo, "descricao": m.descricao}
    return out


def _estado_pos_calculo(p: PendenciaMega, d: dict[str, Any] | None, limite: float) -> None:
    """Atualiza uma pendência ABERTA com o cálculo atual (fecha se voltou à tolerância)."""
    if d is not None and d["diferenca"] > limite:
        p.kg, p.saldo_mega_kg, p.soma_lotes_kg, p.atualizado_em = d["diferenca"], d["mega"], d["lotes"], agora()
        return
    p.situacao = "RESOLVIDA" if p.lote_id else "ENCERRADA"
    p.resolvido_em = p.resolvido_em or agora()
    p.atualizado_em = agora()
    if d is not None:
        p.saldo_mega_kg, p.soma_lotes_kg = d["mega"], d["lotes"]


def atualizar(db: Session, codigo: int | None = None) -> dict[str, int]:
    """Cria/atualiza/fecha as pendências ABERTAS. Não faz commit."""
    limite = parametro(db, "DIVERGENCIA_MEGA_KG")
    calc = diferencas(db, codigo)
    q = select(PendenciaMega).where(PendenciaMega.tipo == "ENTRADA", PendenciaMega.situacao == "ABERTA")
    if codigo is not None:
        q = q.where(PendenciaMega.codigo == codigo)
    abertas = {p.codigo: p for p in db.scalars(q)}
    c = {"criadas": 0, "atualizadas": 0, "fechadas": 0}
    for cod, p in abertas.items():
        _estado_pos_calculo(p, calc.get(cod), limite)
        c["atualizadas" if p.situacao == "ABERTA" else "fechadas"] += 1
    for cod, d in calc.items():
        if cod not in abertas and d["diferenca"] > limite:
            db.add(PendenciaMega(tipo="ENTRADA", codigo=cod, kg=d["diferenca"], situacao="ABERTA",
                                 saldo_mega_kg=d["mega"], soma_lotes_kg=d["lotes"], atualizado_em=agora()))
            c["criadas"] += 1
    db.flush()
    return c


def contador(db: Session) -> int:
    return int(db.scalar(select(func.count(PendenciaMega.id)).where(
        PendenciaMega.tipo == "ENTRADA", PendenciaMega.situacao == "ABERTA")) or 0)


# ---------------- leitura da descrição (mesma regra da carga) ----------------

def interpretar_item(db: Session, descricao: str) -> dict[str, Any]:
    from app.carga.plano import ALIAS_LIGA, LIGAS_POR_TEXTO, medida   # import tardio: a carga lê planilhas
    m = medida(descricao or "")
    up = (descricao or "").upper()
    cod = next((lg for txt, lg in LIGAS_POR_TEXTO if txt in up), None) or ALIAS_LIGA.get(m.liga, m.liga)
    liga = db.scalar(select(Liga).where(Liga.codigo == cod)) if cod else None
    legivel = (liga is not None and (m.formato == "RETO" or (m.formato == "RETANGULAR" and m.espessura and m.largura)
                                     or (m.formato == "REDONDO" and m.diametro)))
    bit = "RETO" if m.formato == "RETO" else m.bitola
    return {"legivel": bool(legivel), "liga": liga.codigo if liga else cod, "formato": m.formato, "bitola": bit,
            "espessura": m.espessura, "largura": m.largura, "diametro": m.diametro,
            "liga_id": liga.id if liga else None,
            "mensagem": None if legivel else MSG_ILEGIVEL}


def _item_do_codigo(db: Session, codigo: int) -> ItemMP | None:
    return db.scalar(select(ItemMP).where(ItemMP.codigo_mega == codigo))


# ---------------- listagem ----------------

def _ultima_entrada(db: Session, codigo: int) -> dict[str, Any] | None:
    m = db.scalar(select(MegaMovimento).where(
        MegaMovimento.codigo == codigo, MegaMovimento.entrada_saida == "ED",
        MegaMovimento.estorno.is_(False)).order_by(MegaMovimento.data.desc(), MegaMovimento.lancamento.desc()).limit(1))
    if m is None:
        return None
    return {"nf": m.documento, "data": m.data.isoformat(), "kg": round(float(m.kg), 3), "tpm": m.tpm_descricao}


def _nome(db: Session, uid: int | None) -> str | None:
    u = db.get(Usuario, uid) if uid else None
    return u.nome if u else None


def pendencia_dict(db: Session, p: PendenciaMega, *, item: ItemMP | None = None, descricao: str | None = None,
                   lotes_codigo: bool = True) -> dict[str, Any]:
    item = item if item is not None else _item_do_codigo(db, p.codigo)
    mega = db.get(MegaSaldo, p.codigo)
    descricao = descricao or (mega.descricao if mega else None) or (item.descricao if item else None)
    d: dict[str, Any] = {
        "id": p.id, "codigo": p.codigo, "descricao": descricao, "situacao": p.situacao,
        "saldo_mega_kg": p.saldo_mega_kg, "soma_lotes_kg": p.soma_lotes_kg, "diferenca_kg": round(float(p.kg), 3),
        "criado_em": p.criado_em.isoformat() if p.criado_em else None,
        "atualizado_em": p.atualizado_em.isoformat() if p.atualizado_em else None,
        "ultima_entrada": _ultima_entrada(db, p.codigo),
        "etiquetas": [], "motivo": p.motivo, "motivo_descricao": MOTIVOS.get(p.motivo or ""),
        "justificativa": p.justificativa,
        "tratada_por": _nome(db, p.resolvido_por_id),
        "tratada_em": p.resolvido_em.isoformat() if p.resolvido_em else None,
        "item": None, "item_sugerido": None,
    }
    if item is None:
        d["etiquetas"].append("CODIGO_NOVO")
        d["item_sugerido"] = {k: v for k, v in interpretar_item(db, descricao or "").items() if k != "liga_id"}
    else:
        d["item"] = {"id": item.id, "liga": item.liga.codigo, "formato": item.formato,
                     "bitola": "RETO" if item.formato == "RETO" else _bitola(item),
                     "criado_pela_t15": item.criado_pela_t15}
        if item.formato == "RETO":
            d["etiquetas"].append("CODIGO_RETO")
            d["aviso"] = "Código RETO: confira se a T13 deste corte já foi lançada antes de criar o lote."
    return d


def _bitola(item: ItemMP) -> str:
    from .estoque import bitola
    return bitola(item)


def listar(db: Session, *, situacao: str = "ABERTA", busca: str | None = None) -> dict[str, Any]:
    from . import sync_mega
    q = select(PendenciaMega).where(PendenciaMega.tipo == "ENTRADA")
    if situacao != "TODAS":
        q = q.where(PendenciaMega.situacao == situacao)
    itens = []
    b = (busca or "").strip().lower()
    for p in db.scalars(q.order_by(PendenciaMega.criado_em, PendenciaMega.id)):
        d = pendencia_dict(db, p)
        if b and b not in str(p.codigo) and b not in (d["descricao"] or "").lower():
            continue
        itens.append(d)
    u, ult = sync_mega.ultima(db, "ESTOQUE"), sync_mega.ultima(db, "ESTOQUE", None)
    mega_fora = ult is not None and ult.situacao == "ERRO"
    return {"itens": itens, "total": len(itens), "limite_kg": parametro(db, "DIVERGENCIA_MEGA_KG"),
            "abertas": contador(db), "mega_indisponivel": mega_fora,
            "aviso": (f"Mega indisponível. Os dados desta lista são da última sincronização "
                      f"({u.terminado_em.isoformat() if u and u.terminado_em else 'nenhuma'})." if mega_fora else None),
            "ultima_sincronizacao": u.terminado_em.isoformat() if u and u.terminado_em else None}


# ---------------- ações ----------------

def _pendencia(db: Session, pid: int, *, travar: bool = False) -> PendenciaMega:
    q = select(PendenciaMega).where(PendenciaMega.id == pid, PendenciaMega.tipo == "ENTRADA")
    if travar:
        q = q.with_for_update().execution_options(populate_existing=True)
    p = db.scalar(q)
    if p is None:
        raise NaoEncontrado("Pendência não encontrada.")
    return p


def _exigir_aberta(db: Session, p: PendenciaMega) -> None:
    if p.situacao != "ABERTA":
        quem = _nome(db, p.resolvido_por_id) or "o sistema"
        hora = p.resolvido_em.astimezone().strftime("%H:%M") if p.resolvido_em else "—"
        raise ErroNegocio(f"Esta pendência já foi tratada por {quem} às {hora}. Atualize a lista.")


def _justificativa(texto: str | None) -> str:
    t = (texto or "").strip()
    if len(t) < 10:
        raise ErroNegocio("Escreva pelo menos 10 caracteres.")
    return t


class LoteDados:
    """Dados de 'Criar lote'. Classe simples (a API converte do corpo pydantic)."""

    def __init__(self, peso_kg: float, conteiner: str | None = None, sem_conteiner: bool = False,
                 pecas: int | None = None, data_entrada: date | None = None, nf: str | None = None,
                 observacao: str | None = None, confirmacoes: dict[str, str] | None = None):
        self.peso_kg, self.conteiner, self.sem_conteiner, self.pecas = peso_kg, conteiner, sem_conteiner, pecas
        self.data_entrada, self.nf, self.observacao, self.confirmacoes = data_entrada, nf, observacao, confirmacoes


def _atual(db: Session, p: PendenciaMega) -> dict[str, Any]:
    d = diferencas(db, p.codigo).get(p.codigo)
    return d or {"mega": float(p.saldo_mega_kg or 0), "lotes": float(p.soma_lotes_kg or 0), "explicada": 0.0,
                 "diferenca": float(p.kg), "no_catalogo": True, "descricao": None}


def _valores_padrao(db: Session, p: PendenciaMega, dif: float) -> dict[str, Any]:
    ult = _ultima_entrada(db, p.codigo)
    return {"peso_sugerido_kg": max(dif, 0.0), "nf": ult["nf"] if ult else None,
            "data_entrada": ult["data"] if ult else None}


def validar_criar_lote(db: Session, pid: int, e: LoteDados) -> Previa:
    p = _pendencia(db, pid)
    pv = Previa()
    r = pv.resultado
    if p.situacao != "ABERTA":
        r.adicionar("PENDENCIA_TRATADA", Nivel.ERRO, "Esta pendência já foi tratada. Atualize a lista.")
        return pv
    cur = _atual(db, p)
    limite = parametro(db, "DIVERGENCIA_MEGA_KG")
    item = _item_do_codigo(db, p.codigo)
    if item is None:
        s = interpretar_item(db, cur.get("descricao") or "")
        if not s["legivel"]:
            r.adicionar("ITEM_ILEGIVEL", Nivel.ERRO, MSG_ILEGIVEL)
        else:
            pv.extra["item_novo"] = {k: s[k] for k in ("liga", "formato", "bitola")}
    if e.peso_kg is None or e.peso_kg <= 0:
        r.adicionar("PESO_INVALIDO", Nivel.ERRO, "O peso do lote deve ser maior que 0.")
    elif e.peso_kg > cur["diferenca"] + limite + 1e-9:
        r.adicionar("PESO_ACIMA_DA_DIFERENCA", Nivel.ERRO,
                    f"O lote não pode ter mais kg do que o Mega tem a mais ({kg_br(max(cur['diferenca'], 0))}). "
                    "Informe um peso menor ou confira a diferença.", maximo_kg=round(cur["diferenca"] + limite, 3))
    cont = (e.conteiner or "").strip().upper()
    if not cont and not e.sem_conteiner:
        r.adicionar("CONTEINER_OBRIGATORIO", Nivel.ERRO, 'Informe o contêiner ou marque "sem contêiner".')
    elif cont and e.sem_conteiner:
        r.adicionar("CONTEINER_E_SEM_CONTEINER", Nivel.ERRO,
                    'Informe o contêiner ou marque "sem contêiner", não os dois.')
    elif cont:
        if not RE_CONTEINER.match(cont):
            r.adicionar("CONTEINER_FORMATO", Nivel.ERRO,
                        f'O contêiner "{cont}" não parece um código válido (ex.: CH11EA).')
        elif item is not None:
            dup = db.scalar(select(Lote).join(Conteiner, Lote.conteiner_id == Conteiner.id).where(
                Conteiner.codigo == cont, Lote.item_mp_id == item.id, Lote.status == "ATIVO").limit(1))
            if dup is not None:
                r.adicionar("CONTEINER_REPETIDO", Nivel.CIENCIA,
                            f"Já existe o lote {dup.codigo} com este contêiner e este material. "
                            "Confirma que é outra entrada?", lote=dup.codigo)
    if e.data_entrada and e.data_entrada > hoje():
        r.adicionar("DATA_FUTURA", Nivel.ERRO, "A data de entrada não pode ser futura.")
    depois = round(cur["diferenca"] - (e.peso_kg or 0), 3)
    pv.frase = (f"Cria 1 lote ITU/ITU de {kg_br(e.peso_kg or 0)} (código {p.codigo}). "
                f"Diferença restante: {kg_br(max(depois, 0))}.")
    pv.extra.update({"diferenca_kg": cur["diferenca"], "diferenca_restante_kg": depois,
                     **_valores_padrao(db, p, cur["diferenca"])})
    return pv


def criar_lote(db: Session, pid: int, e: LoteDados, *, usuario: Usuario, ip: str | None) -> dict[str, Any]:
    p = _pendencia(db, pid, travar=True)
    _exigir_aberta(db, p)
    conf = exigir_sem_pendencias(validar_criar_lote(db, pid, e), e.confirmacoes)
    item = _item_do_codigo(db, p.codigo)
    if item is None:
        cur = _atual(db, p)
        s = interpretar_item(db, cur.get("descricao") or "")
        item = ItemMP(codigo_mega=p.codigo, descricao=(cur.get("descricao") or f"Código {p.codigo}")[:200],
                      liga_id=s["liga_id"], formato=s["formato"], espessura=s["espessura"], largura=s["largura"],
                      diametro=s["diametro"], criado_pela_t15=True)
        db.add(item)
        db.flush()
    cont = (e.conteiner or "").strip().upper()
    ct_id = None
    ult = _ultima_entrada(db, p.codigo)
    data = e.data_entrada or (date.fromisoformat(ult["data"]) if ult else hoje())
    nf = (e.nf or "").strip() or (ult["nf"] if ult else None)
    if cont:
        ct = db.scalar(select(Conteiner).where(Conteiner.codigo == cont))
        if ct is None:
            ct = Conteiner(codigo=cont, data_entrada=data)
            db.add(ct)
            db.flush()
        ct_id = ct.id
    lote = mov.criar_lote(db, item=item, planta_fiscal="ITU", local_fisico="ITU",
                          tipo="RETO" if item.formato == "RETO" else "ORIGINAL", conteiner_id=ct_id,
                          peso_inicial_kg=e.peso_kg, pecas=e.pecas, documento=nf, origem_identificada=bool(cont),
                          usuario_id=usuario.id, origem_ref={"origem": "T15", "pendencia_id": p.id})
    mov.lancar(db, lote, "ENTRADA", e.peso_kg, usuario_id=usuario.id, pecas=e.pecas, documento=nf,
               data_referencia=data, justificativa=(f"Entrada Mega classificada na T15 (pendência {p.id})"
                                                    + (f". {e.observacao.strip()}" if e.observacao else ""))[:500],
               confirmacoes=conf or None)
    if e.observacao and e.observacao.strip():
        from app.models import Nota
        db.add(Nota(entidade="LOTE", entidade_id=lote.id, texto=e.observacao.strip()[:2000], usuario_id=usuario.id))
    p.lote_id, p.resolvido_por_id = lote.id, usuario.id
    db.flush()
    atualizar(db, p.codigo)                          # recalcula (resolve se ficou dentro da tolerância)
    if p.situacao != "ABERTA":
        p.resolvido_por_id, p.resolvido_em = usuario.id, agora()
    dif = max(round(_atual(db, p)["diferenca"], 3), 0.0)
    auditoria.registrar(db, "T15_LOTE_CRIADO", usuario_id=usuario.id, entidade="pendencia_mega", entidade_id=p.id,
                        depois={"codigo": p.codigo, "lote": lote.codigo, "kg": e.peso_kg, "conteiner": cont or None,
                                "nf": nf, "diferenca_restante_kg": dif}, ip=ip)
    db.commit()
    return {"lote": {"id": lote.id, "codigo": lote.codigo, "peso_kg": round(e.peso_kg, 3)},
            "pendencia": pendencia_dict(db, p), "diferenca_restante_kg": dif,
            "mensagem": f"Lote {lote.codigo} criado com {kg_br(e.peso_kg)} (código {p.codigo}). "
                        f"Diferença restante: {kg_br(dif)}."}


def nao_e_entrada(db: Session, pid: int, motivo: str, justificativa: str, *, usuario: Usuario,
                  ip: str | None) -> dict[str, Any]:
    if motivo not in MOTIVOS:
        raise ErroNegocio("Motivo inválido. Use: " + ", ".join(MOTIVOS) + ".")
    just = _justificativa(justificativa)
    p = _pendencia(db, pid, travar=True)
    _exigir_aberta(db, p)
    cur = _atual(db, p)
    kg = round(max(cur["diferenca"], 0.0), 3)
    p.situacao, p.motivo, p.justificativa, p.kg = "DESCARTADA", motivo, just, kg
    p.resolvido_por_id, p.resolvido_em, p.atualizado_em = usuario.id, agora(), agora()
    auditoria.registrar(db, "T15_NAO_E_ENTRADA", usuario_id=usuario.id, entidade="pendencia_mega", entidade_id=p.id,
                        depois={"codigo": p.codigo, "kg": kg, "motivo": motivo, "justificativa": just}, ip=ip)
    db.commit()
    return pendencia_dict(db, p)


def reabrir(db: Session, pid: int, justificativa: str, *, usuario: Usuario, ip: str | None) -> dict[str, Any]:
    just = _justificativa(justificativa)
    p = _pendencia(db, pid, travar=True)
    if p.situacao != "DESCARTADA":
        raise ErroNegocio('Só uma pendência "Não é entrada" (Descartada) pode ser reaberta.')
    antes = {"situacao": p.situacao, "motivo": p.motivo, "kg": float(p.kg)}
    p.situacao, p.resolvido_em, p.resolvido_por_id = "ABERTA", None, None
    p.justificativa = f"Reaberta: {just}"[:500]
    db.flush()
    atualizar(db, p.codigo)                          # a diferença explicada volta ao cálculo
    auditoria.registrar(db, "T15_REABERTA", usuario_id=usuario.id, entidade="pendencia_mega", entidade_id=p.id,
                        antes=antes, depois={"justificativa": just, "situacao": p.situacao}, ip=ip)
    db.commit()
    return pendencia_dict(db, p)


# ---------------- apoio à T16 ----------------

def explicacoes_por_codigo(db: Session) -> dict[int, list[dict[str, Any]]]:
    out: dict[int, list[dict[str, Any]]] = {}
    for p in db.scalars(select(PendenciaMega).where(PendenciaMega.tipo == "ENTRADA",
                                                    PendenciaMega.situacao == "DESCARTADA")
                        .order_by(PendenciaMega.id)):
        out.setdefault(p.codigo, []).append({
            "pendencia_id": p.id, "kg": round(float(p.kg), 3), "motivo": p.motivo,
            "motivo_descricao": MOTIVOS.get(p.motivo or ""), "justificativa": p.justificativa,
            "usuario": _nome(db, p.resolvido_por_id),
            "em": p.resolvido_em.isoformat() if p.resolvido_em else None})
    return out
