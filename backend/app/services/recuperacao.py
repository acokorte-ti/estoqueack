"""Recuperação de senha por e-mail: link de uso único, válido por poucos minutos, sem revelar se o usuário existe."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.core import seguranca
from app.core.config import Config
from app.models import TokenSenha, Usuario

from . import auditoria
from .auth import ErroAutenticacao, revogar_todas

MENSAGEM_PADRAO = ("Se o login ou e-mail estiver cadastrado, enviaremos um link para criar uma nova senha. "
                   "Confira sua caixa de entrada e o spam.")


@dataclass
class PedidoCriado:
    usuario: Usuario
    token: str
    link: str


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def solicitar(db: Session, cfg: Config, identificador: str, ip: str | None) -> PedidoCriado | None:
    """Cria o link se o usuário existir, estiver ativo e tiver e-mail. Sempre audita; nunca informa o motivo."""
    ident = (identificador or "").strip().lower()
    uma_hora = _agora() - timedelta(hours=1)
    if ip and (db.scalar(select(func.count(TokenSenha.id)).where(TokenSenha.ip == ip,
                                                                TokenSenha.criado_em >= uma_hora)) or 0) >= 10:
        auditoria.registrar(db, "SENHA_RECUPERACAO_LIMITE_IP", ip=ip)
        db.commit()
        return None
    u = db.scalar(select(Usuario).where(or_(Usuario.login == ident, func.lower(Usuario.email) == ident)))
    if u is None or not u.ativo or not u.email:
        auditoria.registrar(db, "SENHA_RECUPERACAO_IGNORADA", entidade="usuario", entidade_id=ident[:40], ip=ip,
                            depois={"motivo": "inexistente_inativo_ou_sem_email"})
        db.commit()
        return None
    recentes = db.scalar(select(func.count(TokenSenha.id)).where(TokenSenha.usuario_id == u.id,
                                                                 TokenSenha.criado_em >= uma_hora)) or 0
    if recentes >= cfg.recuperacao_max_por_hora:
        auditoria.registrar(db, "SENHA_RECUPERACAO_LIMITE", usuario_id=u.id, ip=ip)
        db.commit()
        return None
    # Um link novo invalida os anteriores ainda não usados
    db.execute(update(TokenSenha).where(TokenSenha.usuario_id == u.id, TokenSenha.usado_em.is_(None))
               .values(usado_em=_agora()))
    token = seguranca.gerar_token()
    db.add(TokenSenha(usuario_id=u.id, token_hash=seguranca.hash_token(token), ip=ip,
                      expira_em=_agora() + timedelta(minutes=cfg.recuperacao_minutos)))
    auditoria.registrar(db, "SENHA_RECUPERACAO_SOLICITADA", usuario_id=u.id, ip=ip)
    db.commit()
    return PedidoCriado(u, token, f"{cfg.app_url.rstrip('/')}/redefinir-senha?token={token}")


def _token_valido(db: Session, token: str) -> TokenSenha | None:
    t = db.scalar(select(TokenSenha).where(TokenSenha.token_hash == seguranca.hash_token(token or "")))
    if t is None or t.usado_em is not None or _aware(t.expira_em) <= _agora():
        return None
    u = db.get(Usuario, t.usuario_id)
    return t if u is not None and u.ativo else None


def verificar(db: Session, token: str) -> Usuario | None:
    t = _token_valido(db, token)
    return db.get(Usuario, t.usuario_id) if t else None


def redefinir(db: Session, cfg: Config, token: str, nova: str, ip: str | None) -> Usuario:
    t = _token_valido(db, token)
    if t is None:
        raise ErroAutenticacao("Link inválido ou expirado. Peça um novo em \"Esqueci minha senha\".")
    u = db.get(Usuario, t.usuario_id)
    problemas = seguranca.problemas_senha(nova, u.login, cfg.senha_tamanho_minimo)
    if problemas:
        raise ErroAutenticacao(" ".join(problemas))
    u.senha_hash = seguranca.gerar_hash_senha(nova)
    u.trocar_senha = False
    u.tentativas_falhas = 0
    u.bloqueado_ate = None
    t.usado_em = _agora()
    revogar_todas(db, u.id)
    auditoria.registrar(db, "SENHA_REDEFINIDA_POR_EMAIL", usuario_id=u.id, ip=ip)
    db.commit()
    return u


def texto_email(cfg: Config, nome: str, link: str) -> tuple[str, str, str]:
    assunto = "EstoqueACK: criar uma nova senha"
    texto = (f"Olá, {nome}.\n\nRecebemos um pedido para criar uma nova senha no EstoqueACK.\n\n"
             f"Para continuar, abra o link abaixo (vale por {cfg.recuperacao_minutos} minutos e só pode ser usado "
             f"uma vez):\n\n{link}\n\nSe não foi você, ignore este e-mail: sua senha atual continua valendo.\n\n"
             "AçoKorte · EstoqueACK")
    html = (f"<p>Olá, {nome}.</p><p>Recebemos um pedido para criar uma nova senha no <b>EstoqueACK</b>.</p>"
            f"<p><a href=\"{link}\" style=\"background:#BE0A0F;color:#fff;padding:12px 20px;text-decoration:none;"
            f"border-radius:4px;display:inline-block\">Criar nova senha</a></p>"
            f"<p>O link vale por {cfg.recuperacao_minutos} minutos e só pode ser usado uma vez.</p>"
            "<p>Se não foi você, ignore este e-mail: sua senha atual continua valendo.</p>"
            "<p style=\"color:#666\">AçoKorte · EstoqueACK</p>")
    return assunto, texto, html
