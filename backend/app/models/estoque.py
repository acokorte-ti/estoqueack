from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

from ._tipos import DataHora, JsonDoc, Kg, agora
from .catalogo import Conteiner, ItemMP


class Lote(Base):
    """Lote de MP. Estoque 'balde' = (planta_fiscal, local_fisico):
        ITU/ITU = Estoque Mega · RJ/RJ = RJ no Rio · RJ/ITU = RJ em Itu
    """
    __tablename__ = "lote"
    __table_args__ = (
        CheckConstraint("saldo_kg >= 0", name="ck_lote_saldo_nao_negativo"),
        CheckConstraint("planta_fiscal IN ('ITU','RJ')", name="ck_lote_planta"),
        CheckConstraint("local_fisico IN ('ITU','RJ')", name="ck_lote_local"),
        CheckConstraint("tipo IN ('ORIGINAL','SOBRA','RETO')", name="ck_lote_tipo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True, index=True)   # L-000001
    conteiner_id: Mapped[int | None] = mapped_column(ForeignKey("conteiner.id"), index=True)
    item_mp_id: Mapped[int] = mapped_column(ForeignKey("item_mp.id"), index=True)
    planta_fiscal: Mapped[str] = mapped_column(String(3))
    local_fisico: Mapped[str] = mapped_column(String(3))
    tipo: Mapped[str] = mapped_column(String(10), default="ORIGINAL")
    lote_pai_id: Mapped[int | None] = mapped_column(ForeignKey("lote.id"), index=True)
    origem_identificada: Mapped[bool] = mapped_column(Boolean, default=True)
    peso_inicial_kg: Mapped[float] = mapped_column(Kg)
    pecas_iniciais: Mapped[int | None] = mapped_column(Integer)
    saldo_kg: Mapped[float] = mapped_column(Kg)
    custo_kg: Mapped[float | None] = mapped_column(Kg)     # opcional (foco inicial é peso)
    documento_entrada: Mapped[str | None] = mapped_column(String(60))   # NF
    status: Mapped[str] = mapped_column(String(12), default="ATIVO")     # ATIVO | ESGOTADO
    criado_em: Mapped[datetime] = mapped_column(DataHora, default=agora)
    criado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))

    conteiner: Mapped[Conteiner | None] = relationship()
    item: Mapped[ItemMP] = relationship()
    pai: Mapped[Lote | None] = relationship(remote_side="Lote.id")


class Movimento(Base):
    """Movimento de estoque. IMUTÁVEL: correções são feitas por ESTORNO (UPDATE/DELETE bloqueados)."""
    __tablename__ = "movimento"
    __table_args__ = (CheckConstraint("kg <> 0", name="ck_mov_kg_nao_zero"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    lote_id: Mapped[int] = mapped_column(ForeignKey("lote.id"), index=True)
    tipo: Mapped[str] = mapped_column(String(20), index=True)
    # ENTRADA | SAIDA_CORTE_RJ | ENVIO_ITU | RECEBIMENTO_ITU | CONSUMO_OP | GERA_SOBRA | GERA_RETO
    # | AJUSTE_INVENTARIO | ESTORNO | SALDO_INICIAL
    kg: Mapped[float] = mapped_column(Kg)                  # + entrada, − saída
    pecas: Mapped[int | None] = mapped_column(Integer)
    op: Mapped[int | None] = mapped_column(Integer, index=True)
    sa_codigo: Mapped[int | None] = mapped_column(Integer, index=True)
    cop_numero: Mapped[int | None] = mapped_column(Integer, index=True)
    documento: Mapped[str | None] = mapped_column(String(60))
    data_referencia: Mapped[date | None] = mapped_column(Date)       # data do fato (ex.: histórico importado)
    justificativa: Mapped[str | None] = mapped_column(String(500))
    confirmacoes: Mapped[dict[str, Any] | None] = mapped_column(JsonDoc)   # {codigo_ocorrencia: justificativa}
    estorno_de_id: Mapped[int | None] = mapped_column(ForeignKey("movimento.id"))
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    criado_em: Mapped[datetime] = mapped_column(DataHora, default=agora, index=True)

    lote: Mapped[Lote] = relationship()


class Destinacao(Base):
    """Reserva ou restrição de uso de um lote. Exige 'estou ciente' em toda baixa."""
    __tablename__ = "destinacao"
    __table_args__ = (CheckConstraint("tipo IN ('RESERVA','RESTRICAO')", name="ck_destinacao_tipo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    lote_id: Mapped[int] = mapped_column(ForeignKey("lote.id"), index=True)
    tipo: Mapped[str] = mapped_column(String(10))
    descricao: Mapped[str] = mapped_column(String(300))
    kg: Mapped[float | None] = mapped_column(Kg)
    validade: Mapped[date | None] = mapped_column(Date)
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    criado_em: Mapped[datetime] = mapped_column(DataHora, default=agora)


class Nota(Base):
    """Comentários livres (ex.: análises e compras futuras do Renato)."""
    __tablename__ = "nota"

    id: Mapped[int] = mapped_column(primary_key=True)
    entidade: Mapped[str] = mapped_column(String(20))      # LOTE | ITEM | LIGA
    entidade_id: Mapped[int] = mapped_column(Integer, index=True)
    texto: Mapped[str] = mapped_column(String(2000))
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    criado_em: Mapped[datetime] = mapped_column(DataHora, default=agora)
