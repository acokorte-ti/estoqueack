import pytest

from tests.conftest import preparar_admin

pytest.importorskip("fastapi")


@pytest.fixture()
def dados(client):
    from app.core.db import SessionLocal
    from app.models import Conteiner, Destinacao, ItemMP, Liga, Lote, Movimento
    with SessionLocal() as db:
        h13 = Liga(codigo="H13", nome="H13", densidade=7.8, apelidos=[])
        db.add(h13)
        db.flush()
        bit = ItemMP(descricao="H13 70x610", liga_id=h13.id, formato="RETANGULAR", espessura=70, largura=610)
        reto = ItemMP(descricao="IMP-H13 RETO", liga_id=h13.id, formato="RETO", codigo_mega=1698)
        ct = Conteiner(codigo="CH25K")
        db.add_all([bit, reto, ct])
        db.flush()
        orig = Lote(codigo="L-000001", conteiner_id=ct.id, item_mp_id=bit.id, planta_fiscal="RJ", local_fisico="RJ",
                    tipo="ORIGINAL", peso_inicial_kg=5000, saldo_kg=3712)
        db.add(orig)
        db.flush()
        itu = Lote(codigo="L-000002", conteiner_id=ct.id, item_mp_id=bit.id, planta_fiscal="RJ", local_fisico="ITU",
                   tipo="SOBRA", lote_pai_id=orig.id, peso_inicial_kg=1288, saldo_kg=0)
        db.add(itu)
        db.flush()
        r = Lote(codigo="L-000003", conteiner_id=ct.id, item_mp_id=reto.id, planta_fiscal="RJ", local_fisico="ITU",
                 tipo="RETO", lote_pai_id=itu.id, peso_inicial_kg=446, saldo_kg=446)
        db.add(r)
        db.flush()
        db.add_all([
            Movimento(lote_id=orig.id, tipo="SALDO_INICIAL", kg=5000),
            Movimento(lote_id=orig.id, tipo="ENVIO_ITU", kg=-1288, op=100092),
            Movimento(lote_id=r.id, tipo="GERA_RETO", kg=446, op=100092),
            Destinacao(lote_id=orig.id, tipo="RESERVA", descricao="Reservado CPR", kg=200),
        ])
        db.commit()
        return {"orig": orig.id, "itu": itu.id, "reto": r.id}


def test_lista_e_filtros(client, dados):
    preparar_admin(client)
    r = client.get("/api/lotes").json()
    assert r["total"] == 2                       # com_saldo=true esconde o lote zerado
    cods = {i["codigo"]: i for i in r["itens"]}
    assert cods["L-000001"]["reservado_kg"] == 200 and cods["L-000001"]["disponivel_kg"] == 3512
    assert cods["L-000001"]["indicadores"]["destinacao"] is True
    assert cods["L-000003"]["estoque"] == "RJ_EM_ITU"
    assert cods["L-000003"]["origem"] == {"lote": "L-000001", "conteiner": "CH25K", "bitola": "70X610"}
    assert client.get("/api/lotes?estoque=RJ_NO_RIO").json()["total"] == 1
    assert client.get("/api/lotes?formato=RETO&liga=h13").json()["total"] == 1
    assert client.get("/api/lotes?com_saldo=false").json()["total"] == 3
    assert client.get("/api/lotes?largura_de=600&largura_ate=620").json()["total"] == 1
    assert client.get("/api/lotes?com_destinacao=true").json()["total"] == 1
    assert client.get("/api/lotes?codigo_mega=1698").json()["itens"][0]["codigo"] == "L-000003"


def test_agrupado(client, dados):
    preparar_admin(client)
    g = {(i["liga"], i["bitola"]): i for i in client.get("/api/lotes/agrupado").json()["itens"]}
    assert g[("H13", "RETO")]["por_estoque"]["RJ_EM_ITU"] == 446
    assert g[("H13", "70X610")]["saldo_kg"] == 3712


def test_detalhe_arvore_movimentos(client, dados):
    preparar_admin(client)
    d = client.get(f"/api/lotes/{dados['reto']}").json()
    assert d["peso_inicial_kg"] == 446 and d["tipo"] == "RETO"
    a = client.get(f"/api/lotes/{dados['reto']}/arvore").json()
    assert a["raiz"]["codigo"] == "L-000001"
    assert a["raiz"]["filhos"][0]["filhos"][0]["codigo"] == "L-000003"
    m = client.get(f"/api/lotes/{dados['orig']}/movimentos").json()["itens"]
    assert [x["saldo_apos_kg"] for x in m] == [5000, 3712]
    assert m[1]["op"] == 100092 and m[1]["tipo_descricao"] == "Envio para Itu"
    assert client.get("/api/lotes/9999").status_code == 404


def test_notas_e_destinacoes(client, dados):
    h = preparar_admin(client)
    assert client.get(f"/api/lotes/{dados['orig']}/destinacoes").json()[0]["descricao"] == "Reservado CPR"
    r = client.post(f"/api/lotes/{dados['orig']}/notas", json={"texto": "Comprar mais H13 em dezembro"}, headers=h)
    assert r.status_code == 201
    assert client.get(f"/api/lotes/{dados['orig']}/notas").json()[0]["usuario"] == "Administrador"
    assert client.post(f"/api/lotes/{dados['orig']}/notas", json={"texto": "x"}).status_code == 403  # sem CSRF


def test_mega_op(client):
    from datetime import date

    from app.integrations.mega import fabrica
    from app.integrations.mega.gateway import MegaFalso, OrdemProducao
    preparar_admin(client)
    assert client.get("/api/mega/op/100508").status_code == 503     # integração desligada no teste
    fabrica.definir(MegaFalso(ops=[OrdemProducao(100508, 68092, "SA PARTE/ACESSORIO (POS 1) 12X54X90MM", None, "AB",
                                                 None, 128, date(2026, 12, 9))]))
    try:
        r = client.get("/api/mega/op/100508").json()
        assert r["aberta"] is True and r["quantidade"] == 128 and r["data_recebimento"] == "2026-12-09"
        assert r["medida_sugerida"]["espessura"] == 12 and r["medida_sugerida"]["comprimento"] == 90
        assert client.get("/api/mega/op/1").status_code == 404
    finally:
        fabrica.definir(None)
