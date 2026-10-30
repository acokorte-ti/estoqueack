"""Envio de e-mail.

Dois caminhos, nesta ordem de preferência:

1. **Microsoft Graph** (recomendado no Microsoft 365): app registrado no Entra ID com a permissão de aplicativo
   `Mail.Send`, restrita à caixa do remetente. Usa client credentials; nenhuma senha de caixa é guardada.
   Variáveis: GRAPH_TENANT_ID, GRAPH_CLIENT_ID, GRAPH_CLIENT_SECRET, GRAPH_REMETENTE.
2. **SMTP** (outro provedor): SMTP_HOST, SMTP_PORTA, SMTP_USUARIO, SMTP_SENHA, SMTP_REMETENTE.

Sem nenhum dos dois configurado, apenas registra um aviso no log. Uma falha de envio nunca derruba a requisição.

Teste manual no servidor:  docker compose exec api python -m app.services.email destino@acokorte.com.br
"""
from __future__ import annotations

import json
import logging
import smtplib
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from email.message import EmailMessage
from email.utils import make_msgid

from app.core.config import Config

log = logging.getLogger("estoqueack.email")

GRAPH_TOKEN_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
GRAPH_SENDMAIL_URL = "https://graph.microsoft.com/v1.0/users/{remetente}/sendMail"
_TIMEOUT = 20

_token_lock = threading.Lock()
_token_cache: dict[str, tuple[str, float]] = {}   # chave (tenant|client) -> (token, expira_em epoch)


class ErroEnvio(Exception):
    """Falha de envio; a mensagem não contém segredos."""


def graph_configurado(cfg: Config) -> bool:
    return bool(cfg.graph_tenant_id and cfg.graph_client_id and cfg.graph_client_secret and cfg.graph_remetente)


def smtp_configurado(cfg: Config) -> bool:
    return bool(cfg.smtp_host and cfg.smtp_remetente)


def configurado(cfg: Config) -> bool:
    return graph_configurado(cfg) or smtp_configurado(cfg)


def modo(cfg: Config) -> str:
    return "graph" if graph_configurado(cfg) else "smtp" if smtp_configurado(cfg) else "nenhum"


# ---------------- Microsoft Graph ----------------

def _post(url: str, dados: bytes, cabecalhos: dict[str, str]) -> tuple[int, bytes]:
    if not url.startswith("https://"):
        raise ErroEnvio("URL de envio precisa ser https")
    req = urllib.request.Request(url, data=dados, headers=cabecalhos, method="POST")  # noqa: S310 — só https
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:  # noqa: S310 — só https (checado acima)
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def _codigo_erro(corpo: bytes) -> str:
    """Extrai só o código do erro (ex.: ErrorAccessDenied, invalid_client), sem ecoar o resto da resposta."""
    try:
        j = json.loads(corpo or b"{}")
    except ValueError:
        return "resposta inválida"
    if isinstance(j.get("error"), dict):
        return str(j["error"].get("code", "erro"))
    return str(j.get("error", "erro"))


def _token_graph(cfg: Config) -> str:
    chave = f"{cfg.graph_tenant_id}|{cfg.graph_client_id}"
    with _token_lock:
        atual = _token_cache.get(chave)
        if atual and atual[1] > time.time() + 60:
            return atual[0]
        dados = urllib.parse.urlencode({
            "grant_type": "client_credentials",
            "client_id": cfg.graph_client_id,
            "client_secret": cfg.graph_client_secret,
            "scope": "https://graph.microsoft.com/.default",
        }).encode()
        status, corpo = _post(GRAPH_TOKEN_URL.format(tenant=urllib.parse.quote(cfg.graph_tenant_id)), dados,
                              {"Content-Type": "application/x-www-form-urlencoded"})
        if status != 200:
            raise ErroEnvio(f"token do Entra recusado (HTTP {status}, {_codigo_erro(corpo)})")
        j = json.loads(corpo)
        _token_cache[chave] = (j["access_token"], time.time() + int(j.get("expires_in", 3600)))
        return j["access_token"]


def _enviar_graph(cfg: Config, para: str, assunto: str, texto: str, html: str | None) -> None:
    mensagem = {
        "message": {
            "subject": assunto,
            "body": {"contentType": "HTML" if html else "Text", "content": html or texto},
            "toRecipients": [{"emailAddress": {"address": para}}],
        },
        "saveToSentItems": True,
    }
    url = GRAPH_SENDMAIL_URL.format(remetente=urllib.parse.quote(cfg.graph_remetente, safe="@"))
    for tentativa in (1, 2):
        token = _token_graph(cfg)
        status, corpo = _post(url, json.dumps(mensagem).encode(),
                              {"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        if status == 202:
            return
        if status == 401 and tentativa == 1:          # token revogado/expirado antes da hora: pega outro
            _token_cache.clear()
            continue
        raise ErroEnvio(f"Graph recusou o envio (HTTP {status}, {_codigo_erro(corpo)})")


# ---------------- SMTP ----------------

def _enviar_smtp(cfg: Config, para: str, assunto: str, texto: str, html: str | None) -> None:
    msg = EmailMessage()
    msg["From"] = cfg.smtp_remetente
    msg["To"] = para
    msg["Subject"] = assunto
    msg["Message-ID"] = make_msgid(domain="acokorte.com.br")
    msg.set_content(texto)
    if html:
        msg.add_alternative(html, subtype="html")
    with smtplib.SMTP(cfg.smtp_host, cfg.smtp_porta, timeout=_TIMEOUT) as s:
        if cfg.smtp_starttls:
            s.starttls(context=ssl.create_default_context())
        if cfg.smtp_usuario:
            s.login(cfg.smtp_usuario, cfg.smtp_senha)
        s.send_message(msg)


# ---------------- Ponto de entrada ----------------

def enviar(cfg: Config, para: str, assunto: str, texto: str, html: str | None = None) -> bool:
    m = modo(cfg)
    if m == "nenhum":
        log.warning("e-mail não configurado: '%s' para %s NÃO enviado", assunto, para)
        return False
    try:
        (_enviar_graph if m == "graph" else _enviar_smtp)(cfg, para, assunto, texto, html)
        log.info("e-mail '%s' enviado para %s (%s)", assunto, para, m)
        return True
    except ErroEnvio as e:
        log.error("falha ao enviar e-mail '%s' para %s: %s", assunto, para, e)
    except Exception as e:  # noqa: BLE001 — falha de e-mail não pode derrubar a requisição
        log.error("falha ao enviar e-mail '%s' para %s (%s): %s", assunto, para, m, type(e).__name__)
    return False


if __name__ == "__main__":  # pragma: no cover — teste manual no servidor
    import sys

    from app.core.config import get_config

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if len(sys.argv) != 2:
        sys.exit("uso: python -m app.services.email destino@acokorte.com.br")
    c = get_config()
    print(f"modo: {modo(c)}")
    ok = enviar(c, sys.argv[1], "EstoqueACK: teste de envio",
                "Este é um teste de envio do EstoqueACK. Pode ignorar.",
                "<p>Este é um teste de envio do <b>EstoqueACK</b>. Pode ignorar.</p>")
    sys.exit(0 if ok else 1)
