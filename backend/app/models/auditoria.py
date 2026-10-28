from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

from ._tipos import DataHora, JsonDoc, agora


class Auditoria(Base):
    """Trilha de auditoria. Somente INSERT (UPDATE/DELETE bloqueados por trigger no PostgreSQL)."""
    __tablename__ = "auditoria"

    id: Mapped[int] = mapped_column(primary_key=True)
    quando: Mapped[datetime] = mapped_column(DataHora, default=agora, index=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"), index=True)
    acao: Mapped[str] = mapped_column(String(60), index=True)          # ex.: LOGIN_OK, USUARIO_CRIADO
    entidade: Mapped[str | None] = mapped_column(String(40))
    entidade_id: Mapped[str | None] = mapped_column(String(40))
    antes: Mapped[dict[str, Any] | None] = mapped_column(JsonDoc)
    depois: Mapped[dict[str, Any] | None] = mapped_column(JsonDoc)
    ip: Mapped[str | None] = mapped_column(String(64))
