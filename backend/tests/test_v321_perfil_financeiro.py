"""Spec v3.21 (Eduardo, 2026-11-23, pendências item 2): perfil Financeiro (a Bruna). Grava só o R$/kg do precificador
no Cadastro de SA, consulta o resto, vê no Painel os SAs que esperam o R$/kg e recebe aviso quando o COP fecha."""
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


def _cop_fechado(client, u, ids) -> dict:
    h = entrar(client, u["itu"])
    s = client.post("/api/solicitacoes", json=corpo_solicitacao(ids["l33"]), headers=h).json()["solicitacoes"][0]
    h = entrar(client, u["rj"])
    r = client.post(f"/api/solicitacoes/{s['id']}/corte", headers=h,
                    json={"linhas": [{"lote_id": ids["l33"], "pecas": 12, "peso_real_kg": 84}]})
    assert r.status_code == 201, r.text
    cop = client.post("/api/cops", json={}, headers=h).json()
    lib = client.get("/api/cops/cortes-prontos").json()[0]["liberacao_id"]
    client.post(f"/api/cops/{cop['id']}/itens", json={"liberacao_ids": [lib]}, headers=h)
    assert client.post(f"/api/cops/{cop['id']}/fechar", headers=h).status_code == 200
    return cop


def test_financeiro_ve_pendencia_recebe_aviso_e_grava_so_o_rs_kg(amb):
    client, u, ids = amb
    cop = _cop_fechado(client, u, ids)
    h = entrar(client, u["financeiro"])

    p = client.get("/api/painel/pendencias").json()
    assert set(p["grupos"]) == {"FINANCEIRO"}
    card = p["grupos"]["FINANCEIRO"][0]
    assert card["codigo"] == "SA_SEM_PRECIFICADOR" and card["quantidade"] == 1 and card["link"] == "/sa"
    assert card["itens"][0]["cop"] == cop["numero"] and card["itens"][0]["sa_no_mega"] is False

    avisos = client.get("/api/notificacoes").json()["itens"]
    aviso = next(a for a in avisos if a["tipo"] == "SA_AGUARDANDO_PRECIFICADOR")
    assert aviso["link"] == f"/sa?cop={cop['numero']}" and "R$/kg do precificador" in aviso["texto"]

    sa = client.get("/api/sas").json()["itens"][0]
    r = client.patch(f"/api/sas/{sa['id']}", json={"rs_kg": 42.5, "ncm": "99999999", "pedido": "X1"}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["rs_kg"] == 42.5 and r.json()["ncm"] != "99999999" and r.json()["pedido"] != "X1"

    # o resto do Cadastro de SA é do Estoque Itu (e da Amanda, perfil Análise, no código)
    assert client.post(f"/api/sas/{sa['id']}/codigo/validar", json={"sa_codigo": 37983}, headers=h).status_code == 403
    assert client.post("/api/sas/preparar", json={"ids": [sa["id"]]}, headers=h).status_code == 403
    assert client.post("/api/sas/verificar", json={"ids": [sa["id"]]}, headers=h).status_code == 403
    # consulta: estoque, pedidos, COP, exportação do SA
    for url in ("/api/lotes", "/api/solicitacoes", f"/api/cops/{cop['id']}", "/api/entradas-nf",
                "/api/exportar/sas.xlsx"):
        assert client.get(url).status_code == 200, url
    # não altera nada fora do SA
    assert client.post("/api/solicitacoes/validar", json={}, headers=h).status_code == 403
    assert client.post(f"/api/lotes/{ids['l33']}/destinacoes", json={}, headers=h).status_code == 403

    p = client.get("/api/painel/pendencias").json()
    assert p["grupos"]["FINANCEIRO"][0]["quantidade"] == 0


def test_sa_da_carga_nao_entra_na_pendencia_do_financeiro(amb):
    from app.core.db import SessionLocal
    from app.models import CadastroSa
    from app.services import painel
    client, u, ids = amb
    _cop_fechado(client, u, ids)
    with SessionLocal() as db:
        db.query(CadastroSa).update({"origem": "CARGA"})
        db.commit()
        assert painel.pendencias_financeiro(db)[0]["quantidade"] == 0
