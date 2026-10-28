"""Dependências da API: sessão do banco, usuário logado, CSRF e controle por perfil."""
from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core import seguranca
from app.core.config import Config, get_config
from app.core.db import get_db
from app.models import Sessao, Usuario
from app.services import auth

COOKIE_SESSAO = "ack_sessao"
COOKIE_CSRF = "ack_csrf"
HEADER_CSRF = "X-CSRF-Token"
METODOS_SEGUROS = {"GET", "HEAD", "OPTIONS"}


def ip_cliente(request: Request) -> str | None:
    return request.client.host if request.client else None


def sessao_atual(request: Request, db: Session = Depends(get_db)) -> Sessao:
    s = auth.sessao_por_token(db, request.cookies.get(COOKIE_SESSAO))
    if s is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sessão expirada ou inválida. Faça login novamente.")
    if request.method not in METODOS_SEGUROS:
        if not seguranca.comparar(request.headers.get(HEADER_CSRF), s.csrf):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Token CSRF inválido.")
    return s


def usuario_logado(sessao: Sessao = Depends(sessao_atual)) -> Usuario:
    return sessao.usuario


def usuario_liberado(usuario: Usuario = Depends(usuario_logado)) -> Usuario:
    """Usuário que já trocou a senha temporária."""
    if usuario.trocar_senha:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Troque sua senha antes de continuar.")
    return usuario


def exigir_perfil(*perfis: str) -> Callable[..., Usuario]:
    def _dep(usuario: Usuario = Depends(usuario_liberado)) -> Usuario:
        if usuario.perfil != "ADMIN" and usuario.perfil not in perfis:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Seu perfil não tem permissão para esta ação.")
        return usuario
    return _dep


def config() -> Config:
    return get_config()
