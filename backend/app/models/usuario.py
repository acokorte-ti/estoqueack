from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

from ._tipos import DataHora, agora


class Perfil(str, enum.Enum):
    ADMIN = "ADMIN"                # Administração completa
    ESTOQUE = "ESTOQUE"            # Fabiano / Matheus — movimentações em Itu
    OPERACAO_RJ = "OPERACAO_RJ"    # Marcelo — corte, peso real, COP, entrada por NF no RJ
    ANALISE = "ANALISE"            # Renato — consulta, destinações, notas


class Usuario(Base):
    __tablename__ = "usuario"

    id: Mapped[int] = mapped_column(primary_key=True)
    login: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    nome: Mapped[str] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(160))
    perfil: Mapped[str] = mapped_column(String(20), default=Perfil.ANALISE.value)
    planta: Mapped[str] = mapped_column(String(3), default="ITU")  # ITU | RJ
    senha_hash: Mapped[str] = mapped_column(String(255))
    trocar_senha: Mapped[bool] = mapped_column(Boolean, default=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    tentativas_falhas: Mapped[int] = mapped_column(Integer, default=0)
    bloqueado_ate: Mapped[datetime | None] = mapped_column(DataHora)
    ultimo_login: Mapped[datetime | None] = mapped_column(DataHora)
    criado_em: Mapped[datetime] = mapped_column(DataHora, default=agora)
    atualizado_em: Mapped[datetime] = mapped_column(DataHora, default=agora, onupdate=agora)

    sessoes: Mapped[list[Sessao]] = relationship(back_populates="usuario")


class Sessao(Base):
    __tablename__ = "sessao"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    csrf: Mapped[str] = mapped_column(String(64))
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id", ondelete="CASCADE"), index=True)
    criada_em: Mapped[datetime] = mapped_column(DataHora, default=agora)
    expira_em: Mapped[datetime] = mapped_column(DataHora)
    revogada: Mapped[bool] = mapped_column(Boolean, default=False)
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(300))

    usuario: Mapped[Usuario] = relationship(back_populates="sessoes")
