"""T13 corte em Itu (Mega e RJ em Itu, RETO, B2), T06 entrada NF, T17, T18 e T23."""
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


def test_corte_itu_lote_mega_com_reto_e_instrucao(amb):
    client, u, ids, _ = amb
    h = entrar(client, u["itu"])
    corpo = {"op": 100508, "lote_id": ids["lmega"], "consumo_kg": 104.5, "sobra_kg": 12, "sobra_na_bitola": False,
             "pecas": 128, "peso_usado_kg": 117}
    v = client.post("/api/cortes-itu/validar", json=corpo, headers=h).json()
    res = v["resultado"]
    assert res["gera_sa"] is False and res["perda_kg"] == 0.5
    assert res["instrucao_mega"] == ("Baixar 105,0 kg do código 78290 na OP 100508. Transferir 12,0 kg do código "
                                     "78290 para o código 1698 (IMP-H13 RETO).")
    r = client.post("/api/cortes-itu", json=corpo, headers=h)
    assert r.status_code == 201, r.text
    c = r.json()
    assert c["lote_reto"] and c["sa_id"] is None
    assert client.get(f"/api/lotes/{ids['lmega']}").json()["saldo_kg"] == pytest.approx(5198 - 117)
    reto = client.get(f"/api/lotes/{c['lote_reto']['id']}").json()
    assert reto["tipo"] == "RETO" and reto["estoque"] == "ESTOQUE_MEGA" and reto["codigo_mega"] == 1698


def test_corte_itu_valida_soma_e_perda(amb):
    client, u, ids, _ = amb
    h = entrar(client, u["itu"])
    v = client.post("/api/cortes-itu/validar", headers=h, json={"op": 100508, "lote_id": ids["lmega"],
                                                                "consumo_kg": 100, "sobra_kg": 30,
                                                                "peso_usado_kg": 120}).json()
    assert "SOMA_MAIOR_QUE_LOTE" in [o["codigo"] for o in v["ocorrencias"]]
    v = client.post("/api/cortes-itu/validar", headers=h, json={"op": 100508, "lote_id": ids["lmega"],
                                                                "consumo_kg": 100, "sobra_kg": 0,
                                                                "peso_usado_kg": 120, "pecas": 1}).json()
    assert "PERDA_CORTE_ALTA" in [o["codigo"] for o in v["ocorrencias"]]
    v = client.post("/api/cortes-itu/validar", headers=h, json={"op": 100508, "lote_id": ids["l33"],
                                                                "consumo_kg": 10}).json()
    assert "LOTE_FORA_DE_ITU" in [o["codigo"] for o in v["ocorrencias"]]


def _peca_inteira_recebida(client, u, ids, fab):
    from app.integrations.mega.gateway import SituacaoSa
    h = entrar(client, u["itu"])
    corpo = corpo_solicitacao(ids["l70"], op=100092,
                              medida={"formato": "RETANGULAR", "espessura": 65, "largura": 600, "comprimento": 200})
    corpo["itens"] = [{"lote_id": ids["l70"], "modo": "TRAZER_INTEIRA", "quantidade": 1}]
    s = client.post("/api/solicitacoes", json=corpo, headers=h).json()["solicitacoes"][0]
    h = entrar(client, u["rj"])
    client.post(f"/api/solicitacoes/{s['id']}/corte", headers=h,
                json={"linhas": [{"lote_id": ids["l70"], "pecas": 1, "peso_real_kg": 1288}]})
    cop = client.post("/api/cops", json={}, headers=h).json()
    lib = client.get("/api/cops/cortes-prontos").json()[0]["liberacao_id"]
    client.post(f"/api/cops/{cop['id']}/itens", json={"liberacao_ids": [lib]}, headers=h)
    client.post(f"/api/cops/{cop['id']}/fechar", headers=h)
    h = entrar(client, u["itu"])
    sa = client.get("/api/sas").json()["itens"][0]
    fab.obter().situacoes_sa[70001] = SituacaoSa(70001, True, "SA BLOCO", True, date.today(), 837)
    client.post(f"/api/sas/{sa['id']}/codigo", json={"sa_codigo": 70001}, headers=h)
    h = entrar(client, u["rj"])
    client.post(f"/api/cops/{cop['id']}/nf", json={"numero": "777", "emitente": "FIO_CERTO"}, headers=h)
    client.post(f"/api/cops/{cop['id']}/enviar", headers=h)
    h = entrar(client, u["itu"])
    item = client.get(f"/api/cops/{cop['id']}").json()["itens"][0]
    r = client.post(f"/api/cops/{cop['id']}/receber", json={"itens": [{"cop_item_id": item["id"]}]}, headers=h)
    return s["id"], r.json()["itens"][0]["lote_itu_id"], s["peso_previsto_kg"]


def test_peca_inteira_corte_itu_conclui_e_sobra_vira_b2(amb):
    client, u, ids, fab = amb
    sid, lote_itu, previsto = _peca_inteira_recebida(client, u, ids, fab)
    h = entrar(client, u["itu"])
    assert client.get("/api/cortes-itu/sugestao", params={"op": 100092}).json()["lote_id"] == lote_itu
    corpo = {"op": 100092, "lote_id": lote_itu, "consumo_kg": round(previsto * 1.1, 1), "sobra_kg": 300,
             "sobra_na_bitola": True, "pecas": 1, "peso_usado_kg": 1288}
    v = client.post("/api/cortes-itu/validar", json=corpo, headers=h).json()
    assert "EXCESSO_TOLERANCIA" in [o["codigo"] for o in v["ocorrencias"]] and v["resultado"]["gera_sa"] is False
    corpo["confirmacoes"] = {"EXCESSO_TOLERANCIA": "Peso maior por desvio de serra",
                             "PERDA_CORTE_ALTA": "Barra com ponta torta descartada"}
    r = client.post("/api/cortes-itu", json=corpo, headers=h)
    assert r.status_code == 201, r.text
    assert r.json()["sa_id"] is None
    assert client.get(f"/api/solicitacoes/{sid}").json()["situacao"] == "CONCLUIDA"
    assert client.get(f"/api/lotes/{lote_itu}").json()["saldo_kg"] == 300

    # depois, a sobra RJ em Itu usada noutra OP → SA do caminho B2 com NF só fiscal
    r = client.post("/api/cortes-itu", headers=h, json={"op": 100508, "lote_id": lote_itu, "consumo_kg": 50,
                                                        "sobra_kg": 249.5, "pecas": 2, "peso_usado_kg": 300,
                                                        "confirmacoes": {"PERDA_CORTE_ALTA": "Dois cortes na serra"}})
    assert r.status_code == 201, r.text
    sa = client.get(f"/api/sas/{r.json()['sa_id']}").json()
    assert sa["origem"] == "CORTE_ITU" and sa["peso_kg"] == 50 and sa["op"] == 100508
    r = client.post("/api/sas/nf", json={"ids": [sa["id"]], "numero": "558", "emitente": "FIO_CERTO"}, headers=h)
    assert r.json()[0]["nf"]["numero"] == "558"


def test_entrada_nf_cria_lotes_e_bloqueia_duplicada(amb):
    client, u, ids, _ = amb
    h = entrar(client, u["rj"])
    corpo = {"numero": "12345", "data": date.today().isoformat(), "fornecedor": "EASON", "conteiner": "ch50xy",
             "itens": [{"liga": "H13", "formato": "RETANGULAR", "espessura": 50, "largura": 610, "pecas": 4,
                        "peso_kg": 9000, "comprimento": "2800-6000"},
                       {"liga": "H13", "formato": "RETANGULAR", "espessura": 33, "largura": 105, "pecas": 10,
                        "peso_kg": 1200}]}
    v = client.post("/api/entradas-nf/validar", json=corpo, headers=h).json()
    assert v["ocorrencias"] == [] or all(o["nivel"] == "ALERTA" for o in v["ocorrencias"])
    r = client.post("/api/entradas-nf", json=corpo, headers=h)
    assert r.status_code == 201, r.text
    lotes = r.json()["itens"]
    l1 = client.get(f"/api/lotes/{lotes[0]['lote_id']}").json()
    assert l1["conteiner"] == "CH50XY" and l1["estoque"] == "RJ_NO_RIO" and l1["saldo_kg"] == 9000
    assert client.post("/api/entradas-nf", json=corpo, headers=h).status_code == 409
    corpo["itens"][0]["liga"] = "XYZ"
    corpo["numero"] = "999"
    v = client.post("/api/entradas-nf/validar", json=corpo, headers=h).json()
    assert "LIGA_DESCONHECIDA#1" in [o["codigo"] for o in v["ocorrencias"]]


def test_reserva_ajuste_estorno_e_parametro(amb):
    client, u, ids, _ = amb
    h = entrar(client, u["analise"])
    r = client.post(f"/api/lotes/{ids['l33']}/destinacoes", headers=h,
                    json={"tipo": "RESERVA", "descricao": "Reservado CPR", "kg": 950})
    assert r.status_code == 201
    h = entrar(client, u["itu"])
    v = client.post("/api/solicitacoes/validar", json=corpo_solicitacao(ids["l33"]), headers=h).json()
    codigos = [o["codigo"] for o in v["ocorrencias"]]
    assert "USA_SALDO_RESERVADO" in codigos and "DESTINACAO_0" in codigos
    # ajuste
    r = client.post(f"/api/lotes/{ids['l33b']}/ajuste", json={"saldo_contado_kg": 390, "justificativa": "curta"},
                    headers=h)
    assert r.status_code == 400
    r = client.post(f"/api/lotes/{ids['l33b']}/ajuste", headers=h,
                    json={"saldo_contado_kg": 390, "justificativa": "Inventário físico de 03/11"})
    assert r.status_code == 201 and r.json()["kg"] == -10
    # estorno de corte RJ antes do COP
    s = client.post("/api/solicitacoes", json=corpo_solicitacao(ids["l33b"]), headers=h).json()["solicitacoes"][0]
    h = entrar(client, u["rj"])
    client.post(f"/api/solicitacoes/{s['id']}/corte", headers=h,
                json={"linhas": [{"lote_id": ids["l33b"], "pecas": 12, "peso_real_kg": 84}]})
    mov = client.get(f"/api/lotes/{ids['l33b']}/movimentos").json()["itens"][-1]
    r = client.post(f"/api/movimentos/{mov['id']}/estorno", json={"justificativa": "Peso digitado errado"},
                    headers=h)
    assert r.status_code == 201, r.text
    assert client.get(f"/api/solicitacoes/{s['id']}").json()["situacao"] == "ENVIADA"
    assert client.get(f"/api/lotes/{ids['l33b']}").json()["saldo_kg"] == 390
    assert client.post(f"/api/movimentos/{mov['id']}/estorno", json={"justificativa": "De novo, por engano"},
                       headers=h).status_code == 400
    # parâmetro: só admin
    assert client.patch("/api/parametros/TOLERANCIA_EXCESSO_PCT", json={"valor": "10"}, headers=h).status_code == 403
