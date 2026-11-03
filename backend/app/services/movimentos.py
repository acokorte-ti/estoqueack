"""Lançamento de movimentos (imutáveis), criação de lotes e reservas.

Regra única de saldo: `lote.saldo_kg` é a soma dos movimentos do lote e nunca fica negativo. Todo serviço que
mexe em estoque passa por `lancar`, que atualiza o saldo e a situação (Ativo/Esgotado) junto com o movimento.
"""
from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.domain.formato import kg_br
from app.models import Destinacao, ItemMP, LiberacaoCorte, Liga, Lote, Movimento, SolicitacaoCorte

from .base import ErroNegocio, NaoEncontrado

EPS = 1e-6
SITUACOES_COM_RESERVA = ("ENVIADA", "CORTADA_PARCIAL")


def lote_ou_404(db: Session, lote_id: int, *, travar: bool = False) -> Lote:
    q = select(Lote).where(Lote.id == lote_id)
    if travar:
        # populate_existing: se o lote já estava na sessão (lido sem trava na validação), recarrega o saldo
        # DEPOIS de obter a trava; sem isso, o 2º corte simultâneo usa o saldo velho (Parte B, 2026-11-03)
        q = q.with_for_update().execution_options(populate_existing=True)
    lote = db.scalar(q)
    if lote is None:
        raise NaoEncontrado("Lote não encontrado.")
    return lote


def lancar(db: Session, lote: Lote, tipo: str, kg: float, *, usuario_id: int | None, **campos) -> Movimento:
    """Grava o movimento e atualiza o saldo do lote. kg > 0 entra, kg < 0 sai."""
    kg = round(float(kg), 3)
    if abs(kg) < EPS:
        raise ErroNegocio("Movimento com 0 kg não é permitido.")
    novo = round(float(lote.saldo_kg) + kg, 3)
    if novo < -EPS:
        raise ErroNegocio(f"O lote {lote.codigo} ficaria com saldo negativo ({kg_br(novo)}).")
    m = Movimento(lote_id=lote.id, tipo=tipo, kg=kg, usuario_id=usuario_id, **campos)
    db.add(m)
    lote.saldo_kg = max(novo, 0.0)
    lote.status = "ESGOTADO" if lote.saldo_kg <= EPS else "ATIVO"
    db.flush()
    return m


def criar_lote(db: Session, *, item: ItemMP, planta_fiscal: str, local_fisico: str, tipo: str = "ORIGINAL",
               pai: Lote | None = None, conteiner_id: int | None = None, peso_inicial_kg: float,
               pecas: int | None = None, documento: str | None = None, custo_kg: float | None = None,
               origem_identificada: bool = True, usuario_id: int | None = None, origem_ref: dict | None = None) -> Lote:
    """Cria o lote com saldo 0; o saldo entra pelo movimento que o originou (ENTRADA, GERA_RETO, RECEBIMENTO_ITU…)."""
    lote = Lote(codigo=f"TMP-{uuid.uuid4().hex[:14]}", item_mp_id=item.id, planta_fiscal=planta_fiscal,
                local_fisico=local_fisico, tipo=tipo, lote_pai_id=pai.id if pai else None,
                conteiner_id=conteiner_id if conteiner_id is not None else (pai.conteiner_id if pai else None),
                origem_identificada=origem_identificada if pai is None else pai.origem_identificada,
                peso_inicial_kg=round(peso_inicial_kg, 3), pecas_iniciais=pecas, saldo_kg=0.0, custo_kg=custo_kg,
                documento_entrada=documento, status="ATIVO", criado_por_id=usuario_id, origem_ref=origem_ref)
    db.add(lote)
    db.flush()
    lote.codigo = f"L-{lote.id:06d}"
    db.flush()
    return lote


def item_reto(db: Session, liga_id: int) -> ItemMP:
    """Item RETO da liga (prefere o que tem código Mega, ex.: 1698 H13 RETO). Cria um item só-RJ se não existir."""
    item = db.scalar(select(ItemMP).where(ItemMP.liga_id == liga_id, ItemMP.formato == "RETO", ItemMP.ativo.is_(True))
                     .order_by(ItemMP.codigo_mega.is_(None), ItemMP.id))
    if item is None:
        liga = db.get(Liga, liga_id)
        item = ItemMP(descricao=f"{liga.codigo} RETO", liga_id=liga_id, formato="RETO")
        db.add(item)
        db.flush()
    return item


# ---------------- Reservas ----------------

def pecas_cortadas(sol: SolicitacaoCorte) -> int:
    return sum(l.pecas for l in sol.liberacoes if not l.estornada)


def reserva_da_solicitacao(sol: SolicitacaoCorte) -> float:
    """Reserva = peso previsto do que ainda falta cortar, enquanto a solicitação está Enviada ou Parcial."""
    if sol.situacao not in SITUACOES_COM_RESERVA or sol.encerrada_saldo_pendente:
        return 0.0
    falta = max(sol.quantidade - pecas_cortadas(sol), 0)
    return round(float(sol.peso_previsto_kg) * falta / sol.quantidade, 3)


def reservas_solicitacoes(db: Session, lote_ids: list[int], *,
                          exceto_solicitacao: int | None = None) -> dict[int, float]:
    if not lote_ids:
        return {}
    q = select(SolicitacaoCorte).where(SolicitacaoCorte.lote_id.in_(lote_ids),
                                       SolicitacaoCorte.situacao.in_(SITUACOES_COM_RESERVA))
    if exceto_solicitacao is not None:
        q = q.where(SolicitacaoCorte.id != exceto_solicitacao)
    total: dict[int, float] = defaultdict(float)
    for s in db.scalars(q):
        total[s.lote_id] += reserva_da_solicitacao(s)
    return {k: round(v, 3) for k, v in total.items()}


def reservas_destinacoes(db: Session, lote_ids: list[int]) -> dict[int, float]:
    if not lote_ids:
        return {}
    q = (select(Destinacao.lote_id, func.coalesce(func.sum(Destinacao.kg), 0))
         .where(Destinacao.lote_id.in_(lote_ids), Destinacao.ativa.is_(True), Destinacao.tipo == "RESERVA",
                or_(Destinacao.validade.is_(None), Destinacao.validade >= date.today()))
         .group_by(Destinacao.lote_id))
    return {i: float(k) for i, k in db.execute(q)}


def reservado(db: Session, lote_ids: list[int], *, exceto_solicitacao: int | None = None) -> dict[int, float]:
    """Kg reservados por lote: solicitações enviadas/parciais + reservas (T17) com kg."""
    a = reservas_solicitacoes(db, lote_ids, exceto_solicitacao=exceto_solicitacao)
    b = reservas_destinacoes(db, lote_ids)
    return {i: round(a.get(i, 0.0) + b.get(i, 0.0), 3) for i in set(a) | set(b)}


def destinacoes_vigentes(db: Session, lote_id: int) -> list[Destinacao]:
    return list(db.scalars(select(Destinacao).where(
        Destinacao.lote_id == lote_id, Destinacao.ativa.is_(True),
        or_(Destinacao.validade.is_(None), Destinacao.validade >= date.today())).order_by(Destinacao.id)))


def liberacoes_ativas(db: Session, solicitacao_id: int) -> list[LiberacaoCorte]:
    return list(db.scalars(select(LiberacaoCorte).where(LiberacaoCorte.solicitacao_id == solicitacao_id,
                                                        LiberacaoCorte.estornada.is_(False))))
