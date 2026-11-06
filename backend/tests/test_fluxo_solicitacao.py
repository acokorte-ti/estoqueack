"""T07–T10: solicitação, reserva, fila RJ, corte (total, parcial, lote trocado), material insuficiente, perfis."""
import pytest

from tests.fluxo_util import catalogo_e_lotes, corpo_solicitacao, criar_usuarios, entrar, mega_falso

pytest.importorskip("fastapi")

# 30×100×250 de bitola 33×105 → bruto 33×105×255 (usa a largura inteira), 12 peças, H13 7,8
PREVISTO = round(33 * 105 * 255 * 7.8e-6, 3) * 12
PECA = round(30 * 100 * 250 * 7.8e-6, 3) * 12


@pytest.fixture()
def amb(client):
    u = criar_usuarios(client)
    ids = catalogo_e_lotes()
    fab = mega_falso()
    yield client, u, ids
    fab.definir(None)


def _lote(client, lote_id):
    return client.get(f"/api/lotes/{lote_id}").json()


def test_previa_calcula_bruto_peso_e_nao_grava(amb):
    client, u, ids = amb
    h = entrar(client, u["itu"])
    r = client.post("/api/solicitacoes/validar", json=corpo_solicitacao(ids["l33"]), headers=h)
    assert r.status_code == 200, r.text
    ef = r.json()["resultado"]["efeitos"][0]
    assert ef["bruto"] == {"espessura": 33, "largura": 105, "diametro": None, "comprimento": 255}
    assert ef["usa_largura_inteira"] is True and ef["sobremetal_largura_mm"] == 0
    assert ef["peso_previsto_kg"] == pytest.approx(PREVISTO, abs=0.01)
    assert ef["peso_peca_kg"] == pytest.approx(PECA, abs=0.01)
    assert ef["instrucao"] == "12 PEÇAS COM 255MM COMPRIMENTO"
    assert r.json()["resultado"]["op"]["cliente"] == "CLIENTE X"
    assert client.get("/api/solicitacoes").json()["total"] == 0


def test_fluxo_enviar_reservar_cortar(amb):
    client, u, ids = amb
    h = entrar(client, u["itu"])
    r = client.post("/api/solicitacoes", json=corpo_solicitacao(ids["l33"]), headers=h)
    assert r.status_code == 201, r.text
    s = r.json()["solicitacoes"][0]
    assert s["situacao"] == "ENVIADA" and s["cliente"] == "CLIENTE X" and s["pedido"] == "1-4521"
    assert s["reserva_kg"] == pytest.approx(PREVISTO, abs=0.01) and s["atraso"] == "NORMAL"
    assert _lote(client, ids["l33"])["reservado_kg"] == pytest.approx(PREVISTO, abs=0.01)

    # Marcelo: aviso, fila e corte com 5 % estourado
    h = entrar(client, u["rj"])
    assert any(n["tipo"] == "SOLICITACAO_ENVIADA" for n in client.get("/api/notificacoes").json()["itens"])
    fila = client.get("/api/fila-rj").json()
    assert [f["id"] for f in fila] == [s["id"]]
    corte = {"linhas": [{"lote_id": ids["l33"], "pecas": 12, "peso_real_kg": 90}]}
    v = client.post(f"/api/solicitacoes/{s['id']}/corte/validar", json=corte, headers=h).json()
    assert [o["codigo"] for o in v["ocorrencias"]] == ["EXCESSO_TOLERANCIA"]
    assert client.post(f"/api/solicitacoes/{s['id']}/corte", json=corte, headers=h).status_code == 409
    corte["confirmacoes"] = {"EXCESSO_TOLERANCIA": "Desvio de serra na barra"}
    r = client.post(f"/api/solicitacoes/{s['id']}/corte", json=corte, headers=h)
    assert r.status_code == 201, r.text
    assert r.json()["situacao"] == "CORTADA" and r.json()["peso_real_kg"] == 90
    assert client.get("/api/fila-rj").json() == []
    lote = _lote(client, ids["l33"])
    assert lote["saldo_kg"] == 910 and lote["reservado_kg"] == 0
    movs = client.get(f"/api/lotes/{ids['l33']}/movimentos").json()["itens"]
    assert movs[-1]["tipo"] == "SAIDA_CORTE_RJ" and movs[-1]["kg"] == -90 and movs[-1]["op"] == 100592

    h = entrar(client, u["itu"])
    tipos = [n["tipo"] for n in client.get("/api/notificacoes").json()["itens"]]
    assert "CORTE_REGISTRADO" in tipos


def test_parcial_e_encerrar_com_saldo_pendente(amb):
    client, u, ids = amb
    h = entrar(client, u["itu"])
    s = client.post("/api/solicitacoes", json=corpo_solicitacao(ids["l33"]), headers=h).json()["solicitacoes"][0]
    h = entrar(client, u["rj"])
    r = client.post(f"/api/solicitacoes/{s['id']}/corte", headers=h,
                    json={"linhas": [{"lote_id": ids["l33"], "pecas": 4, "peso_real_kg": 27.5}]})
    assert r.status_code == 201, r.text
    assert r.json()["situacao"] == "CORTADA_PARCIAL"
    assert r.json()["reserva_kg"] == pytest.approx(PREVISTO * 8 / 12, abs=0.01)
    h = entrar(client, u["itu"])
    assert client.post(f"/api/solicitacoes/{s['id']}/encerrar", json={"justificativa": "curta"},
                       headers=h).status_code == 422
    r = client.post(f"/api/solicitacoes/{s['id']}/encerrar", headers=h,
                    json={"justificativa": "Restante vai em outra OP com outro lote"})
    assert r.json()["situacao"] == "CORTADA" and r.json()["reserva_kg"] == 0
    assert _lote(client, ids["l33"])["reservado_kg"] == 0


def test_parcial_com_material_insuficiente_nao_fica_travada(amb):
    """Auditoria 06/11: parcial marcada 'material insuficiente' tinha corte e não saía mais do estado."""
    client, u, ids = amb
    h = entrar(client, u["itu"])
    s = client.post("/api/solicitacoes", json=corpo_solicitacao(ids["l33"]), headers=h).json()["solicitacoes"][0]
    h = entrar(client, u["rj"])
    client.post(f"/api/solicitacoes/{s['id']}/corte", headers=h,
                json={"linhas": [{"lote_id": ids["l33"], "pecas": 4, "peso_real_kg": 27.5}]})
    r = client.post(f"/api/solicitacoes/{s['id']}/material-insuficiente", headers=h,
                    json={"observacao": "Barra com trinca, faltam peças"})
    assert r.json()["situacao"] == "MATERIAL_INSUFICIENTE" and r.json()["pecas_cortadas"] == 4
    h = entrar(client, u["itu"])
    # as peças já cortadas entram no COP mesmo com a solicitação em Material insuficiente
    assert len(client.get("/api/cops/cortes-prontos").json()) == 1
    # trocar lote / cancelar continuam bloqueados (já há corte); a saída é encerrar com saldo pendente
    assert client.post(f"/api/solicitacoes/{s['id']}/cancelar", json={"motivo": "x"}, headers=h).status_code == 400
    r = client.post(f"/api/solicitacoes/{s['id']}/encerrar", headers=h,
                    json={"justificativa": "Restante vai em outra solicitação com outro lote"})
    assert r.status_code == 200, r.text
    assert r.json()["situacao"] == "CORTADA" and r.json()["reserva_kg"] == 0
    assert len(client.get("/api/cops/cortes-prontos").json()) == 1


def test_encerrar_sem_corte_em_material_insuficiente_continua_bloqueado(amb):
    client, u, ids = amb
    h = entrar(client, u["itu"])
    s = client.post("/api/solicitacoes", json=corpo_solicitacao(ids["l33"]), headers=h).json()["solicitacoes"][0]
    h = entrar(client, u["rj"])
    client.post(f"/api/solicitacoes/{s['id']}/material-insuficiente", headers=h, json={"observacao": "Sem material"})
    h = entrar(client, u["itu"])
    r = client.post(f"/api/solicitacoes/{s['id']}/encerrar", headers=h,
                    json={"justificativa": "Tentativa sem corte nenhum"})
    assert r.status_code == 400


def test_lote_trocado_e_dividido_no_rj(amb):
    client, u, ids = amb
    h = entrar(client, u["itu"])
    s = client.post("/api/solicitacoes", json=corpo_solicitacao(ids["l33"]), headers=h).json()["solicitacoes"][0]
    h = entrar(client, u["rj"])
    corte = {"linhas": [{"lote_id": ids["l33"], "pecas": 8, "peso_real_kg": 55},
                        {"lote_id": ids["l33b"], "pecas": 4, "peso_real_kg": 27.6}]}
    v = client.post(f"/api/solicitacoes/{s['id']}/corte/validar", json=corte, headers=h).json()
    assert [o["codigo"] for o in v["ocorrencias"]] == ["LOTE_TROCADO#2"]
    corte["confirmacoes"] = {"LOTE_TROCADO#2": "CH33K acabou, completei com o CH40SH"}
    r = client.post(f"/api/solicitacoes/{s['id']}/corte", json=corte, headers=h)
    assert r.status_code == 201 and r.json()["situacao"] == "CORTADA" and len(r.json()["cortes"]) == 2
    assert _lote(client, ids["l33b"])["saldo_kg"] == pytest.approx(372.4)
    h = entrar(client, u["itu"])
    assert "LOTE_TROCADO_RJ" in [n["tipo"] for n in client.get("/api/notificacoes").json()["itens"]]


def test_material_insuficiente_trocar_lote_e_cancelar(amb):
    client, u, ids = amb
    h = entrar(client, u["itu"])
    s = client.post("/api/solicitacoes", json=corpo_solicitacao(ids["l33"]), headers=h).json()["solicitacoes"][0]
    h = entrar(client, u["rj"])
    r = client.post(f"/api/solicitacoes/{s['id']}/material-insuficiente", headers=h,
                    json={"observacao": "Barra do CH33K com trinca"})
    assert r.json()["situacao"] == "MATERIAL_INSUFICIENTE" and r.json()["reserva_kg"] == 0
    h = entrar(client, u["itu"])
    v = client.post(f"/api/solicitacoes/{s['id']}/trocar-lote/validar", json={"lote_id": ids["l2344"]},
                    headers=h).json()
    assert "LIGA_EQUIVALENTE" in [o["codigo"] for o in v["ocorrencias"]]
    r = client.post(f"/api/solicitacoes/{s['id']}/trocar-lote", headers=h,
                    json={"lote_id": ids["l2344"], "confirmacoes": {"LIGA_EQUIVALENTE": "1.2344 equivale ao H13"}})
    assert r.status_code == 200, r.text
    assert r.json()["situacao"] == "ENVIADA" and r.json()["lote"]["id"] == ids["l2344"]
    assert _lote(client, ids["l2344"])["reservado_kg"] > 0 and _lote(client, ids["l33"])["reservado_kg"] == 0
    r = client.post(f"/api/solicitacoes/{s['id']}/cancelar", json={"motivo": "OP suspensa"}, headers=h)
    assert r.json()["situacao"] == "CANCELADA" and _lote(client, ids["l2344"])["reservado_kg"] == 0


def test_validacoes_op_bitola_saldo_e_modo(amb):
    client, u, ids = amb
    h = entrar(client, u["itu"])
    v = client.post("/api/solicitacoes/validar", json=corpo_solicitacao(ids["l33"], op=999999), headers=h).json()
    assert "OP_INEXISTENTE" in [o["codigo"] for o in v["ocorrencias"]]
    medida = {"formato": "RETANGULAR", "espessura": 40, "largura": 100, "comprimento": 250}
    v = client.post("/api/solicitacoes/validar", json=corpo_solicitacao(ids["l33"], medida=medida), headers=h).json()
    assert "BITOLA_MENOR_QUE_PECA" in [o["codigo"] for o in v["ocorrencias"]]
    corpo = corpo_solicitacao(ids["l33"])
    corpo["itens"][0]["quantidade"] = 200
    v = client.post("/api/solicitacoes/validar", json=corpo, headers=h).json()
    assert "SALDO_INSUFICIENTE" in [o["codigo"] for o in v["ocorrencias"]]
    v = client.post("/api/solicitacoes/validar", json=corpo_solicitacao(ids["lmega"]), headers=h).json()
    assert "MODO_INCOMPATIVEL" in [o["codigo"] for o in v["ocorrencias"]]
    client.post("/api/solicitacoes", json=corpo_solicitacao(ids["l33"]), headers=h)
    v = client.post("/api/solicitacoes/validar", json=corpo_solicitacao(ids["l33b"]), headers=h).json()
    assert "OP_DUPLICADA" in [o["codigo"] for o in v["ocorrencias"]]


def test_peca_inteira_sem_regra_5pct_e_rascunho(amb):
    client, u, ids = amb
    h = entrar(client, u["itu"])
    corpo = corpo_solicitacao(ids["l70"], op=100092, enviar=False,
                              medida={"formato": "RETANGULAR", "espessura": 65, "largura": 600, "comprimento": 200})
    corpo["itens"] = [{"lote_id": ids["l70"], "modo": "TRAZER_INTEIRA", "quantidade": 1, "comprimento_barra_mm": 3905}]
    r = client.post("/api/solicitacoes", json=corpo, headers=h)
    s = r.json()["solicitacoes"][0]
    assert s["situacao"] == "RASCUNHO" and s["instrucao"] == "TRAZER 01 PEÇA H13 70X610X3905"
    assert s["reserva_kg"] == 0
    corpo["enviar"] = True
    r = client.put(f"/api/solicitacoes/{s['id']}", json=corpo, headers=h)
    assert r.json()["situacao"] == "ENVIADA"
    h = entrar(client, u["rj"])
    r = client.post(f"/api/solicitacoes/{s['id']}/corte", headers=h,
                    json={"linhas": [{"lote_id": ids["l70"], "pecas": 1, "peso_real_kg": 1288,
                                      "comprimento_barra_mm": 3905}]})
    assert r.status_code == 201, r.text   # barra bem maior que o previsto: sem EXCESSO_TOLERANCIA
    assert r.json()["situacao"] == "CORTADA"


def test_perfis_e_visibilidade(amb):
    client, u, ids = amb
    h = entrar(client, u["rj"])
    assert client.post("/api/solicitacoes/validar", json=corpo_solicitacao(ids["l33"]), headers=h).status_code == 403
    estoques = {l["estoque"] for l in client.get("/api/lotes").json()["itens"]}
    assert estoques == {"RJ_NO_RIO"}
    assert client.get(f"/api/lotes/{ids['lmega']}").status_code == 404
    h = entrar(client, u["analise"])
    assert client.get("/api/fila-rj").status_code == 403
    assert client.get("/api/solicitacoes").status_code == 200


def test_lotes_compativeis_com_liga_equivalente(amb):
    client, u, ids = amb
    entrar(client, u["itu"])
    r = client.get("/api/lotes/compativeis", params={"liga": "H13", "espessura": 30, "largura": 100,
                                                      "comprimento": 250, "quantidade": 12}).json()
    codigos = [(x["id"], x["liga_equivalente"]) for x in r["itens"]]
    assert (ids["l2344"], True) in codigos and (ids["l33"], False) in codigos
    assert ids["l70"] in [x["id"] for x in r["itens"]]          # comporta, mas com sobremetal maior
    assert r["itens"][-1]["id"] == ids["l70"]
