from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

from ._tipos import DataHora, Densidade, JsonDoc, Mm, agora


class Liga(Base):
    __tablename__ = "liga"
    __table_args__ = (CheckConstraint("densidade > 6 AND densidade < 10", name="ck_liga_densidade"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(30), unique=True, index=True)   # H13, D2, CR12MOV…
    nome: Mapped[str] = mapped_column(String(120))
    apelidos: Mapped[list[str]] = mapped_column(JsonDoc, default=list)          # "Cr12 MoV", "DIN 1.2344"…
    densidade: Mapped[float] = mapped_column(Densidade, default=7.85)                  # g/cm³
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)


class ItemMP(Base):
    """Item de matéria-prima = liga + bitola. Pode ter código no Mega (ITU) ou não (só RJ)."""
    __tablename__ = "item_mp"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo_mega: Mapped[int | None] = mapped_column(Integer, unique=True, index=True)
    descricao: Mapped[str] = mapped_column(String(200))
    liga_id: Mapped[int] = mapped_column(ForeignKey("liga.id"), index=True)
    formato: Mapped[str] = mapped_column(String(15))      # RETANGULAR | REDONDO | RETO
    espessura: Mapped[float | None] = mapped_column(Mm)
    largura: Mapped[float | None] = mapped_column(Mm)
    diametro: Mapped[float | None] = mapped_column(Mm)
    comprimento_fixado: Mapped[str | None] = mapped_column(String(120))
    um: Mapped[str] = mapped_column(String(5), default="KG")
    observacao_uso: Mapped[str | None] = mapped_column(String(500))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)

    liga: Mapped[Liga] = relationship()


class Conteiner(Base):
    """Lote de importação (ex.: CH11EA). Usado como ID de origem."""
    __tablename__ = "conteiner"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    data_entrada: Mapped[date | None] = mapped_column(Date)
    observacao: Mapped[str | None] = mapped_column(String(500))
    criado_em: Mapped[datetime] = mapped_column(DataHora, default=agora)
