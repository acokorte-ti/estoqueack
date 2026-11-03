"""T11 COP → T14 SA → NF → envio → T12 recebimento (caminhos A e B)."""
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


def _cortada(client, u, ids, corpo, peso, pecas):
    h = entrar(client, u["itu"])
    s = client.post("/api/solicitacoes", json=corpo, headers=h).json()["solicitacoes"][0]
    h = entrar(client, u["rj"])
    r = client.post(f"/api/solicitacoes/{s['id']}/corte", headers=h,
                    json={"linhas": [{"lote_id": corpo["itens"][0]["lote_id"], "pecas": pecas, "peso_real_kg": peso}],
                          "confirmacoes": {"EXCESSO_TOLERANCIA": "Desvio de serra na barra"}})
    assert r.status_code == 201, r.text
    return s["id"]


def _confirmar_no_mega(fab, codigo):
    from app.integrations.mega.gateway import SituacaoSa
    fab.obter().situacoes_sa[codigo] = SituacaoSa(codigo, True, "SA PECA - CÓD.777", True, date.today(), 82.0)


def test_caminho_a_corte_rj(amb):
    client, u, ids, fab = amb
    sid = _cortada(client, u, ids, corpo_solicitacao(ids["l33"]), 85, 12)
    h = entrar(client, u["rj"])
    prontos = client.get("/api/cops/cortes-prontos").json()
    assert len(prontos) == 1
    assert client.get("/api/cops/proximo-numero").json() == {"numero": 1}
    cop = client.post("/api/cops", json={"numero": 601}, headers=h).json()
    cop = client.post(f"/api/cops/{cop['id']}/itens", json={"liberacao_ids": [prontos[0]["liberacao_id"]]},
                      headers=h).json()
    assert cop["qtd_itens"] == 1 and cop["situacao"] == "ABERTO"
    v = client.post(f"/api/cops/{cop['id']}/enviar/validar", headers=h).json()
    assert "COP_NAO_FECHADO" in [o["codigo"] for o in v["ocorrencias"]]
    cop = client.post(f"/api/cops/{cop['id']}/fechar", headers=h).json()
    assert cop["situacao"] == "FECHADO" and cop["itens"][0]["sa"]["situacao"] == "PENDENTE"
    assert client.get(f"/api/solicitacoes/{sid}").json()["situacao"] == "EM_COP"
    assert client.post(f"/api/cops/{cop['id']}/enviar", headers=h).status_code == 409

    # Itu: SA novo (a peça nunca teve SA), informa o código e o Mega confirma
    h = entrar(client, u["itu"])
    fila = client.get("/api/sas").json()
    assert fila["cops_aguardando_sa"][0]["numero"] == 601
    sa = fila["itens"][0]
    assert sa["sa_novo"] is True and sa["peso_kg"] == 85 and sa["dimensao"] == "33X105" and sa["conteiner"] == "CH33K"
    r = client.post(f"/api/sas/{sa['id']}/codigo", json={"sa_codigo": 50001}, headers=h)
    assert r.json()["situacao"] == "AGUARDANDO_MEGA"
    _confirmar_no_mega(fab, 50001)
    assert client.post("/api/sas/verificar", json={}, headers=h).json()["confirmados"] == 1
    assert client.get(f"/api/solicitacoes/{sid}").json()["situacao"] == "SA_PRONTO"

    # RJ: NF + envio
    h = entrar(client, u["rj"])
    assert "COP_SA_PRONTO" in [n["tipo"] for n in client.get("/api/notificacoes").json()["itens"]]
    assert client.get(f"/api/cops/{cop['id']}").json()["situacao"] == "AGUARDANDO_NF"
    v = client.post(f"/api/cops/{cop['id']}/enviar/validar", headers=h).json()
    assert [o["codigo"] for o in v["ocorrencias"]] == ["NF_PENDENTE"]
    client.post(f"/api/cops/{cop['id']}/nf", json={"numero": "556", "emitente": "FIO_CERTO"}, headers=h)
    r = client.post(f"/api/cops/{cop['id']}/enviar", headers=h)
    assert r.status_code == 200 and r.json()["situacao"] == "ENVIADO"
    assert client.get(f"/api/solicitacoes/{sid}").json()["situacao"] == "EM_TRANSITO"
    assert client.get(f"/api/sas/{sa['id']}").json()["nf"] == {"numero": "556", "emitente": "FIO_CERTO"}

    # Itu recebe com divergência de peso
    h = entrar(client, u["itu"])
    item = client.get(f"/api/cops/{cop['id']}").json()["itens"][0]
    corpo = {"itens": [{"cop_item_id": item["id"], "peso_conferido_kg": 80}]}
    v = client.post(f"/api/cops/{cop['id']}/receber/validar", json=corpo, headers=h).json()
    codigo = f"DIVERGENCIA_TRANSPORTE_{item['id']}"
    assert [o["codigo"] for o in v["ocorrencias"]] == [codigo]
    corpo["confirmacoes"] = {codigo: "Balança de Itu pesou 80 kg"}
    r = client.post(f"/api/cops/{cop['id']}/receber", json=corpo, headers=h)
    assert r.json()["situacao"] == "RECEBIDO"
    assert client.get(f"/api/solicitacoes/{sid}").json()["situacao"] == "CONCLUIDA"

    # a próxima OP do mesmo item já recebe o código sugerido
    sid2 = _cortada(client, u, ids, corpo_solicitacao(ids["l33b"], confirmacoes={"OP_DUPLICADA": "Segunda remessa"}),
                    30, 4)
    h = entrar(client, u["rj"])
    cop2 = client.post("/api/cops", json={}, headers=h).json()
    assert cop2["numero"] == 602
    lib = client.get("/api/cops/cortes-prontos").json()[0]["liberacao_id"]
    client.post(f"/api/cops/{cop2['id']}/itens", json={"liberacao_ids": [lib]}, headers=h)
    client.post(f"/api/cops/{cop2['id']}/fechar", headers=h)
    h = entrar(client, u["itu"])
    sa2 = [s for s in client.get("/api/sas").json()["itens"] if s["solicitacao_id"] == sid2][0]
    assert sa2["sa_codigo"] == 50001 and sa2["sa_novo"] is False
    v = client.post(f"/api/sas/{sa2['id']}/codigo/validar", json={"sa_codigo": 50002}, headers=h).json()
    assert [o["codigo"] for o in v["ocorrencias"]] == ["SA_CODIGO_TROCADO"]


def test_caminho_b_peca_inteira_gera_lote_rj_em_itu(amb):
    client, u, ids, fab = amb
    corpo = corpo_solicitacao(ids["l70"], op=100092,
                              medida={"formato": "RETANGULAR", "espessura": 65, "largura": 600, "comprimento": 200})
    corpo["itens"] = [{"lote_id": ids["l70"], "modo": "TRAZER_INTEIRA", "quantidade": 1}]
    sid = _cortada(client, u, ids, corpo, 1288, 1)
    previsto = client.get(f"/api/solicitacoes/{sid}").json()["peso_previsto_kg"]
    h = entrar(client, u["rj"])
    cop = client.post("/api/cops", json={}, headers=h).json()
    lib = client.get("/api/cops/cortes-prontos").json()[0]["liberacao_id"]
    client.post(f"/api/cops/{cop['id']}/itens", json={"liberacao_ids": [lib]}, headers=h)
    cop = client.post(f"/api/cops/{cop['id']}/fechar", headers=h).json()
    h = entrar(client, u["itu"])
    sa = client.get("/api/sas").json()["itens"][0]
    assert sa["peso_kg"] == pytest.approx(previsto)          # peça inteira: SA com o previsto [P03]
    client.post(f"/api/sas/{sa['id']}/codigo", json={"sa_codigo": 60001}, headers=h)
    _confirmar_no_mega(fab, 60001)
    client.post("/api/sas/verificar", json={"ids": [sa["id"]]}, headers=h)
    h = entrar(client, u["rj"])
    client.post(f"/api/cops/{cop['id']}/nf", json={"numero": "900", "emitente": "MEDIO_VALE"}, headers=h)
    assert client.post(f"/api/cops/{cop['id']}/enviar", headers=h).status_code == 200
    h = entrar(client, u["itu"])
    item = client.get(f"/api/cops/{cop['id']}").json()["itens"][0]
    r = client.post(f"/api/cops/{cop['id']}/receber", json={"itens": [{"cop_item_id": item["id"]}]}, headers=h)
    assert r.status_code == 200, r.text
    novo = r.json()["itens"][0]["lote_itu_id"]
    lote = client.get(f"/api/lotes/{novo}").json()
    assert lote["estoque"] == "RJ_EM_ITU" and lote["saldo_kg"] == 1288 and lote["origem"]["conteiner"] == "CH25K"
    assert client.get(f"/api/solicitacoes/{sid}").json()["situacao"] == "AGUARDANDO_CORTE_ITU"


def test_reabrir_cop_e_nf_por_item(amb):
    client, u, ids, fab = amb
    _cortada(client, u, ids, corpo_solicitacao(ids["l33"]), 85, 12)
    h = entrar(client, u["rj"])
    cop = client.post("/api/cops", json={}, headers=h).json()
    lib = client.get("/api/cops/cortes-prontos").json()[0]["liberacao_id"]
    client.post(f"/api/cops/{cop['id']}/itens", json={"liberacao_ids": [lib]}, headers=h)
    client.post(f"/api/cops/{cop['id']}/fechar", headers=h)
    assert client.post(f"/api/cops/{cop['id']}/itens", json={"liberacao_ids": [lib]}, headers=h).status_code == 400
    r = client.post(f"/api/cops/{cop['id']}/reabrir", json={"justificativa": "Faltou incluir a OP 100600"},
                    headers=h)
    assert r.json()["situacao"] == "ABERTO" and r.json()["itens"][0]["sa"] is None
    h = entrar(client, u["analise"])
    assert client.post(f"/api/cops/{cop['id']}/fechar", headers=h).status_code == 403
