"""Configuração dos testes de API (precisam das dependências de requirements-dev.txt).

Os testes de domínio (test_dominio_*.py) rodam só com a biblioteca padrão.

Banco dos testes:
- padrão: SQLite temporário, tabelas criadas pelos models (rápido, sem trigger nem trava de linha);
- com `TEST_DATABASE_URL=postgresql+psycopg://…` (CI e Parte B): PostgreSQL de verdade. O esquema é recriado
  **pelas migrações** (trigger de imutabilidade incluso) uma vez por sessão e cada teste começa com as tabelas
  vazias (TRUNCATE, que não dispara os triggers de linha). ATENÇÃO: o banco indicado é apagado.
"""
import os
import tempfile
from pathlib import Path

import pytest

_TMP = tempfile.mkdtemp()
if os.environ.get("TEST_DATABASE_URL"):
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TMP}/teste.db")
os.environ["APP_ENV"] = "test"
os.environ["ADMIN_LOGIN"] = "admin"
os.environ["ADMIN_SENHA_INICIAL"] = "SenhaInicial123"
os.environ["LOGIN_MAX_TENTATIVAS"] = "3"

PG = os.environ["DATABASE_URL"].startswith("postgresql")
BACKEND = Path(__file__).resolve().parents[1]


def pytest_report_header(config):
    return f"banco dos testes: {'PostgreSQL (migrações)' if PG else 'SQLite (models)'}"


@pytest.fixture(scope="session")
def esquema_pg():
    """Recria o esquema do zero pelas migrações (upgrade head). Só no PostgreSQL."""
    if not PG:
        pytest.skip("só no PostgreSQL (defina TEST_DATABASE_URL)")
    from alembic import command
    from alembic.config import Config as AlembicConfig
    from sqlalchemy import text

    from app.core.db import engine
    with engine.begin() as c:
        c.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        c.execute(text("CREATE SCHEMA public"))
    cfg = AlembicConfig(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    command.upgrade(cfg, "head")
    return cfg


def limpar_pg():
    from sqlalchemy import text

    from app import models  # noqa: F401
    from app.core.db import Base, engine
    tabelas = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    with engine.begin() as c:
        c.execute(text(f"TRUNCATE {tabelas} RESTART IDENTITY CASCADE"))


@pytest.fixture()
def client(request):
    fastapi = pytest.importorskip("fastapi")  # noqa: F841
    from fastapi.testclient import TestClient

    from app import models  # noqa: F401
    from app.core.db import Base, engine
    from app.main import app

    if PG:
        request.getfixturevalue("esquema_pg")
        limpar_pg()
    else:
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
