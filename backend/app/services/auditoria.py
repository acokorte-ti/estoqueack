from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import Auditoria


def registrar(db: Session, acao: str, *, usuario_id: int | None = None, entidade: str | None = None,
              entidade_id: Any = None, antes: dict | None = None, depois: dict | None = None,
              ip: str | None = None) -> None:
    """Adiciona um registro de auditoria na transação corrente (commit fica com quem chama)."""
    db.add(Auditoria(acao=acao, usuario_id=usuario_id, entidade=entidade,
                     entidade_id=None if entidade_id is None else str(entidade_id),
                     antes=antes, depois=depois, ip=ip))
