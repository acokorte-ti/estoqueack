"""Situação derivada da solicitação (§3.1) e textos comuns do fluxo.

A situação nunca é "setada à mão" depois do envio: ela é recalculada a partir dos fatos (cortes, COP, SA,
recebimento, corte em Itu) sempre que algum deles muda. Quando há mais de um corte (lote dividido), vale o
estágio **menos avançado**.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CadastroSa, CorteItu, SolicitacaoCorte

from .estoque import bitola
from .movimentos import pecas_cortadas

ORDEM = ["CORTADA", "EM_COP", "SA_PRONTO", "EM_TRANSITO", "AGUARDANDO_CORTE_ITU", "CONCLUIDA"]
ATIVAS_RJ = ("ENVIADA", "CORTADA_PARCIAL")


def _estagio_liberacao(db: Session, sol: SolicitacaoCorte, lib) -> str:
    item = lib.cop_item
    if item is None or item.cop.situacao == "ABERTO":
        return "CORTADA"
    if item.situacao == "EM_COP":
        sa = db.scalar(select(CadastroSa).where(CadastroSa.cop_item_id == item.id))
        return "SA_PRONTO" if sa is not None and sa.situacao == "CONFIRMADO" else "EM_COP"
    if item.situacao == "EM_TRANSITO":
        return "EM_TRANSITO"
    if sol.modo == "TRAZER_INTEIRA":
        feito = db.scalar(select(CorteItu.id).where(CorteItu.solicitacao_id == sol.id))
        return "CONCLUIDA" if feito else "AGUARDANDO_CORTE_ITU"
    return "CONCLUIDA"


def recalcular_solicitacao(db: Session, sol: SolicitacaoCorte) -> str:
    if sol.situacao in ("RASCUNHO", "CANCELADA"):
        return sol.situacao
    db.refresh(sol, ["liberacoes"])
    libs = [l for l in sol.liberacoes if not l.estornada]
    if sol.situacao == "MATERIAL_INSUFICIENTE" and not (sol.encerrada_saldo_pendente and libs):
        # sai daqui só por "trocar lote" (sem corte) ou por "encerrar com saldo pendente" (com corte)
        return sol.situacao
    if not libs:
        sol.situacao = "ENVIADA"
    elif pecas_cortadas(sol) < sol.quantidade and not sol.encerrada_saldo_pendente:
        sol.situacao = "CORTADA_PARCIAL"
    else:
        estagios = [_estagio_liberacao(db, sol, l) for l in libs]
        sol.situacao = min(estagios, key=ORDEM.index)
    db.flush()
    return sol.situacao


def material_texto(sol: SolicitacaoCorte) -> str:
    l = sol.lote
    ct = l.conteiner.codigo if l.conteiner else "sem contêiner"
    return f"{l.item.liga.codigo} {bitola(l.item)} / {ct}"
