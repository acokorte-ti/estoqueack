"""Spec v3.16 (Eduardo, 2026-11-18, teste manual): a NF do COP só libera com o SA confirmado e o R$/kg do
precificador em todos os itens; o precificador aparece no item do COP; a T14 filtra por COP."""
from datetime import date

import pytest

from tests.fluxo_util import catalogo_e_lotes, corpo_solicitacao, criar_usuarios, entrar, mega_falso

pytest.importorskip("fastapi")


def _falta(r) -> str:
    """Parte variável da mensagem da NF bloqueada (depois de "Falta"), spec v3.16."""
    return r.json()["detail"].split("Falta")[-1]


@pytest.fixture()
def amb(client):
    u = criar_usuarios(client)
    ids = catalogo_e_lotes()
    fab = mega_falso()
    yield client, u, ids, fab
    fab.definir(None)


def _cop_fechado(client, u, ids, numero=801):
    """Corte de 12 peças / 85 kg no RJ, COP fechado; devolve (cop_id, sa) com o SA pendente."""
    h = entrar(client, u["itu"])
    s = client.post("/api/solicitacoes", json=corpo_solicitacao(ids["l33"]), headers=h).json()["solicitacoes"][0]
    h = entrar(client, u["rj"])
    r = client.post(f"/api/solicitacoes/{s['id']}/corte", headers=h,
                    json={"linhas": [{"lote_id": ids["l33"], "pecas": 12, "peso_real_kg": 85}],
                          "confirmacoes": {"EXCESSO_TOLERANCIA": "Desvio de serra"}})
    assert r.status_code == 201, r.text
    lib = client.get("/api/cops/cortes-prontos").json()[0]["liberacao_id"]
    cop = client.post("/api/cops", json={"numero": numero}, headers=h).json()
    client.post(f"/api/cops/{cop['id']}/itens", json={"liberacao_ids": [lib]}, headers=h)
    client.post(f"/api/cops/{cop['id']}/fechar", headers=h)
    h = entrar(client, u["itu"])
    return cop["id"], client.get("/api/sas", params={"cop": numero}).json()["itens"][0]


def _confirmar(client, fab, h, sa, codigo=50101):
    from app.integrations.mega.gateway import SituacaoSa
    fab.obter().situacoes_sa[codigo] = SituacaoSa(codigo, True, "SA PECA - CÓD.777", True, date.today(), 82.0)
    v = client.post(f"/api/sas/{sa['id']}/codigo/validar", json={"sa_codigo": codigo}, headers=h).json()
    conf = {o["codigo"]: "Teste" for o in v["ocorrencias"]}
    client.post(f"/api/sas/{sa['id']}/codigo", json={"sa_codigo": codigo, "confirmacoes": conf}, headers=h)
    assert client.get(f"/api/sas/{sa['id']}").json()["situacao"] == "CONFIRMADO"


NF = {"numero": "556", "emitente": "FIO_CERTO"}


def test_nf_do_cop_espera_sa_confirmado_e_precificador(amb):
    client, u, ids, fab = amb
    cop_id, sa = _cop_fechado(client, u, ids)

    # sem SA e sem R$/kg: a NF é recusada com as duas faltas
    h = entrar(client, u["rj"])
    r = client.post(f"/api/cops/{cop_id}/nf", json=NF, headers=h)
    assert r.status_code == 400
    assert "SA confirmado em 1 item(ns)" in _falta(r) and "R$/kg do precificador em 1" in _falta(r)

    # SA confirmado, ainda sem R$/kg: o COP não chega a "Aguardando NF" e o RJ não é avisado
    h = entrar(client, u["itu"])
    _confirmar(client, fab, h, sa)
    h = entrar(client, u["rj"])
    cop = client.get(f"/api/cops/{cop_id}").json()
    assert cop["situacao"] == "FECHADO"
    assert cop["itens"][0]["sa"]["situacao"] == "CONFIRMADO" and cop["itens"][0]["sa"]["rs_kg"] is None
    assert "COP_SA_PRONTO" not in [n["tipo"] for n in client.get("/api/notificacoes").json()["itens"]]
    r = client.post(f"/api/cops/{cop_id}/nf", json=NF, headers=h)
    assert r.status_code == 400 and "SA confirmado" not in _falta(r) and "R$/kg" in _falta(r)
    v = client.post(f"/api/cops/{cop_id}/enviar/validar", headers=h).json()
    assert {o["codigo"] for o in v["ocorrencias"]} == {"PRECIFICADOR_PENDENTE", "NF_PENDENTE"}

    # R$/kg preenchido: "Aguardando NF", aviso ao RJ e o precificador no item do COP
    h = entrar(client, u["itu"])
    assert client.patch(f"/api/sas/{sa['id']}", json={"rs_kg": 42.5}, headers=h).status_code == 200
    h = entrar(client, u["rj"])
    cop = client.get(f"/api/cops/{cop_id}").json()
    assert cop["situacao"] == "AGUARDANDO_NF"
    item_sa = cop["itens"][0]["sa"]
    assert item_sa["rs_kg"] == 42.5 and item_sa["valor_precificador"] == pytest.approx(round(42.5 * 85 / 12, 2))
    assert [n["tipo"] for n in client.get("/api/notificacoes").json()["itens"]].count("COP_SA_PRONTO") == 1
    assert client.post(f"/api/cops/{cop_id}/nf", json=NF, headers=h).status_code == 200
    assert client.post(f"/api/cops/{cop_id}/enviar", headers=h).status_code == 200

    # depois da NF, o R$/kg pode ser corrigido, mas não apagado [proposta, P44(d)]
    h = entrar(client, u["itu"])
    r = client.patch(f"/api/sas/{sa['id']}", json={"rs_kg": None}, headers=h)
    assert r.status_code == 400 and "não apagado" in r.json()["detail"]
    assert client.patch(f"/api/sas/{sa['id']}", json={"rs_kg": 43.0}, headers=h).json()["rs_kg"] == 43.0


def test_precificador_antes_do_sa_e_zero_conta_como_vazio(amb):
    client, u, ids, fab = amb
    cop_id, sa = _cop_fechado(client, u, ids, numero=802)
    h = entrar(client, u["itu"])
    client.patch(f"/api/sas/{sa['id']}", json={"rs_kg": 0}, headers=h)
    h = entrar(client, u["rj"])
    r = client.post(f"/api/cops/{cop_id}/nf", json=NF, headers=h)
    assert r.status_code == 400 and "R$/kg do precificador em 1" in _falta(r)   # zero = vazio (P44(c))
    h = entrar(client, u["itu"])
    client.patch(f"/api/sas/{sa['id']}", json={"rs_kg": 40}, headers=h)
    h = entrar(client, u["rj"])
    r = client.post(f"/api/cops/{cop_id}/nf", json=NF, headers=h)
    assert r.status_code == 400 and "SA confirmado em 1" in _falta(r) and "R$/kg" not in _falta(r)
    # o último que falta (o SA) dispara o aviso ao RJ
    h = entrar(client, u["itu"])
    _confirmar(client, fab, h, sa, codigo=50102)
    h = entrar(client, u["rj"])
    assert "COP_SA_PRONTO" in [n["tipo"] for n in client.get("/api/notificacoes").json()["itens"]]
    assert client.post(f"/api/cops/{cop_id}/nf", json=NF, headers=h).status_code == 200


def test_fila_de_sa_filtra_pelo_numero_do_cop(amb):
    client, u, ids, _ = amb
    _cop_fechado(client, u, ids, numero=803)
    h = entrar(client, u["itu"])
    assert h is not None
    assert [s["cop"]["numero"] for s in client.get("/api/sas", params={"cop": 803}).json()["itens"]] == [803]
    assert client.get("/api/sas", params={"cop": 999}).json()["itens"] == []
