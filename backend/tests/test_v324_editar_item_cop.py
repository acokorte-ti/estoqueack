"""Spec v3.24 T11 (Eduardo, 2026-11-25): "Editar" ao lado de "Remover" no item do COP aberto. Corrige OP, peças e
peso real do corte; o peso ajusta o saldo do lote e a OP muda na solicitação."""
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


def _cop_com_corte(client, u, ids) -> tuple[dict, dict, int]:
    h = entrar(client, u["itu"])
    s = client.post("/api/solicitacoes", json=corpo_solicitacao(ids["l33"]), headers=h).json()["solicitacoes"][0]
    h = entrar(client, u["rj"])
    assert client.post(f"/api/solicitacoes/{s['id']}/corte", headers=h,
                       json={"linhas": [{"lote_id": ids["l33"], "pecas": 12, "peso_real_kg": 84}]}).status_code == 201
    cop = client.post("/api/cops", json={}, headers=h).json()
    lib = client.get("/api/cops/cortes-prontos").json()[0]["liberacao_id"]
    cop = client.post(f"/api/cops/{cop['id']}/itens", json={"liberacao_ids": [lib]}, headers=h).json()
    return cop, cop["itens"][0], s["id"]


def _gravar(client, url, corpo, h):
    """Prévia → confirma o que pedir ciência → grava."""
    p = client.post(url + "/validar", json=corpo, headers=h).json()
    conf = {o["codigo"]: "conferido" for o in p["ocorrencias"] if o["nivel"] == "CIENCIA"}
    return p, client.patch(url, json={**corpo, "confirmacoes": conf}, headers=h)


def _cod(p):
    return {o["codigo"] for o in p["ocorrencias"]}


def test_peso_ajusta_o_saldo_e_o_ajuste_nao_se_estorna_sozinho(amb):
    from app.core.db import SessionLocal
    from app.models import LiberacaoCorte, Lote, Movimento, Notificacao
    client, u, ids = amb
    cop, item, _ = _cop_com_corte(client, u, ids)
    h = entrar(client, u["rj"])
    url = f"/api/cops/{cop['id']}/itens/{item['id']}"
    p, r = _gravar(client, url, {"peso_kg": 90}, h)
    assert "AJUSTE_SALDO" in _cod(p) and "916,0 kg para 910,0 kg" in next(
        o["mensagem"] for o in p["ocorrencias"] if o["codigo"] == "AJUSTE_SALDO")
    assert r.status_code == 200, r.text
    assert r.json()["itens"][0]["peso_kg"] == 90 and r.json()["itens"][0]["pecas"] == 12
    with SessionLocal() as db:
        lote = db.get(Lote, ids["l33"])
        assert lote.saldo_kg == pytest.approx(910)
        assert sum(m.kg for m in db.query(Movimento).filter_by(lote_id=lote.id)) == pytest.approx(lote.saldo_kg)
        aj = db.query(Movimento).filter_by(lote_id=lote.id, tipo="AJUSTE_INVENTARIO").one()
        assert aj.kg == pytest.approx(-6) and aj.liberacao_id == item["liberacao_id"] and "COP" in aj.justificativa
        assert db.get(LiberacaoCorte, item["liberacao_id"]).peso_real_kg == pytest.approx(90)
        assert db.query(Notificacao).filter_by(tipo="CORTE_CORRIGIDO").count() >= 1
    extrato = client.get(f"/api/lotes/{ids['l33']}/movimentos").json()["itens"]
    assert not next(m for m in extrato if m["id"] == aj.id)["estornavel"]
    h = entrar(client, u["admin"])
    r = client.post(f"/api/movimentos/{aj.id}/estorno", json={"justificativa": "teste"}, headers=h)
    assert r.status_code == 400 and "edite o item no COP" in r.json()["detail"]


def test_menos_pecas_volta_a_solicitacao_para_parcial(amb):
    client, u, ids = amb
    cop, item, sol_id = _cop_com_corte(client, u, ids)
    h = entrar(client, u["rj"])
    url = f"/api/cops/{cop['id']}/itens/{item['id']}"
    p, r = _gravar(client, url, {"pecas": 10, "peso_kg": 70}, h)
    assert "SOLICITACAO_PARCIAL" in _cod(p)
    assert r.status_code == 200, r.text
    assert client.get(f"/api/solicitacoes/{sol_id}").json()["situacao"] == "CORTADA_PARCIAL"


def test_troca_a_op_na_solicitacao(amb):
    client, u, ids = amb
    cop, item, sol_id = _cop_com_corte(client, u, ids)
    h = entrar(client, u["rj"])
    url = f"/api/cops/{cop['id']}/itens/{item['id']}"
    p, r = _gravar(client, url, {"op": 100092}, h)
    assert "OP_TROCADA" in _cod(p) and "AJUSTE_SALDO" not in _cod(p)
    assert r.status_code == 200, r.text
    novo = r.json()["itens"][0]
    assert (novo["op"], novo["cliente"], novo["peso_kg"]) == (100092, "CLIENTE Y", 84)
    assert client.get(f"/api/solicitacoes/{sol_id}").json()["op"] == 100092
    # OP que não existe no Mega bloqueia
    assert "OP_INEXISTENTE" in _cod(client.post(url + "/validar", json={"op": 999999}, headers=h).json())


def test_bloqueios_e_perfis(amb):
    client, u, ids = amb
    cop, item, _ = _cop_com_corte(client, u, ids)
    url = f"/api/cops/{cop['id']}/itens/{item['id']}"
    for perfil in ("itu", "analise", "financeiro"):
        h = entrar(client, u[perfil])
        assert client.patch(url, json={"pecas": 11}, headers=h).status_code == 403, perfil
    h = entrar(client, u["rj"])
    assert _cod(client.post(url + "/validar", json={"pecas": 12, "peso_kg": 84}, headers=h).json()) == {"SEM_MUDANCA"}
    r = client.patch(url, json={"peso_kg": 5000}, headers=h)
    assert r.status_code == 409 and "SALDO_INSUFICIENTE" in _cod(r.json())
    assert client.post(f"/api/cops/{cop['id']}/fechar", headers=h).status_code == 200
    r = client.patch(url, json={"pecas": 11}, headers=h)
    assert r.status_code == 400 and "COP aberto" in r.json()["detail"]
    h = entrar(client, u["admin"])
    assert client.patch(f"/api/cops/{cop['id']}/itens/999999", json={"pecas": 1}, headers=h).status_code in (400, 404)
