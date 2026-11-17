"""Ajustes do teste manual de 2026-11-17 (DECISOES.md): filtro de liga por "contém", justificativa sem mínimo,
NF de transferência nova só da Fio Certo e instrução de processo com várias opções. Dados fictícios."""
import pytest

from tests.fluxo_util import catalogo_e_lotes, corpo_solicitacao, criar_usuarios, entrar, mega_falso

pytest.importorskip("fastapi")


@pytest.fixture()
def amb(client):
    u = criar_usuarios(client)
    ids = catalogo_e_lotes()
    from app.core.db import SessionLocal
    from app.models import Conteiner, ItemMP, Liga
    from app.services import movimentos as mov
    with SessionLocal() as db:
        a8 = Liga(codigo="A8", nome="A8", densidade=7.8, apelidos=[])
        a8m = Liga(codigo="A8MOD", nome="A8 MOD", densidade=7.8, apelidos=[])
        db.add_all([a8, a8m])
        db.flush()
        ct = Conteiner(codigo="CH90Z")
        i1 = ItemMP(descricao="A8 40x200", liga_id=a8.id, formato="RETANGULAR", espessura=40, largura=200)
        i2 = ItemMP(descricao="A8 MOD 40x200", liga_id=a8m.id, formato="RETANGULAR", espessura=40, largura=200)
        r1 = ItemMP(descricao="A8 RETO", liga_id=a8.id, formato="RETO")
        r2 = ItemMP(descricao="A8 MOD RETO", liga_id=a8m.id, formato="RETO")
        db.add_all([ct, i1, i2, r1, r2])
        db.flush()
        for item, kg, tipo in ((i1, 700, "ORIGINAL"), (i2, 800, "ORIGINAL"), (r1, 50, "RETO"), (r2, 60, "RETO")):
            lote = mov.criar_lote(db, item=item, planta_fiscal="RJ", local_fisico="RJ", conteiner_id=ct.id,
                                  peso_inicial_kg=kg, tipo=tipo)
            mov.lancar(db, lote, "SALDO_INICIAL", kg, usuario_id=None)
        db.commit()
    fab = mega_falso()
    yield client, u, ids
    fab.definir(None)


def test_liga_por_contem_sem_diferenciar_maiuscula(amb):
    client, u, _ = amb
    entrar(client, u["itu"])
    ligas = lambda r: sorted({i["liga"] for i in r.json()["itens"]})  # noqa: E731
    assert ligas(client.get("/api/lotes?liga=a8")) == ["A8", "A8MOD"]          # A8 traz A8 e A8 MOD
    assert ligas(client.get("/api/lotes?liga=A8 mod")) == ["A8MOD"]           # com espaço, como na tela
    assert ligas(client.get("/api/lotes?liga=mod")) == ["A8MOD"]
    assert "H13" in ligas(client.get("/api/lotes?liga=h13"))                 # equivalentes: P38(a), proposta
    assert client.get("/api/lotes?liga=a8_").json()["total"] == 0              # "_" não é curinga
    ag = {g["liga"] for g in client.get("/api/lotes/agrupado?liga=A8").json()["itens"]}
    assert ag == {"A8", "A8MOD"}                                               # MOD continua grupo próprio
    reto = client.get("/api/lotes/reto-por-origem?liga=a8").json()
    assert sorted(lg["liga"] for lg in reto["ligas"]) == ["A8", "A8MOD"]
    assert client.get("/api/exportar/lotes.xlsx?liga=a8").status_code == 200
    assert client.get("/api/exportar/reto-por-origem.xlsx?liga=a8").status_code == 200


def test_liga_contem_funcao():
    from app.services.estoque import liga_contem
    assert liga_contem("A8MOD", "a8") and liga_contem("A8MOD", "A8 MOD") and liga_contem("H13", None)
    assert not liga_contem("H13", "A8")


def test_justificativa_sem_minimo(amb):
    from app.domain import regras
    r = regras.validar_peso_real(100, 106)
    assert not r.pode_gravar({"EXCESSO_TOLERANCIA": "   "})                   # vazia continua não valendo
    assert r.pode_gravar({"EXCESSO_TOLERANCIA": "x"})
    client, u, ids = amb
    h = entrar(client, u["itu"])
    r = client.post(f"/api/lotes/{ids['l33b']}/ajuste", json={"saldo_contado_kg": 390, "justificativa": ""},
                    headers=h)
    assert r.status_code == 400
    r = client.post(f"/api/lotes/{ids['l33b']}/ajuste", json={"saldo_contado_kg": 390, "justificativa": "ok"},
                    headers=h)
    assert r.status_code == 201, r.text
    r = client.post(f"/api/movimentos/{r.json()['movimento_id']}/estorno", json={"justificativa": "x"}, headers=h)
    assert r.status_code == 201, r.text


def test_instrucao_de_processo_com_varias_opcoes(amb):
    client, u, ids = amb
    h = entrar(client, u["itu"])
    texto = "Retificar espessura; Retificar largura; Peça bipartida; Usar sobras; " + "x" * 200
    assert len(texto) <= 300
    corpo = corpo_solicitacao(ids["l33"])
    corpo["itens"][0]["instrucao_processo"] = texto
    r = client.post("/api/solicitacoes", json=corpo, headers=h)
    assert r.status_code == 201, r.text
    sid = r.json()["solicitacoes"][0]["id"]
    assert client.get(f"/api/solicitacoes/{sid}").json()["instrucao_processo"] == texto


def test_emitente_novo_so_fio_certo():
    from app.api.routes.cops import NfB2, NfCorpo
    from app.services import sas
    from app.services.base import ErroNegocio
    assert NfCorpo(numero="1").emitente == "FIO_CERTO"                       # padrão: pode omitir
    for valor in ("MEDIO_VALE", "OUTRO"):
        with pytest.raises(ValueError):
            NfCorpo(numero="1", emitente=valor)
        with pytest.raises(ValueError):
            NfB2(ids=[1], numero="1", emitente=valor)
        with pytest.raises(ErroNegocio):
            sas.obter_nf(None, "1", valor)
    assert "MEDIO_VALE" in sas.EMITENTES_HISTORICO                          # histórico continua lido


# ---- bitola estritamente maior que a peça (Eduardo, 2026-11-17) ----

def test_validar_bitola_estritamente_maior():
    from app.domain import regras

    def cods(r):
        return [o.codigo for o in r.ocorrencias]
    assert cods(regras.validar_bitola(45, 600, None, 45, 600, None)) == ["BITOLA_MENOR_QUE_PECA"]   # igual: erro
    assert cods(regras.validar_bitola(46, 601, None, 45, 600, None)) == []
    assert cods(regras.validar_bitola(46, 600, None, 45, 600, None)) == ["BITOLA_MENOR_QUE_PECA"]
    r = regras.validar_bitola(45, 600, None, 45, 600, None)
    assert r.ocorrencias[0].mensagem == "A bitola precisa ser maior que a peça em todas as medidas."
    assert cods(regras.validar_bitola(None, None, 90, None, None, 90)) == ["BITOLA_MENOR_QUE_PECA"]   # redondo
    assert cods(regras.validar_bitola(None, None, 91, None, None, 90)) == []
    # (a) comprimento: só quando os dois têm
    assert cods(regras.validar_bitola(46, 601, None, 45, 600, None, 3000, 3000)) == ["COMPRIMENTO_MENOR_QUE_PECA"]
    assert cods(regras.validar_bitola(46, 601, None, 45, 600, None, 3001, 3000)) == []
    assert cods(regras.validar_bitola(46, 601, None, 45, 600, None, None, 3000)) == []


@pytest.fixture()
def amb_bitola(client):
    u = criar_usuarios(client)
    from app.core.db import SessionLocal
    from app.models import Conteiner, ItemMP, Liga
    from app.services import movimentos as mov
    ids = {}
    with SessionLocal() as db:
        h13 = Liga(codigo="H13", nome="H13", densidade=7.8, apelidos=[])
        db.add(h13)
        db.flush()
        ct = Conteiner(codigo="CH77Q")
        db.add(ct)
        for nome, desc, e, larg in (("igual", "H13 45x600", 45, 600), ("maior", "H13 46x601", 46, 601),
                                    ("so_esp", "H13 46x600", 46, 600), ("curto", "H13 50x650x200", 50, 650)):
            it = ItemMP(descricao=desc, liga_id=h13.id, formato="RETANGULAR", espessura=e, largura=larg)
            db.add(it)
            db.flush()
            lote = mov.criar_lote(db, item=it, planta_fiscal="RJ", local_fisico="RJ", conteiner_id=ct.id,
                                  peso_inicial_kg=900)
            mov.lancar(db, lote, "SALDO_INICIAL", 900, usuario_id=None)
            ids[nome] = lote.id
        reto = ItemMP(descricao="H13 RETO", liga_id=h13.id, formato="RETO")
        db.add(reto)
        db.flush()
        lote = mov.criar_lote(db, item=reto, planta_fiscal="RJ", local_fisico="RJ", conteiner_id=ct.id,
                              peso_inicial_kg=80, tipo="RETO")
        mov.lancar(db, lote, "SALDO_INICIAL", 80, usuario_id=None)
        ids["reto"] = lote.id
        db.commit()
    fab = mega_falso()
    yield client, u, ids
    fab.definir(None)


def test_sugestao_so_oferece_lote_maior(amb_bitola):
    client, u, ids = amb_bitola
    entrar(client, u["itu"])
    r = client.get("/api/lotes/compativeis?liga=H13&espessura=45&largura=600&comprimento=250&quantidade=1").json()
    achou = {i["id"]: i for i in r["itens"]}
    assert ids["maior"] in achou and ids["curto"] not in achou          # 200 de comprimento < 250 (proposta a)
    assert ids["igual"] not in achou and ids["so_esp"] not in achou
    assert achou[ids["reto"]]["aviso_medida"] == "RETO sem medida: confira se é maior que a peça."   # proposta b
    assert achou[ids["maior"]]["aviso_medida"] is None


def test_pedido_com_lote_igual_a_peca_da_erro(amb_bitola):
    client, u, ids = amb_bitola
    h = entrar(client, u["itu"])
    medida = {"formato": "RETANGULAR", "espessura": 45, "largura": 600, "comprimento": 250}
    for nome, erro in (("igual", True), ("so_esp", True), ("maior", False)):
        corpo = corpo_solicitacao(ids[nome], medida=medida)
        corpo["itens"][0]["quantidade"] = 1
        v = client.post("/api/solicitacoes/validar", json=corpo, headers=h).json()
        assert ("BITOLA_MENOR_QUE_PECA" in [o["codigo"] for o in v["ocorrencias"]]) is erro, (nome, v)


# ---- lote consumido por inteiro e peças × quantidade da OP (Eduardo, 2026-11-17; dados fictícios) ----

@pytest.fixture()
def amb_op50(client):
    from datetime import date

    from app.core.db import SessionLocal
    from app.integrations.mega.gateway import OrdemProducao
    from app.models import Conteiner, ItemMP, Liga
    from app.services import movimentos as mov
    u = criar_usuarios(client)
    ids = {}
    with SessionLocal() as db:
        h13 = Liga(codigo="H13", nome="H13", densidade=7.8, apelidos=[])
        db.add(h13)
        db.flush()
        ct = Conteiner(codigo="CH88W")
        db.add(ct)
        for nome, e, larg, kg in (("fim", 47, 153, 35), ("curto", 47, 153, 30), ("grande", 50, 610, 900)):
            it = ItemMP(descricao=f"H13 {e}x{larg}", liga_id=h13.id, formato="RETANGULAR", espessura=e, largura=larg)
            db.add(it)
            db.flush()
            lote = mov.criar_lote(db, item=it, planta_fiscal="RJ", local_fisico="RJ", conteiner_id=ct.id,
                                  peso_inicial_kg=kg)
            mov.lancar(db, lote, "SALDO_INICIAL", kg, usuario_id=None)
            ids[nome] = lote.id
        db.commit()
    fab = mega_falso(OrdemProducao(100957, 999, "PECA 40X150X180MM", "CLIENTE W", "AB", date(2026, 10, 1), 50,
                                   date(2026, 12, 20)))
    yield client, u, ids
    fab.definir(None)


def _pedido_op50(ids, partes):
    return {"op": 100957, "liga": "H13",
            "medida": {"formato": "RETANGULAR", "espessura": 40, "largura": 150, "comprimento": 180},
            "itens": [{"lote_id": ids[n], "modo": "CORTAR_RJ", "quantidade": q} for n, q in partes],
            "enviar": True, "confirmacoes": {}}


def test_lote_menor_que_previsto_e_consumido_por_inteiro(amb_op50):
    client, u, ids = amb_op50
    h = entrar(client, u["itu"])
    corpo = _pedido_op50(ids, [("fim", 4), ("grande", 46)])
    v = client.post("/api/solicitacoes/validar", json=corpo, headers=h).json()
    oc = {o["codigo"]: o for o in v["ocorrencias"]}
    assert "SALDO_INSUFICIENTE" not in oc and oc["CONSUMO_LOTE_INTEIRO"]["nivel"] == "CIENCIA"
    ef = v["resultado"]["efeitos"][0]
    assert ef["peso_previsto_kg"] > 35 > ef["peso_peca_kg"]                  # previsto > saldo > peça acabada
    assert ef["reserva_kg"] == 35 and ef["consome_lote_inteiro"] is True
    assert v["resultado"]["efeitos"][1]["consome_lote_inteiro"] is False
    assert "consumido por inteiro (35,0 kg)" in oc["CONSUMO_LOTE_INTEIRO"]["mensagem"]
    assert "PECAS_ACIMA_OP" not in oc and "PECAS_ABAIXO_OP" not in oc
    assert "consumido por inteiro: 35,0 kg" in v["resultado"]["frase"]
    corpo["confirmacoes"] = {o["codigo"]: "fim de lote" for o in v["ocorrencias"] if o["nivel"] == "CIENCIA"}
    r = client.post("/api/solicitacoes", json=corpo, headers=h)
    assert r.status_code == 201, r.text
    sol = r.json()["solicitacoes"][0]
    assert client.get(f"/api/solicitacoes/{sol['id']}").json()["reserva_kg"] == 35
    assert client.get(f"/api/lotes/{ids['fim']}").json()["disponivel_kg"] == 0
    # RJ corta as 4 peças com o lote inteiro: sem "estou ciente" de excesso
    h = entrar(client, u["rj"])
    corte = {"linhas": [{"lote_id": ids["fim"], "pecas": 4, "peso_real_kg": 35}]}
    v = client.post(f"/api/solicitacoes/{sol['id']}/corte/validar", json=corte, headers=h).json()
    assert [o["codigo"] for o in v["ocorrencias"] if o["nivel"] != "ALERTA"] == []
    assert client.post(f"/api/solicitacoes/{sol['id']}/corte", json=corte, headers=h).status_code == 201


def test_saldo_abaixo_da_peca_acabada_continua_erro(amb_op50):
    client, u, ids = amb_op50
    h = entrar(client, u["itu"])
    v = client.post("/api/solicitacoes/validar", json=_pedido_op50(ids, [("curto", 4), ("grande", 46)]),
                    headers=h).json()
    oc = {o["codigo"]: o for o in v["ocorrencias"]}
    assert oc["SALDO_INSUFICIENTE"]["nivel"] == "ERRO" and "CONSUMO_LOTE_INTEIRO" not in oc


def test_soma_das_pecas_contra_a_op(amb_op50):
    client, u, ids = amb_op50
    h = entrar(client, u["itu"])
    v = client.post("/api/solicitacoes/validar", json=_pedido_op50(ids, [("grande", 50), ("fim", 1)]),
                    headers=h).json()
    oc = {o["codigo"]: o for o in v["ocorrencias"]}
    assert oc["PECAS_ACIMA_OP"]["nivel"] == "ERRO"
    assert oc["PECAS_ACIMA_OP"]["mensagem"] == "A soma das peças (51) passa da quantidade da OP (50)."
    r = client.post("/api/solicitacoes", json=_pedido_op50(ids, [("grande", 50), ("fim", 1)]), headers=h)
    assert r.status_code == 409
    v = client.post("/api/solicitacoes/validar", json=_pedido_op50(ids, [("grande", 40)]), headers=h).json()
    oc = {o["codigo"]: o for o in v["ocorrencias"]}
    assert oc["PECAS_ABAIXO_OP"]["nivel"] == "ALERTA" and "Faltam 10 peça(s)" in oc["PECAS_ABAIXO_OP"]["mensagem"]
