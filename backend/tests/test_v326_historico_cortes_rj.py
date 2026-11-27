"""Spec v3.26 T28 (Eduardo, 2026-11-27): aba do Admin com o histórico de cortes do RJ (sistema e planilha), com o log de
cada corte (movimentos ligados a ele e correções no COP)."""
import pytest

from tests.fluxo_util import catalogo_e_lotes, corpo_solicitacao, criar_usuarios, entrar, mega_falso

pytest.importorskip("fastapi")
URL = "/api/admin/cortes-rj"


@pytest.fixture()
def amb(client):
    u = criar_usuarios(client)
    ids = catalogo_e_lotes()
    fab = mega_falso()
    yield client, u, ids
    fab.definir(None)


def _corte(client, u, ids, *, lote="l33", pecas=12, peso=84):
    h = entrar(client, u["itu"])
    s = client.post("/api/solicitacoes", json=corpo_solicitacao(ids[lote]), headers=h).json()["solicitacoes"][0]
    h = entrar(client, u["rj"])
    r = client.post(f"/api/solicitacoes/{s['id']}/corte", headers=h,
                    json={"linhas": [{"lote_id": ids[lote], "pecas": pecas, "peso_real_kg": peso}],
                          "confirmacoes": {"OP_DUPLICADA": "nova OP"}})
    assert r.status_code == 201, r.text
    return s["id"]


def test_so_admin(amb):
    client, u, _ = amb
    for perfil in ("itu", "rj", "analise", "financeiro"):
        entrar(client, u[perfil])
        assert client.get(URL).status_code == 403, perfil
        assert client.get(URL + ".xlsx").status_code == 403, perfil


def test_lista_corte_do_sistema_e_da_planilha(amb):
    from app.core.db import SessionLocal
    from app.models import LiberacaoCorte
    client, u, ids = amb
    _corte(client, u, ids)
    with SessionLocal() as db:           # corte "da planilha": mesmo registro, com a referência da carga
        lib = db.query(LiberacaoCorte).one()
        copia = LiberacaoCorte(solicitacao_id=lib.solicitacao_id, lote_id=lib.lote_id, pecas=1, peso_real_kg=7,
                               data_corte=lib.data_corte, origem_ref={"arquivo": "CONTROLE.xlsx", "aba": "RJ",
                                                                      "linha": 12})
        db.add(copia)
        db.commit()
    entrar(client, u["admin"])
    r = client.get(URL).json()
    assert r["total"] == 2 and r["totais"]["cortes"] == 2 and r["totais"]["peso_real_kg"] == pytest.approx(91)
    assert {x["origem"] for x in r["itens"]} == {"SISTEMA", "PLANILHA"}
    x = next(x for x in r["itens"] if x["origem"] == "SISTEMA")
    assert x["op"] == 100592 and x["registrado_por"] and x["situacao"] == "CORTE_PRONTO" and x["peso_real_kg"] == 84
    assert x["previsto_kg"] and x["diferenca_pct"] is not None
    assert client.get(URL, params={"origem": "PLANILHA"}).json()["total"] == 1
    assert client.get(URL, params={"busca": "ch33k"}).json()["total"] == 2
    assert client.get(URL, params={"busca": "naoexiste"}).json()["total"] == 0
    assert client.get(URL, params={"op": 100592}).json()["total"] == 2
    assert client.get(URL, params={"de": "2000-01-01", "ate": "2000-01-31"}).json()["total"] == 0
    d = client.get(f"{URL}/{x['id']}").json()
    assert [m["tipo"] for m in d["movimentos"]] == ["SAIDA_CORTE_RJ"] and d["movimentos"][0]["kg"] == -84
    assert client.get(URL + ".xlsx").headers["content-type"].startswith("application/vnd.openxml")


def test_log_mostra_correcao_no_cop_e_estorno(amb):
    from app.core.db import SessionLocal
    from app.models import Movimento
    client, u, ids = amb
    _corte(client, u, ids)
    h = entrar(client, u["rj"])
    cop = client.post("/api/cops", json={}, headers=h).json()
    lib = client.get("/api/cops/cortes-prontos").json()[0]["liberacao_id"]
    item = client.post(f"/api/cops/{cop['id']}/itens", json={"liberacao_ids": [lib]}, headers=h).json()["itens"][0]
    corpo = {"peso_kg": 90, "motivo": "balança", "confirmacoes": {"EXCESSO_TOLERANCIA": "conferido"}}
    r = client.patch(f"/api/cops/{cop['id']}/itens/{item['id']}", json=corpo, headers=h)
    assert r.status_code == 200, r.text
    entrar(client, u["admin"])
    x = client.get(URL).json()["itens"][0]
    assert x["situacao"] == "EM_COP" and x["cop"] == cop["numero"] and x["corrigido"] and x["peso_real_kg"] == 90
    d = client.get(f"{URL}/{x['id']}").json()
    assert [m["tipo"] for m in d["movimentos"]] == ["SAIDA_CORTE_RJ", "AJUSTE_INVENTARIO"]
    assert d["correcoes"][0]["antes"]["peso_kg"] == 84 and d["correcoes"][0]["motivo"] == "balança"
    # tira do COP e estorna: o corte continua no histórico, marcado como estornado e fora dos totais
    h = entrar(client, u["rj"])
    client.delete(f"/api/cops/{cop['id']}/itens/{item['id']}", headers=h)
    with SessionLocal() as db:
        mov = db.query(Movimento).filter_by(tipo="SAIDA_CORTE_RJ").one().id
    assert client.post(f"/api/movimentos/{mov}/estorno", json={"justificativa": "lançado errado"},
                       headers=h).status_code == 201
    entrar(client, u["admin"])
    r = client.get(URL).json()
    assert r["itens"][0]["estornado"] and r["itens"][0]["situacao"] == "ESTORNADO" and r["totais"]["cortes"] == 0
    assert client.get(URL, params={"estornados": False}).json()["total"] == 0
    assert "ESTORNO" in [m["tipo"] for m in client.get(f"{URL}/{x['id']}").json()["movimentos"]]
