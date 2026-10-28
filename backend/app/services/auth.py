"""Login local com bloqueio por tentativas, sessões no servidor e troca de senha."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core import seguranca
from app.core.config import Config
from app.models import Sessao, Usuario

from . import auditoria


class ErroAutenticacao(Exception):
    pass


@dataclass
class SessaoCriada:
    token: str
    csrf: str
    usuario: Usuario
    expira_em: datetime


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is not None and dt.tzinfo is None:   # SQLite devolve datetime sem fuso
        return dt.replace(tzinfo=timezone.utc)
    return dt


MSG_GENERICA = "Login ou senha inválidos."


def autenticar(db: Session, cfg: Config, login: str, senha: str, ip: str | None, user_agent: str | None) -> SessaoCriada:
    login = (login or "").strip().lower()
    usuario = db.scalar(select(Usuario).where(Usuario.login == login))

    if usuario is None or not usuario.ativo:
        seguranca.verificar_senha(senha, None)  # tempo constante
        auditoria.registrar(db, "LOGIN_FALHA", entidade="usuario", entidade_id=login, ip=ip,
                            depois={"motivo": "inexistente_ou_inativo"})
        db.commit()
        raise ErroAutenticacao(MSG_GENERICA)

    bloqueio = _aware(usuario.bloqueado_ate)
    if bloqueio and bloqueio > _agora():
        auditoria.registrar(db, "LOGIN_BLOQUEADO", usuario_id=usuario.id, ip=ip)
        db.commit()
        minutos = max(1, int((bloqueio - _agora()).total_seconds() // 60) + 1)
        raise ErroAutenticacao(f"Usuário bloqueado por excesso de tentativas. Tente novamente em {minutos} min.")

    if not seguranca.verificar_senha(senha, usuario.senha_hash):
        usuario.tentativas_falhas += 1
        if usuario.tentativas_falhas >= cfg.login_max_tentativas:
            usuario.bloqueado_ate = _agora() + timedelta(minutes=cfg.login_bloqueio_minutos)
            usuario.tentativas_falhas = 0
            auditoria.registrar(db, "USUARIO_BLOQUEADO", usuario_id=usuario.id, ip=ip)
        auditoria.registrar(db, "LOGIN_FALHA", usuario_id=usuario.id, ip=ip)
        db.commit()
        raise ErroAutenticacao(MSG_GENERICA)

    if seguranca.precisa_rehash(usuario.senha_hash):
        usuario.senha_hash = seguranca.gerar_hash_senha(senha)
    usuario.tentativas_falhas = 0
    usuario.bloqueado_ate = None
    usuario.ultimo_login = _agora()

    token, csrf = seguranca.gerar_token(), seguranca.gerar_token()
    expira = _agora() + timedelta(hours=cfg.sessao_horas)
    db.add(Sessao(token_hash=seguranca.hash_token(token), csrf=csrf, usuario_id=usuario.id,
                  expira_em=expira, ip=ip, user_agent=(user_agent or "")[:300]))
    auditoria.registrar(db, "LOGIN_OK", usuario_id=usuario.id, ip=ip)
    db.commit()
    return SessaoCriada(token, csrf, usuario, expira)


def sessao_por_token(db: Session, token: str | None) -> Sessao | None:
    if not token:
        return None
    s = db.scalar(select(Sessao).where(Sessao.token_hash == seguranca.hash_token(token)))
    if s is None or s.revogada or _aware(s.expira_em) <= _agora() or not s.usuario.ativo:
        return None
    return s


def encerrar(db: Session, sessao: Sessao, ip: str | None) -> None:
    sessao.revogada = True
    auditoria.registrar(db, "LOGOUT", usuario_id=sessao.usuario_id, ip=ip)
    db.commit()


def revogar_todas(db: Session, usuario_id: int, exceto_id: int | None = None) -> None:
    q = update(Sessao).where(Sessao.usuario_id == usuario_id, Sessao.revogada.is_(False))
    if exceto_id is not None:
        q = q.where(Sessao.id != exceto_id)
    db.execute(q.values(revogada=True))


def trocar_senha(db: Session, cfg: Config, usuario: Usuario, senha_atual: str, nova: str,
                 sessao_atual_id: int | None, ip: str | None) -> None:
    if not seguranca.verificar_senha(senha_atual, usuario.senha_hash):
        raise ErroAutenticacao("Senha atual incorreta.")
    if senha_atual == nova:
        raise ErroAutenticacao("A nova senha deve ser diferente da atual.")
    problemas = seguranca.problemas_senha(nova, usuario.login, cfg.senha_tamanho_minimo)
    if problemas:
        raise ErroAutenticacao(" ".join(problemas))
    usuario.senha_hash = seguranca.gerar_hash_senha(nova)
    usuario.trocar_senha = False
    revogar_todas(db, usuario.id, exceto_id=sessao_atual_id)
    auditoria.registrar(db, "SENHA_ALTERADA", usuario_id=usuario.id, ip=ip)
    db.commit()


def garantir_admin_inicial(db: Session, cfg: Config) -> None:
    """Cria o primeiro ADMIN se a tabela de usuários estiver vazia."""
    if db.scalar(select(Usuario.id).limit(1)) is not None:
        return
    if not cfg.admin_senha_inicial:
        raise RuntimeError("Nenhum usuário cadastrado: defina ADMIN_SENHA_INICIAL no .env para criar o administrador.")
    u = Usuario(login=cfg.admin_login.strip().lower(), nome=cfg.admin_nome, perfil="ADMIN", planta="ITU",
                senha_hash=seguranca.gerar_hash_senha(cfg.admin_senha_inicial), trocar_senha=True)
    db.add(u)
    db.flush()
    auditoria.registrar(db, "ADMIN_INICIAL_CRIADO", usuario_id=u.id, entidade="usuario", entidade_id=u.id)
    db.commit()
