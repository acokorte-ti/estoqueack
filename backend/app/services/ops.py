"""OP: leitura no Mega com cache local (`ordem_producao`). Se o Mega cair, o sistema segue com o cache ou com os
dados digitados, marcados como "não confirmado no Mega" (§7)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.integrations.mega import fabrica
from app.integrations.mega.consultas import SITUACOES_OP
from app.models import OrdemProducao

from .base import agora


@dataclass
class DadosOp:
    numero: int
    encontrada: bool                 # False = o Mega respondeu que a OP não existe
    confirmada_mega: bool            # True = lida agora no Mega
    item_codigo: int | None = None
    item_descricao: str | None = None
    cliente: str | None = None
    pedido: str | None = None
    situacao: str | None = None
    quantidade: float | None = None
    data_entrega: date | None = None
    erro_mega: str | None = None

    @property
    def situacao_descricao(self) -> str | None:
        return SITUACOES_OP.get(self.situacao or "", (self.situacao, None))[0]

    @property
    def aberta(self) -> bool | None:
        """True/False quando o código de situação é conhecido; None quando ainda não foi mapeado."""
        return SITUACOES_OP.get(self.situacao or "", (None, None))[1]


def _do_cache(c: OrdemProducao, erro: str | None) -> DadosOp:
    return DadosOp(c.numero, True, False, c.item_codigo, c.item_descricao, c.cliente, c.pedido, c.situacao,
                   c.quantidade, c.data_entrega, erro)


def consultar(db: Session, numero: int) -> DadosOp:
    try:
        op = fabrica.obter().ordem_producao(numero)
    except Exception as e:  # noqa: BLE001 — Mega fora do ar não derruba o sistema
        cache = db.get(OrdemProducao, numero)
        motivo = str(e) if isinstance(e, fabrica.MegaIndisponivel) else f"Erro ao consultar o Mega ({type(e).__name__})"
        return _do_cache(cache, motivo) if cache else DadosOp(numero, True, False, erro_mega=motivo)
    if op is None:
        return DadosOp(numero, False, True)
    d = DadosOp(op.numero, True, True, op.item_codigo, op.item_descricao, op.cliente,
                getattr(op, "pedido", None), op.situacao, op.quantidade, op.data_recebimento)
    c = db.get(OrdemProducao, numero) or OrdemProducao(numero=numero)
    c.item_codigo, c.item_descricao, c.cliente, c.pedido = d.item_codigo, d.item_descricao, d.cliente, d.pedido
    c.cliente_codigo = getattr(op, "cliente_codigo", None)
    c.situacao, c.quantidade, c.data_entrega, c.fonte, c.atualizado_em = (d.situacao, d.quantidade, d.data_entrega,
                                                                         "MEGA", agora())
    db.add(c)
    db.flush()
    return d
