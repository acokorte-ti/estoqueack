from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import deps
from app.api.schemas import UsuarioAtualizar, UsuarioCriadoSaida, UsuarioCriar, UsuarioSaida
from app.core import seguranca
from app.core.db import get_db
from app.models import Usuario
from app.services import auditoria, auth

router = APIRouter(prefix="/usuarios", tags=["usuários"])
somente_admin = deps.exigir_perfil("ADMIN")


def _snapshot(u: Usuario) -> dict:
    return {"login": u.login, "nome": u.nome, "email": u.email, "perfil": u.perfil, "planta": u.planta,
            "ativo": u.ativo}


@router.get("", response_model=list[UsuarioSaida])
def listar(db: Session = Depends(get_db), _: Usuario = Depends(somente_admin)):
    return db.scalars(select(Usuario).order_by(Usuario.nome)).all()


@router.post("", response_model=UsuarioCriadoSaida, status_code=201)
def criar(dados: UsuarioCriar, request: Request, db: Session = Depends(get_db),
          admin: Usuario = Depends(somente_admin)):
    login = dados.login.strip().lower()
    if db.scalar(select(Usuario.id).where(Usuario.login == login)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Já existe um usuário com este login.")
    senha = seguranca.gerar_senha_temporaria()
    u = Usuario(login=login, nome=dados.nome, email=dados.email, perfil=dados.perfil, planta=dados.planta,
                senha_hash=seguranca.gerar_hash_senha(senha), trocar_senha=True)
    db.add(u)
    db.flush()
    auditoria.registrar(db, "USUARIO_CRIADO", usuario_id=admin.id, entidade="usuario", entidade_id=u.id,
                        depois=_snapshot(u), ip=deps.ip_cliente(request))
    db.commit()
    return UsuarioCriadoSaida(usuario=UsuarioSaida.model_validate(u), senha_temporaria=senha)


@router.patch("/{usuario_id}", response_model=UsuarioSaida)
def atualizar(usuario_id: int, dados: UsuarioAtualizar, request: Request, db: Session = Depends(get_db),
              admin: Usuario = Depends(somente_admin)):
    u = db.get(Usuario, usuario_id)
    if u is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuário não encontrado.")
    if u.id == admin.id and (dados.ativo is False or (dados.perfil and dados.perfil != "ADMIN")):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Você não pode desativar ou rebaixar o próprio usuário.")
    antes = _snapshot(u)
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(u, campo, valor)
    if dados.ativo is False:
        auth.revogar_todas(db, u.id)
    auditoria.registrar(db, "USUARIO_ALTERADO", usuario_id=admin.id, entidade="usuario", entidade_id=u.id,
                        antes=antes, depois=_snapshot(u), ip=deps.ip_cliente(request))
    db.commit()
    return u


@router.post("/{usuario_id}/redefinir-senha", response_model=UsuarioCriadoSaida)
def redefinir_senha(usuario_id: int, request: Request, db: Session = Depends(get_db),
                    admin: Usuario = Depends(somente_admin)):
    u = db.get(Usuario, usuario_id)
    if u is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuário não encontrado.")
    senha = seguranca.gerar_senha_temporaria()
    u.senha_hash = seguranca.gerar_hash_senha(senha)
    u.trocar_senha = True
    u.tentativas_falhas = 0
    u.bloqueado_ate = None
    auth.revogar_todas(db, u.id)
    auditoria.registrar(db, "SENHA_REDEFINIDA", usuario_id=admin.id, entidade="usuario", entidade_id=u.id,
                        ip=deps.ip_cliente(request))
    db.commit()
    return UsuarioCriadoSaida(usuario=UsuarioSaida.model_validate(u), senha_temporaria=senha)
