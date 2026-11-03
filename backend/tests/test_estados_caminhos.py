"""Parte C1: estados derivados da solicitação nos casos de borda (§3.1).

- lote dividido entre dois cortes: vale o estágio MENOS avançado;
- estorno do corte antes do COP: volta para Enviada e o saldo do lote volta;
- trocar a OP depois do SA confirmado: permitido, com aviso "ajuste o SA no Mega".
"""
from datetime import date

import pytest

from tests.fluxo_util import catalogo_e_lotes, corpo_solicitacao, criar_usuarios, entrar, mega_falso

pytest.importorskip("fastapi")


@pytest.fixture()
def amb(client):
    u = criar_usuarios(client)
    ids = catalogo_e_lotes()
    fab = mega_falso()
    yield client, u, ids, fab
    fab.definir(None)


def _sol(client, u, ids):
    h = entrar(client, u["itu"])
    return client.post("/api/solicitacoes", json=corpo_solicitacao(ids["l33"]), headers=h).json()["solicitacoes"][0]


def _situacao(client, u, sid):
    entrar(client, u["itu"])
    return client.get(f"/api/solicitacoes/{sid}").json()["situacao"]


def test_lote_dividido_vale_o_estagio_menos_avancado(amb):
    from app.integrations.mega.gateway import SituacaoSa
    client, u, ids, fab = amb
    s = _sol(client, u, ids)
    h = entrar(client, u["rj"])
    corte = {"linhas": [{"lote_id": ids["l33"], "pecas": 8, "peso_real_kg": 55},
                        {"lote_id": ids["l33b"], "pecas": 4, "peso_real_kg": 27.6}],
             "confirmacoes": {"LOTE_TROCADO#2": "Completei com outro contêiner"}}
    assert client.post(f"/api/solicitacoes/{s['id']}/corte", json=corte, headers=h).status_code == 201
    prontos = client.get("/api/cops/cortes-prontos").json()
    assert len(prontos) == 2
    cop = client.post("/api/cops", json={"numero": 801}, headers=h).json()
    client.post(f"/api/cops/{cop['id']}/itens", json={"liberacao_ids": [prontos[0]["liberacao_id"]]}, headers=h)
    client.post(f"/api/cops/{cop['id']}/fechar", headers=h)
    # um corte no COP fechado, o outro ainda fora de COP → Cortada (o menos avançado)
    assert _situacao(client, u, s["id"]) == "CORTADA"
    # o segundo corte entra noutro COP e os dois SAs são confirmados → SA pronto
    h = entrar(client, u["rj"])
    cop2 = client.post("/api/cops", json={"numero": 802}, headers=h).json()
    client.post(f"/api/cops/{cop2['id']}/itens", json={"liberacao_ids": [prontos[1]["liberacao_id"]]}, headers=h)
    client.post(f"/api/cops/{cop2['id']}/fechar", headers=h)
    assert _situacao(client, u, s["id"]) == "EM_COP"
    fab.obter().situacoes_sa[50001] = SituacaoSa(50001, True, "SA PECA", True, date.today(), 12)
    h = entrar(client, u["itu"])
    for sa in client.get("/api/sas").json()["itens"]:
        client.post(f"/api/sas/{sa['id']}/codigo", json={"sa_codigo": 50001,
                                                        "confirmacoes": {"SA_CODIGO_TROCADO": "Mesmo SA da OP"}},
                    headers=h)
    assert _situacao(client, u, s["id"]) == "SA_PRONTO"


def test_estorno_do_corte_antes_do_cop_volta_para_enviada(amb):
    client, u, ids, _ = amb
    s = _sol(client, u, ids)
    h = entrar(client, u["rj"])
    corte = {"linhas": [{"lote_id": ids["l33"], "pecas": 12, "peso_real_kg": 85}],
             "confirmacoes": {"EXCESSO_TOLERANCIA": "Desvio de serra na barra"}}
    assert client.post(f"/api/solicitacoes/{s['id']}/corte", json=corte, headers=h).status_code == 201
    mov = [m for m in client.get(f"/api/lotes/{ids['l33']}/movimentos").json()["itens"]
           if m["tipo"] == "SAIDA_CORTE_RJ"][-1]
    r = client.post(f"/api/movimentos/{mov['id']}/estorno", json={"justificativa": "Peso digitado errado"}, headers=h)
    assert r.status_code in (200, 201), r.text
    assert _situacao(client, u, s["id"]) == "ENVIADA"
    lote = client.get(f"/api/lotes/{ids['l33']}").json()
    assert lote["saldo_kg"] == pytest.approx(1000)
    # o estorno não apaga nada: o corte e o estorno continuam no extrato
    tipos = [m["tipo"] for m in client.get(f"/api/lotes/{ids['l33']}/movimentos").json()["itens"]]
    assert tipos.count("SAIDA_CORTE_RJ") == 1 and tipos.count("ESTORNO") == 1


def test_trocar_op_depois_do_sa_confirmado_avisa(amb):
    from app.integrations.mega.gateway import OrdemProducao, SituacaoSa
    client, u, ids, fab = amb
    fab.obter()._ops[100777] = OrdemProducao(100777, 777, "PECA 30X100X250MM", "CLIENTE X", "AB", date.today(), 12)
    s = _sol(client, u, ids)
    h = entrar(client, u["rj"])
    client.post(f"/api/solicitacoes/{s['id']}/corte", headers=h, json={
        "linhas": [{"lote_id": ids["l33"], "pecas": 12, "peso_real_kg": 85}],
        "confirmacoes": {"EXCESSO_TOLERANCIA": "Desvio de serra na barra"}})
    lib = client.get("/api/cops/cortes-prontos").json()[0]["liberacao_id"]
    cop = client.post("/api/cops", json={"numero": 803}, headers=h).json()
    client.post(f"/api/cops/{cop['id']}/itens", json={"liberacao_ids": [lib]}, headers=h)
    client.post(f"/api/cops/{cop['id']}/fechar", headers=h)
    fab.obter().situacoes_sa[50001] = SituacaoSa(50001, True, "SA PECA", True, date.today(), 12)
    h = entrar(client, u["itu"])
    sa = client.get("/api/sas").json()["itens"][0]
    client.post(f"/api/sas/{sa['id']}/codigo", json={"sa_codigo": 50001}, headers=h)
    r = client.post(f"/api/solicitacoes/{s['id']}/trocar-op",
                    json={"op": 100777, "justificativa": "OP original cancelada pelo cliente"}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["op"] == 100777 and any("ajuste o SA no Mega" in a for a in r.json()["avisos"])
