"""Configuração dos testes de API (precisam das dependências de requirements-dev.txt).

Os testes de domínio (test_dominio_*.py) rodam só com a biblioteca padrão.
"""
import os
import tempfile

import pytest

_TMP = tempfile.mkdtemp()
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TMP}/teste.db")
os.environ["APP_ENV"] = "test"
os.environ["ADMIN_LOGIN"] = "admin"
os.environ["ADMIN_SENHA_INICIAL"] = "SenhaInicial123"
os.environ["LOGIN_MAX_TENTATIVAS"] = "3"


@pytest.fixture()
def client():
    fastapi = pytest.importorskip("fastapi")  # noqa: F841
    from fastapi.testclient import TestClient

    from app import models  # noqa: F401
    from app.core.db import Base, engine
    from app.main import app

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestClient(app) as c:
        yield c


def login(client, usuario="admin", senha="SenhaInicial123"):
    r = client.post("/api/auth/login", json={"login": usuario, "senha": senha})
    return r


def preparar_admin(client) -> dict:
    """Faz login do admin, troca a senha temporária e devolve headers com CSRF."""
    r = login(client)
    assert r.status_code == 200, r.text
    h = {"X-CSRF-Token": r.json()["csrf"]}
    r = client.post("/api/auth/trocar-senha", json={"senha_atual": "SenhaInicial123", "nova_senha": "NovaSenha2026x"},
                    headers=h)
    assert r.status_code == 204, r.text
    return h
