import re

import pytest

from tests.conftest import login, preparar_admin

pytest.importorskip("fastapi")


@pytest.fixture()
def caixa(monkeypatch):
    """Captura os e-mails em vez de enviar."""
    enviados = []
    from app.services import email
    monkeypatch.setattr(email, "enviar", lambda cfg, para, assunto, texto, html=None: enviados.append(
        {"para": para, "assunto": assunto, "texto": texto}) or True)
    return enviados


def _criar(client, h, **kw):
    corpo = {"login": "fabiano.camargo", "nome": "Fabiano Camargo", "email": "Fabiano@AcoKorte.com.br",
             "perfil": "ESTOQUE", "senha": "Estoque2026ok", "trocar_senha": False} | kw
    return client.post("/api/usuarios", json=corpo, headers=h)


def test_login_padrao_nome_sobrenome(client):
    h = preparar_admin(client)
    assert _criar(client, h, login="fabiano").status_code == 422           # sem ponto
    assert _criar(client, h, login="fabiano_camargo").status_code == 422
    assert _criar(client, h, login="fábio.camargo").status_code == 422      # sem acento
    r = _criar(client, h, login="Fabiano.Camargo")                          # normaliza para minúsculo
    assert r.status_code == 201 and r.json()["usuario"]["login"] == "fabiano.camargo"
    assert r.json()["usuario"]["email"] == "fabiano@acokorte.com.br"


def test_admin_define_senha_e_nao_obriga_troca(client):
    h = preparar_admin(client)
    r = _criar(client, h)
    assert r.json()["senha_temporaria"] is None and r.json()["usuario"]["trocar_senha"] is False
    client.post("/api/auth/logout", headers=h)
    r = login(client, "fabiano.camargo", "Estoque2026ok")
    assert r.status_code == 200 and r.json()["usuario"]["trocar_senha"] is False
    assert client.get("/api/painel/resumo").status_code == 200              # entra direto


def test_admin_obriga_troca_e_senha_fraca(client):
    h = preparar_admin(client)
    assert _criar(client, h, senha="curta").status_code == 400
    assert _criar(client, h, senha="fabiano.camargo123").status_code == 400  # contém o login
    r = _criar(client, h, senha=None, trocar_senha=True)
    assert r.json()["senha_temporaria"] and r.json()["usuario"]["trocar_senha"] is True
    assert _criar(client, h, login="outro.usuario").status_code == 409       # e-mail repetido


def test_redefinir_e_alterar_flag(client):
    h = preparar_admin(client)
    uid = _criar(client, h).json()["usuario"]["id"]
    r = client.post(f"/api/usuarios/{uid}/redefinir-senha", json={"senha": "NovaSenha2026b", "trocar_senha": True},
                    headers=h)
    assert r.status_code == 200 and r.json()["senha_temporaria"] is None and r.json()["usuario"]["trocar_senha"]
    r = client.post(f"/api/usuarios/{uid}/redefinir-senha", headers=h)      # sem corpo: gera temporária
    assert r.json()["senha_temporaria"]
    assert client.patch(f"/api/usuarios/{uid}", json={"trocar_senha": False}, headers=h).json()["trocar_senha"] is False


def test_manter_conectado(client):
    preparar_admin(client)
    client.post("/api/auth/logout", headers={"X-CSRF-Token": client.cookies.get("ack_csrf")})
    r = client.post("/api/auth/login", json={"login": "admin", "senha": "NovaSenha2026x", "lembrar": True})
    assert r.status_code == 200
    idade = re.search(r"ack_sessao=[^;]+;.*?Max-Age=(\d+)", r.headers["set-cookie"])
    assert idade and int(idade.group(1)) == 30 * 86400


def test_recuperacao_completa(client, caixa):
    h = preparar_admin(client)
    _criar(client, h)
    client.post("/api/auth/logout", headers=h)
    padrao = client.post("/api/auth/recuperar", json={"identificador": "naoexiste"}).json()
    r = client.post("/api/auth/recuperar", json={"identificador": "fabiano@acokorte.com.br"})
    assert r.status_code == 202 and r.json() == padrao                      # mesma resposta: não revela usuário
    assert len(caixa) == 1 and caixa[0]["para"] == "fabiano@acokorte.com.br"
    token = re.search(r"token=([\w-]+)", caixa[0]["texto"]).group(1)
    assert client.post("/api/auth/recuperar/verificar", json={"token": token}).json() == {
        "valido": True, "login": "fabiano.camargo"}
    assert client.post("/api/auth/recuperar/redefinir", json={"token": token, "nova_senha": "curta"}).status_code == 400
    assert client.post("/api/auth/recuperar/redefinir",
                       json={"token": token, "nova_senha": "Recuperada2026"}).status_code == 204
    assert client.post("/api/auth/recuperar/redefinir",                       # uso único
                       json={"token": token, "nova_senha": "OutraSenha2026"}).status_code == 400
    assert login(client, "fabiano.camargo", "Estoque2026ok").status_code == 401
    assert login(client, "fabiano.camargo", "Recuperada2026").status_code == 200


def test_recuperacao_expira_e_limita(client, caixa):
    from datetime import datetime, timedelta, timezone

    from app.core.db import SessionLocal
    from app.models import TokenSenha
    h = preparar_admin(client)
    _criar(client, h)
    client.post("/api/auth/recuperar", json={"identificador": "fabiano.camargo"})
    token = re.search(r"token=([\w-]+)", caixa[-1]["texto"]).group(1)
    with SessionLocal() as db:
        for t in db.query(TokenSenha).all():
            t.expira_em = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
    assert client.post("/api/auth/recuperar/verificar", json={"token": token}).json()["valido"] is False
    for _ in range(5):
        client.post("/api/auth/recuperar", json={"identificador": "fabiano.camargo"})
    assert len(caixa) == 3                                                   # máximo 3 por hora por usuário
