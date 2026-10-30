"""Envio de e-mail por SMTP (Microsoft 365 ou outro). Sem SMTP configurado, apenas registra no log."""
from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import make_msgid

from app.core.config import Config

log = logging.getLogger("estoqueack.email")


def configurado(cfg: Config) -> bool:
    return bool(cfg.smtp_host and cfg.smtp_remetente)


def enviar(cfg: Config, para: str, assunto: str, texto: str, html: str | None = None) -> bool:
    if not configurado(cfg):
        log.warning("SMTP não configurado: e-mail '%s' para %s NÃO enviado", assunto, para)
        return False
    msg = EmailMessage()
    msg["From"] = cfg.smtp_remetente
    msg["To"] = para
    msg["Subject"] = assunto
    msg["Message-ID"] = make_msgid(domain="acokorte.com.br")
    msg.set_content(texto)
    if html:
        msg.add_alternative(html, subtype="html")
    try:
        with smtplib.SMTP(cfg.smtp_host, cfg.smtp_porta, timeout=20) as s:
            if cfg.smtp_starttls:
                s.starttls(context=ssl.create_default_context())
            if cfg.smtp_usuario:
                s.login(cfg.smtp_usuario, cfg.smtp_senha)
            s.send_message(msg)
        log.info("e-mail '%s' enviado para %s", assunto, para)
        return True
    except Exception as e:  # noqa: BLE001 — falha de e-mail não pode derrubar a requisição
        log.error("falha ao enviar e-mail '%s' para %s: %s", assunto, para, type(e).__name__)
        return False
