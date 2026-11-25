"""Spec v3.23 T11 (Eduardo, 2026-11-25): "Excluir COP", por quem abriu o COP ou pelo Admin, enquanto o COP não foi
enviado e nenhum SA dele está confirmado; os cortes voltam para "cortes prontos"."""
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


def _cop_com_corte(client, u, ids, *, fechar: bool) -> tuple[dict, int]:
    h = entrar(client, u["itu"])
    s = client.post("/api/solicitacoes", json=corpo_solicitacao(ids["l33"]), headers=h).json()["solicitacoes"][0]
    h = entrar(client, u["rj"])
    assert client.post(f"/api/solicitacoes/{s['id']}/corte", headers=h,
                       json={"linhas": [{"lote_id": ids["l33"], "pecas": 12, "peso_real_kg": 84}]}).status_code == 201
    cop = client.post("/api/cops", json={}, headers=h).json()
    lib = client.get("/api/cops/cortes-prontos").json()[0]["liberacao_id"]
    client.post(f"/api/cops/{cop['id']}/itens", json={"liberacao_ids": [lib]}, headers=h)
    if fechar:
        assert client.post(f"/api/cops/{cop['id']}/fechar", headers=h).status_code == 200
    return cop, s["id"]


def test_quem_abriu_exclui_cop_fechado_e_o_corte_volta(amb):
    from app.core.db import SessionLocal
    from app.models import Auditoria, CadastroSa, Cop, Movimento, Notificacao
    client, u, ids = amb
    cop, sol_id = _cop_com_corte(client, u, ids, fechar=True)
    h = entrar(client, u["rj"])
    d = client.get(f"/api/cops/{cop['id']}").json()
    assert d["criado_por_id"] is not None and d["criado_por"]
    with SessionLocal() as db:
        movs = db.query(Movimento).count()
        assert db.query(CadastroSa).filter(CadastroSa.cop_item_id.is_not(None)).count() == 1
    r = client.post(f"/api/cops/{cop['id']}/excluir", json={"motivo": "COP aberto em duplicidade"}, headers=h)
    assert r.status_code == 204, r.text
    assert client.get(f"/api/cops/{cop['id']}").status_code == 404
    assert [x["solicitacao_id"] for x in client.get("/api/cops/cortes-prontos").json()] == [sol_id]
    assert client.get(f"/api/solicitacoes/{sol_id}").json()["situacao"] == "CORTADA"
    with SessionLocal() as db:
        assert db.get(Cop, cop["id"]) is None
        assert db.query(CadastroSa).filter(CadastroSa.cop_item_id.is_not(None)).count() == 0
        assert db.query(Movimento).count() == movs                       # não mexe em saldo
        assert db.query(Auditoria).filter_by(acao="COP_EXCLUIDO").count() == 1
        assert db.query(Notificacao).filter_by(tipo="COP_EXCLUIDO").count() >= 1
    # o número fica livre e o corte entra em outro COP
    novo = client.post("/api/cops", json={"numero": cop["numero"]}, headers=h)
    assert novo.status_code == 201, novo.text


def test_so_quem_abriu_ou_admin(amb):
    client, u, ids = amb
    cop, _ = _cop_com_corte(client, u, ids, fechar=False)
    for perfil in ("itu", "analise", "financeiro"):
        h = entrar(client, u[perfil])
        assert client.post(f"/api/cops/{cop['id']}/excluir", json={}, headers=h).status_code == 403, perfil
    h = entrar(client, u["admin"])
    assert client.post(f"/api/cops/{cop['id']}/excluir", headers=h).status_code == 204


def test_nao_exclui_com_sa_confirmado(amb):
    from app.core.db import SessionLocal
    from app.models import CadastroSa
    client, u, ids = amb
    cop, _ = _cop_com_corte(client, u, ids, fechar=True)
    with SessionLocal() as db:
        db.query(CadastroSa).filter(CadastroSa.cop_item_id.is_not(None)).update({"situacao": "CONFIRMADO"})
        db.commit()
    h = entrar(client, u["rj"])
    r = client.post(f"/api/cops/{cop['id']}/excluir", json={}, headers=h)
    assert r.status_code == 400 and "SA confirmado" in r.json()["detail"]
