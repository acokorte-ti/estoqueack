import json
import logging

import pytest

from app.core.config import Config
from app.services import email


def _cfg(**kw) -> Config:
    base = {"graph_tenant_id": "", "graph_client_id": "", "graph_client_secret": "", "graph_remetente": "",
            "smtp_host": "", "smtp_remetente": ""}
    return Config(_env_file=None, **(base | kw))


GRAPH = {"graph_tenant_id": "tenant-x", "graph_client_id": "cliente-x", "graph_client_secret": "segredo-x",
         "graph_remetente": "estoque.smtp@acokorte.com.br"}


@pytest.fixture()
def http(monkeypatch):
    """Simula o Entra e o Graph. `respostas` = fila de (status, corpo) para o sendMail."""
    chamadas = []
    estado = {"envios": [(202, b"")], "token": (200, json.dumps({"access_token": "tok-1", "expires_in": 3600}))}
    email._token_cache.clear()

    def falso(url, dados, cab):
        chamadas.append({"url": url, "dados": dados, "cab": cab})
        if "login.microsoftonline.com" in url:
            s, c = estado["token"]
            return s, c.encode() if isinstance(c, str) else c
        return estado["envios"].pop(0)

    monkeypatch.setattr(email, "_post", falso)
    return chamadas, estado


def test_modo():
    assert email.modo(_cfg()) == "nenhum"
    assert email.modo(_cfg(smtp_host="smtp.x", smtp_remetente="a@x")) == "smtp"
    assert email.modo(_cfg(smtp_host="smtp.x", smtp_remetente="a@x", **GRAPH)) == "graph"   # Graph tem prioridade
    assert email.modo(_cfg(**(GRAPH | {"graph_client_secret": ""}))) == "nenhum"           # incompleto


def test_sem_configuracao_nao_envia(caplog):
    with caplog.at_level(logging.WARNING):
        assert email.enviar(_cfg(), "a@b.com", "Assunto", "texto") is False
    assert "NÃO enviado" in caplog.text


def test_graph_envia(http):
    chamadas, _ = http
    assert email.enviar(_cfg(**GRAPH), "fabiano@acokorte.com.br", "Recuperar senha", "texto", "<p>html</p>")
    token, envio = chamadas
    assert token["url"] == "https://login.microsoftonline.com/tenant-x/oauth2/v2.0/token"
    assert b"grant_type=client_credentials" in token["dados"] and b"graph.microsoft.com%2F.default" in token["dados"]
    assert envio["url"] == "https://graph.microsoft.com/v1.0/users/estoque.smtp@acokorte.com.br/sendMail"
    assert envio["cab"]["Authorization"] == "Bearer tok-1"
    corpo = json.loads(envio["dados"])["message"]
    assert corpo["subject"] == "Recuperar senha"
    assert corpo["body"] == {"contentType": "HTML", "content": "<p>html</p>"}
    assert corpo["toRecipients"] == [{"emailAddress": {"address": "fabiano@acokorte.com.br"}}]


def test_graph_reaproveita_token(http):
    chamadas, estado = http
    estado["envios"] = [(202, b""), (202, b"")]
    cfg = _cfg(**GRAPH)
    assert email.enviar(cfg, "a@acokorte.com.br", "1", "t") and email.enviar(cfg, "b@acokorte.com.br", "2", "t")
    assert sum("login.microsoftonline.com" in c["url"] for c in chamadas) == 1
    assert json.loads(chamadas[-1]["dados"])["message"]["body"]["contentType"] == "Text"


def test_graph_401_renova_token_uma_vez(http):
    chamadas, estado = http
    estado["envios"] = [(401, b"{}"), (202, b"")]
    assert email.enviar(_cfg(**GRAPH), "a@acokorte.com.br", "x", "t")
    assert sum("login.microsoftonline.com" in c["url"] for c in chamadas) == 2


def test_graph_recusado_registra_codigo_sem_segredo(http, caplog):
    _, estado = http
    estado["envios"] = [(403, json.dumps({"error": {"code": "ErrorAccessDenied", "message": "detalhe"}}).encode())]
    with caplog.at_level(logging.ERROR):
        assert email.enviar(_cfg(**GRAPH), "a@acokorte.com.br", "x", "t") is False
    assert "HTTP 403" in caplog.text and "ErrorAccessDenied" in caplog.text
    assert "segredo-x" not in caplog.text and "tok-1" not in caplog.text


def test_graph_token_recusado(http, caplog):
    _, estado = http
    estado["token"] = (401, json.dumps({"error": "invalid_client", "error_description": "segredo-x errado"}))
    with caplog.at_level(logging.ERROR):
        assert email.enviar(_cfg(**GRAPH), "a@acokorte.com.br", "x", "t") is False
    assert "invalid_client" in caplog.text and "segredo-x" not in caplog.text


def test_graph_erro_de_rede_nao_derruba(monkeypatch, caplog):
    email._token_cache.clear()

    def explode(*_a):
        raise OSError("rede")

    monkeypatch.setattr(email, "_post", explode)
    with caplog.at_level(logging.ERROR):
        assert email.enviar(_cfg(**GRAPH), "a@acokorte.com.br", "x", "t") is False
    assert "OSError" in caplog.text
