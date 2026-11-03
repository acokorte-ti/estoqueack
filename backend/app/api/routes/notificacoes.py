"""Sino de avisos (§6). Só no sistema, sem e-mail nesta versão [P05]."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.api import deps
from app.core.db import get_db
from app.models import Notificacao, Usuario
from app.services.base import NaoEncontrado, agora

router = APIRouter(prefix="/notificacoes", tags=["notificações"])


def _dict(n: Notificacao) -> dict:
    return {"id": n.id, "tipo": n.tipo, "texto": n.texto, "link": n.link, "criado_em": n.criado_em.isoformat(),
            "lida": n.lida_em is not None}


@router.get("")
def listar(somente_nao_lidas: bool = False, limite: int = Query(50, ge=1, le=200), db: Session = Depends(get_db),
           u: Usuario = Depends(deps.usuario_liberado)) -> dict:
    q = select(Notificacao).where(Notificacao.usuario_id == u.id)
    if somente_nao_lidas:
        q = q.where(Notificacao.lida_em.is_(None))
    itens = db.scalars(q.order_by(Notificacao.id.desc()).limit(limite)).all()
    nao_lidas = db.scalar(select(func.count(Notificacao.id)).where(Notificacao.usuario_id == u.id,
                                                                   Notificacao.lida_em.is_(None)))
    return {"itens": [_dict(n) for n in itens], "nao_lidas": int(nao_lidas or 0)}


@router.post("/{notif_id}/lida", status_code=204)
def marcar_lida(notif_id: int, db: Session = Depends(get_db), u: Usuario = Depends(deps.usuario_liberado)):
    n = db.get(Notificacao, notif_id)
    if n is None or n.usuario_id != u.id:
        raise NaoEncontrado("Aviso não encontrado.")
    n.lida_em = n.lida_em or agora()
    db.commit()


@router.post("/lidas", status_code=204)
def marcar_todas(db: Session = Depends(get_db), u: Usuario = Depends(deps.usuario_liberado)):
    db.execute(update(Notificacao).where(Notificacao.usuario_id == u.id, Notificacao.lida_em.is_(None))
               .values(lida_em=agora()))
    db.commit()
