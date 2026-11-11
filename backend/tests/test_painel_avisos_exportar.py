"""T03 pendências, T16 conciliação mínima, avisos automáticos do sino e exportações Excel."""
import io
from datetime import datetime, timedelta, timezone

import pytest

from tests.fluxo_util import catalogo_e_lotes, corpo_solicitacao, criar_usuarios, entrar, mega_falso

pytest.importorskip("fastapi")


@pytest.fixture()
def amb(client):
    u = criar_usuarios(client)
    ids = catalogo_e_lotes()
    fab = mega_falso()
    yield client, u, ids
    fab.definir(None)


def _cop_fechado(client, u, ids):
    h = entrar(client, u["itu"])
    corpo = corpo_solicitacao(ids["l33"], confirmacoes={"OP_DUPLICADA": "Segunda remessa da mesma OP"})
    s = client.post("/api/solicitacoes", json=corpo, headers=h).json()["solicitacoes"][0]
    h = entrar(client, u["rj"])
    client.post(f"/api/solicitacoes/{s['id']}/corte", headers=h,
                json={"linhas": [{"lote_id": ids["l33"], "pecas": 12, "peso_real_kg": 84}]})
    cop = client.post("/api/cops", json={}, headers=h).json()
    lib = client.get("/api/cops/cortes-prontos").json()[0]["liberacao_id"]
    client.post(f"/api/cops/{cop['id']}/itens", json={"liberacao_ids": [lib]}, headers=h)
    client.post(f"/api/cops/{cop['id']}/fechar", headers=h)
    return s["id"], cop["id"]


def _grupo(resp, perfil, codigo):
    return next(p for p in resp["grupos"][perfil] if p["codigo"] == codigo)


def test_pendencias_por_perfil(amb):
    client, u, ids = amb
    h = entrar(client, u["itu"])
    s = client.post("/api/solicitacoes", json=corpo_solicitacao(ids["l33b"]), headers=h).json()["solicitacoes"][0]
    _cop_fechado(client, u, ids)
    entrar(client, u["itu"])
    r = client.get("/api/painel/pendencias").json()
    assert set(r["grupos"]) == {"ESTOQUE"}
    assert _grupo(r, "ESTOQUE", "SA_SEGURANDO_COP")["quantidade"] == 1
    assert r["atrasos"]["NORMAL"] == 1 and r["divergencias_mega"]["limite_kg"] == 5
    entrar(client, u["rj"])
    r = client.get("/api/painel/pendencias").json()
    assert set(r["grupos"]) == {"OPERACAO_RJ"}
    assert [x["id"] for x in _grupo(r, "OPERACAO_RJ", "FILA_CORTE")["itens"]] == [s["id"]]
    assert _grupo(r, "OPERACAO_RJ", "COP_AGUARDANDO_SA")["quantidade"] == 1
    assert r["divergencias_mega"]["quantidade"] is None
    entrar(client, u["analise"])
    r = client.get("/api/painel/pendencias").json()
    assert set(r["grupos"]) == {"ANALISE"}
    entrar(client, u["admin"])
    assert set(client.get("/api/painel/pendencias").json()["grupos"]) == {"ESTOQUE", "OPERACAO_RJ", "ANALISE"}


def test_conciliacao_minima(amb):
    from app.core.db import SessionLocal
    from app.models import MegaSaldo
    client, u, ids = amb
    with SessionLocal() as db:
        db.add(MegaSaldo(codigo=78290, saldo_kg=5210.0, descricao="IMP-H13 24X62MM"))
        db.commit()
    entrar(client, u["rj"])
    assert client.get("/api/conciliacao").status_code == 403
    entrar(client, u["analise"])
    r = client.get("/api/conciliacao").json()
    it = next(x for x in r["itens"] if x["codigo"] == 78290)
    assert it["saldo_mega_kg"] == 5210 and it["soma_lotes_kg"] == 5198 and it["diferenca_kg"] == 12
    assert it["status"] == "MEGA_MAIOR" and r["totais"]["mega_maior"] == 1
    assert len(client.get("/api/conciliacao", params={"somente_divergentes": True}).json()["itens"]) == 1


def test_avisos_automaticos_sem_repetir(amb):
    from app.core.db import SessionLocal
    from app.models import CadastroSa, Destinacao, Notificacao, SolicitacaoCorte
    from app.services import avisos
    client, u, ids = amb
    _, _ = _cop_fechado(client, u, ids)
    h = entrar(client, u["itu"])
    corpo = corpo_solicitacao(ids["l33b"], confirmacoes={"OP_DUPLICADA": "Segunda remessa da mesma OP"})
    s2 = client.post("/api/solicitacoes", json=corpo, headers=h).json()["solicitacoes"][0]
    with SessionLocal() as db:
        velho = datetime.now(timezone.utc) - timedelta(days=20)
        db.get(SolicitacaoCorte, s2["id"]).enviada_em = velho
        for sa in db.query(CadastroSa):
            sa.criado_em = velho
        db.add(Destinacao(lote_id=ids["l70"], tipo="RESERVA", descricao="Reservado CPR", kg=100,
                          validade=(datetime.now().date() + timedelta(days=3))))
        db.commit()
        n1 = avisos.rodar(db)
        n2 = avisos.rodar(db)
        tipos = [n.tipo for n in db.query(Notificacao)]
    assert n1["sa_48h"] == 1 and n1["atrasadas"] == 1 and n1["reservas"] == 1
    assert n2 == {"sa_48h": 0, "atrasadas": 0, "reservas": 0, "resumo_excecoes": n2["resumo_excecoes"]}
    assert "SA_SEM_CONFIRMACAO" in tipos and "SOLICITACAO_ATRASADA" in tipos and "RESERVA_VENCENDO" in tipos


def test_exportacoes_excel(amb):
    import openpyxl
    client, u, ids = amb
    _cop_fechado(client, u, ids)
    entrar(client, u["itu"])
    for url, cab0 in (("/api/exportar/lotes.xlsx", "Lote"), ("/api/exportar/lotes-agrupado.xlsx", "Liga × bitola"),
                      ("/api/exportar/solicitacoes.xlsx", "Nº"), ("/api/exportar/sas.xlsx", "DATA")):
        r = client.get(url)
        assert r.status_code == 200, url
        assert r.headers["content-type"].startswith("application/vnd.openxmlformats")
        ws = openpyxl.load_workbook(io.BytesIO(r.content)).active
        assert ws["A1"].value == cab0 and ws.max_row >= 2, url
    entrar(client, u["rj"])
    ws = openpyxl.load_workbook(io.BytesIO(client.get("/api/exportar/lotes.xlsx").content)).active
    assert {ws.cell(r, 2).value for r in range(2, ws.max_row + 1)} == {"RJ no Rio"}
