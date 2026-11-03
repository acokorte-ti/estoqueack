"""Parte B (chat BANCO E TESTES): o que só existe no PostgreSQL de verdade.

- os models batem com as migrações (nada criado só por um dos dois);
- `movimento` e `auditoria` são somente-inclusão (trigger);
- dois cortes ao mesmo tempo no mesmo lote não deixam o saldo negativo nem perdem atualização (SELECT … FOR UPDATE).

Rodam só com TEST_DATABASE_URL apontando para um PostgreSQL (CI e scripts/testes_pg.sh); no SQLite são pulados.
"""
import threading
import time

import pytest
from sqlalchemy import text

from tests.conftest import PG
from tests.fluxo_util import catalogo_e_lotes, corpo_solicitacao, criar_usuarios, entrar, mega_falso

pytestmark = pytest.mark.skipif(not PG, reason="só no PostgreSQL (defina TEST_DATABASE_URL)")


def test_models_iguais_as_migracoes(esquema_pg):
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    from app import models  # noqa: F401
    from app.core.db import Base, engine
    with engine.connect() as c:
        ctx = MigrationContext.configure(c, opts={"compare_type": True})
        diff = compare_metadata(ctx, Base.metadata)
    # diferenças de tipo JSON×JSONB e de servidor-default não importam; o resto é erro de esquema
    relevantes = [d for d in diff if not (isinstance(d, list) and d and d[0][0] == "modify_type"
                                          and "JSON" in str(d[0][-1]).upper())]
    assert relevantes == [], relevantes


@pytest.mark.parametrize("tabela", ["movimento", "auditoria"])
def test_trigger_bloqueia_update_e_delete(client, tabela):
    from sqlalchemy.exc import DBAPIError

    from app.core.db import engine
    criar_usuarios(client)      # gera auditoria
    if tabela == "movimento":
        catalogo_e_lotes()      # gera movimentos SALDO_INICIAL
    with engine.connect() as c:
        assert c.execute(text(f"SELECT count(*) FROM {tabela}")).scalar() > 0
    for sql in (f"UPDATE {tabela} SET id = id", f"DELETE FROM {tabela}"):
        with engine.connect() as c, pytest.raises(DBAPIError, match="somente-inclus"):
            c.execute(text(sql))
    with engine.connect() as c:          # nada mudou
        assert c.execute(text(f"SELECT count(*) FROM {tabela}")).scalar() > 0


def _segura_transacao(monkeypatch, segundos: float):
    """Depois de gravar o movimento, a 1ª chamada espera `segundos` ainda dentro da transação (trava aberta)."""
    from app.services import movimentos
    original = movimentos.lancar
    chamadas = {"n": 0}

    def lancar_lento(*a, **k):
        m = original(*a, **k)
        chamadas["n"] += 1
        if chamadas["n"] == 1:
            time.sleep(segundos)
        return m
    monkeypatch.setattr(movimentos, "lancar", lancar_lento)


def test_dois_cortes_simultaneos_no_mesmo_lote(client, monkeypatch):
    """Lote de 1.000 kg; dois cortes de 600 kg em solicitações diferentes, ao mesmo tempo. Só um pode passar."""
    from fastapi.testclient import TestClient

    from app.main import app
    u = criar_usuarios(client)
    ids = catalogo_e_lotes()
    fab = mega_falso()
    try:
        h = entrar(client, u["itu"])
        sols = []
        for _ in range(2):
            r = client.post("/api/solicitacoes", json=corpo_solicitacao(ids["l33"], confirmacoes={
                "OP_DUPLICADA": "Segunda solicitação de teste"}), headers=h)
            assert r.status_code == 201, r.text
            sols.append(r.json()["solicitacoes"][0]["id"])

        _segura_transacao(monkeypatch, 1.5)
        corpo = {"linhas": [{"lote_id": ids["l33"], "pecas": 12, "peso_real_kg": 600}],
                 "confirmacoes": {"EXCESSO_TOLERANCIA": "Teste de concorrência no lote",
                                  "PECAS_ACIMA_SOLICITADO": "Teste de concorrência no lote"}}
        resultados: dict[int, int] = {}

        def cortar(sid: int, atraso: float):
            time.sleep(atraso)
            with TestClient(app) as c:
                hh = entrar(c, u["rj"])
                resultados[sid] = c.post(f"/api/solicitacoes/{sid}/corte", json=corpo, headers=hh).status_code

        t1 = threading.Thread(target=cortar, args=(sols[0], 0))
        t2 = threading.Thread(target=cortar, args=(sols[1], 0.5))   # começa enquanto o 1º segura a trava
        t1.start(), t2.start()
        t1.join(30), t2.join(30)

        assert sorted(resultados.values()) in ([201, 400], [201, 409]), resultados
        from app.core.db import engine
        with engine.connect() as c:
            saldo = float(c.execute(text("SELECT saldo_kg FROM lote WHERE id = :i"), {"i": ids["l33"]}).scalar())
            soma = float(c.execute(text("SELECT sum(kg) FROM movimento WHERE lote_id = :i"),
                                   {"i": ids["l33"]}).scalar())
        assert saldo == pytest.approx(400) and soma == pytest.approx(saldo)   # nada negativo, nada perdido
    finally:
        fab.definir(None)
