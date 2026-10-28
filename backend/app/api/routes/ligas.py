from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import deps
from app.api.schemas import LigaAtualizar, LigaCriar, LigaSaida
from app.core.db import get_db
from app.models import Liga, Usuario
from app.services import auditoria

router = APIRouter(prefix="/ligas", tags=["catálogo"])


def _snap(l: Liga) -> dict:
    return {"codigo": l.codigo, "nome": l.nome, "densidade": l.densidade, "apelidos": l.apelidos, "ativo": l.ativo}


@router.get("", response_model=list[LigaSaida])
def listar(db: Session = Depends(get_db), _: Usuario = Depends(deps.usuario_liberado)):
    return db.scalars(select(Liga).order_by(Liga.codigo)).all()


@router.post("", response_model=LigaSaida, status_code=201)
def criar(dados: LigaCriar, request: Request, db: Session = Depends(get_db),
          admin: Usuario = Depends(deps.exigir_perfil("ADMIN"))):
    codigo = dados.codigo.strip().upper()
    if db.scalar(select(Liga.id).where(Liga.codigo == codigo)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Liga já cadastrada.")
    l = Liga(codigo=codigo, nome=dados.nome, densidade=dados.densidade, apelidos=dados.apelidos)
    db.add(l)
    db.flush()
    auditoria.registrar(db, "LIGA_CRIADA", usuario_id=admin.id, entidade="liga", entidade_id=l.id,
                        depois=_snap(l), ip=deps.ip_cliente(request))
    db.commit()
    return l


@router.patch("/{liga_id}", response_model=LigaSaida)
def atualizar(liga_id: int, dados: LigaAtualizar, request: Request, db: Session = Depends(get_db),
              admin: Usuario = Depends(deps.exigir_perfil("ADMIN"))):
    l = db.get(Liga, liga_id)
    if l is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Liga não encontrada.")
    antes = _snap(l)
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(l, campo, valor)
    auditoria.registrar(db, "LIGA_ALTERADA", usuario_id=admin.id, entidade="liga", entidade_id=l.id,
                        antes=antes, depois=_snap(l), ip=deps.ip_cliente(request))
    db.commit()
    return l
