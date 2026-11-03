"""Tabelas de apoio da Fase 1: parâmetros (T23), notificações (sino, §6), sincronização e cache do Mega (§7,
T15/T16), equivalência de ligas [P18], paridade RJ ↔ CM [P06] e material a chegar (T26) [P17]."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Date, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

from ._tipos import DataHora, JsonDoc, Kg, agora


class Parametro(Base):
    __tablename__ = "parametro"

    chave: Mapped[str] = mapped_column(String(40), primary_key=True)
    valor: Mapped[str] = mapped_column(String(200))
    tipo: Mapped[str] = mapped_column(String(10), default="NUMERO")   # NUMERO | TEXTO | HORARIOS
    descricao: Mapped[str] = mapped_column(String(200))
    atualizado_em: Mapped[datetime] = mapped_column(DataHora, default=agora)
    atualizado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))


class Notificacao(Base):
    """Aviso no sino do sistema (sem e-mail nesta versão [P05])."""
    __tablename__ = "notificacao"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id", ondelete="CASCADE"), index=True)
    tipo: Mapped[str] = mapped_column(String(40), index=True)
    texto: Mapped[str] = mapped_column(String(500))
    link: Mapped[str | None] = mapped_column(String(200))
    criado_em: Mapped[datetime] = mapped_column(DataHora, default=agora, index=True)
    lida_em: Mapped[datetime | None] = mapped_column(DataHora)


class SyncMega(Base):
    __tablename__ = "sync_mega"

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo: Mapped[str] = mapped_column(String(15))            # ESTOQUE | SA
    gatilho: Mapped[str] = mapped_column(String(15))         # AGENDADA | MANUAL
    iniciado_em: Mapped[datetime] = mapped_column(DataHora, default=agora, index=True)
    terminado_em: Mapped[datetime | None] = mapped_column(DataHora)
    situacao: Mapped[str] = mapped_column(String(10), default="RODANDO")   # RODANDO | OK | ERRO
    ultimo_lancamento: Mapped[int | None] = mapped_column(BigInteger)
    detalhes: Mapped[dict[str, Any] | None] = mapped_column(JsonDoc)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))


class MegaSaldo(Base):
    """Saldo físico e preço médio por código de MP na filial 3 (última sincronização)."""
    __tablename__ = "mega_saldo"

    codigo: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    descricao: Mapped[str | None] = mapped_column(String(200))
    saldo_kg: Mapped[float] = mapped_column(Kg)
    preco_medio: Mapped[float | None] = mapped_column(Kg)
    atualizado_em: Mapped[datetime] = mapped_column(DataHora, default=agora)


class MegaMovimento(Base):
    """Cópia incremental de EST_VW_MOVIMENTOESTOQUE (filial 3, itens MP), por MVT_IN_LANCAM."""
    __tablename__ = "mega_movimento"

    lancamento: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    codigo: Mapped[int] = mapped_column(Integer, index=True)
    data: Mapped[date] = mapped_column(Date, index=True)
    entrada_saida: Mapped[str] = mapped_column(String(2))
    tpm: Mapped[int] = mapped_column(Integer)
    tpm_descricao: Mapped[str | None] = mapped_column(String(80))
    documento: Mapped[str | None] = mapped_column(String(40), index=True)
    kg: Mapped[float] = mapped_column(Kg)
    codigo_destino: Mapped[int | None] = mapped_column(Integer)
    estorno: Mapped[bool] = mapped_column(Boolean, default=False)


class PendenciaMega(Base):
    """T15 (Mega com mais saldo → entrada a classificar) e T16 (divergência explicada)."""
    __tablename__ = "pendencia_mega"
    __table_args__ = (CheckConstraint("tipo IN ('ENTRADA','DIVERGENCIA')", name="ck_pend_tipo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo: Mapped[str] = mapped_column(String(12))
    codigo: Mapped[int] = mapped_column(Integer, index=True)
    kg: Mapped[float] = mapped_column(Kg)
    situacao: Mapped[str] = mapped_column(String(12), default="ABERTA", index=True)  # ABERTA | RESOLVIDA
    nota: Mapped[str | None] = mapped_column(String(1000))
    lote_id: Mapped[int | None] = mapped_column(ForeignKey("lote.id"))
    criado_em: Mapped[datetime] = mapped_column(DataHora, default=agora)
    resolvido_em: Mapped[datetime | None] = mapped_column(DataHora)
    resolvido_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))


class LigaEquivalente(Base):
    """Par de ligas compatíveis (ex.: 1.2344 ≈ H13) [P18]: aparecem com selo e pedem 'estou ciente'."""
    __tablename__ = "liga_equivalente"
    __table_args__ = (UniqueConstraint("liga_a_id", "liga_b_id", name="uq_liga_equiv"),
                      CheckConstraint("liga_a_id <> liga_b_id", name="ck_liga_equiv_diferente"))

    id: Mapped[int] = mapped_column(primary_key=True)
    liga_a_id: Mapped[int] = mapped_column(ForeignKey("liga.id"))
    liga_b_id: Mapped[int] = mapped_column(ForeignKey("liga.id"))
    observacao: Mapped[str | None] = mapped_column(String(200))


class ParidadeRj(Base):
    """Material RJ (descrição liga + bitola) ↔ item do catálogo / código Mega (CM), confirmado na carga [P06]."""
    __tablename__ = "paridade_rj"

    id: Mapped[int] = mapped_column(primary_key=True)
    descricao_rj: Mapped[str] = mapped_column(String(200), unique=True)
    item_mp_id: Mapped[int | None] = mapped_column(ForeignKey("item_mp.id"), index=True)
    confirmada: Mapped[bool] = mapped_column(Boolean, default=False)
    confirmada_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    confirmada_em: Mapped[datetime | None] = mapped_column(DataHora)


class PedidoAChegar(Base):
    """T26 Material a chegar [P17]."""
    __tablename__ = "pedido_a_chegar"
    __table_args__ = (CheckConstraint("situacao IN ('PEDIDO','EMBARCADO','CHEGOU','CANCELADO')",
                                      name="ck_pedido_situacao"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    item_mp_id: Mapped[int | None] = mapped_column(ForeignKey("item_mp.id"), index=True)
    descricao: Mapped[str | None] = mapped_column(String(200))
    fornecedor: Mapped[str | None] = mapped_column(String(120))
    kg: Mapped[float | None] = mapped_column(Kg)
    previsao: Mapped[date | None] = mapped_column(Date)
    situacao: Mapped[str] = mapped_column(String(10), default="PEDIDO")
    observacao: Mapped[str | None] = mapped_column(String(1000))
    criado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    criado_em: Mapped[datetime] = mapped_column(DataHora, default=agora)
