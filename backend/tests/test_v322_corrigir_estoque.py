"""Spec v3.22 T27 (Eduardo, 2026-11-25): "Corrigir estoque", só Admin. Lista os lotes que não são do Estoque Mega e
corrige tudo no sistema, sem justificativa obrigatória; liga e bitola avisam que mudam a busca do Pedir corte."""
import pytest

from tests.fluxo_util import catalogo_e_lotes, criar_usuarios, entrar, mega_falso

pytest.importorskip("fastapi")

URL = "/api/admin/lotes/{}/correcao"


@pytest.fixture()
def amb(client):
    u = criar_usuarios(client)
    ids = catalogo_e_lotes()
    fab = mega_falso()
    from app.core.db import SessionLocal
    from app.models import Liga
    with SessionLocal() as db:
        db.add(Liga(codigo="D2", nome="D2", densidade=7.7, apelidos=[]))
        db.commit()
    yield client, u, ids
    fab.definir(None)


def _cod(o):
    return {x["codigo"] for x in o["ocorrencias"]}


def test_so_admin_e_so_fora_do_estoque_mega(amb):
    client, u, ids = amb
    for perfil in ("itu", "rj", "analise", "financeiro"):
        entrar(client, u[perfil])
        assert client.get("/api/admin/estoque").status_code == 403, perfil
        assert client.post(URL.format(ids["l33"]) + "/validar", json={"saldo_kg": 1}).status_code == 403, perfil
    entrar(client, u["admin"])
    r = client.get("/api/admin/estoque").json()
    lotes = {x["id"]: x for x in r["itens"]}
    assert ids["lmega"] not in lotes and {ids["l33"], ids["l70"], ids["l33b"], ids["l2344"]} <= set(lotes)
    x = lotes[ids["l33"]]
    assert x["estoque"] == "RJ_NO_RIO" and x["espessura"] == 33 and x["corrigido"] is False
    assert client.get("/api/admin/estoque", params={"conteiner": "CH25K"}).json()["total"] == 1


def test_saldo_vira_ajuste_e_sem_justificativa(amb):
    from app.core.db import SessionLocal
    from app.models import Lote, Movimento, Nota
    client, u, ids = amb
    h = entrar(client, u["admin"])
    p = client.post(URL.format(ids["l33"]) + "/validar", json={"saldo_kg": 950}, headers=h).json()
    assert _cod(p) == {"AJUSTE_SALDO"} and "1.000,0 kg → 950,0 kg" in p["resultado"]["frase"]
    r = client.post(URL.format(ids["l33"]), json={"saldo_kg": 950}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["lote"]["saldo_kg"] == 950 and r.json()["lote"]["corrigido"] is True
    with SessionLocal() as db:
        m = db.get(Movimento, r.json()["movimento_id"])
        assert m.tipo == "AJUSTE_INVENTARIO" and m.kg == -50 and m.justificativa
        lote = db.get(Lote, ids["l33"])
        assert sum(x.kg for x in db.query(Movimento).filter_by(lote_id=lote.id)) == pytest.approx(lote.saldo_kg)
        assert any("Correção manual" in n.texto for n in db.query(Nota).filter_by(entidade_id=lote.id))
        from app.carga.__main__ import correcoes_manuais
        assert correcoes_manuais(db) == 1


def test_liga_e_medida_avisam_a_busca_e_nao_mexem_no_item_dos_outros_lotes(amb):
    from app.core.db import SessionLocal
    from app.models import Lote
    client, u, ids = amb
    h = entrar(client, u["admin"])
    corpo = {"liga": "d2", "espessura": 34, "conteiner": "ch99z", "descricao": "D2 34x105"}
    p = client.post(URL.format(ids["l33"]) + "/validar", json=corpo, headers=h).json()
    assert {"LIGA_ALTERADA", "MEDIDA_ALTERADA", "DESCRICAO_ALTERADA", "CONTEINER_NOVO"} <= _cod(p)
    liga = next(o for o in p["ocorrencias"] if o["codigo"] == "LIGA_ALTERADA")["mensagem"]
    assert "H13 33X105" in liga and "D2 34X105" in liga and not [o for o in p["ocorrencias"] if o["nivel"] != "ALERTA"]
    r = client.post(URL.format(ids["l33"]), json=corpo, headers=h)
    assert r.status_code == 200, r.text
    x = r.json()["lote"]
    assert (x["liga"], x["bitola"], x["conteiner"], x["descricao"]) == ("D2", "34X105", "CH99Z", "D2 34x105")
    with SessionLocal() as db:
        novo, outro = db.get(Lote, ids["l33"]), db.get(Lote, ids["l33b"])
        assert novo.item_mp_id != outro.item_mp_id
        assert (outro.item.liga.codigo, outro.item.espessura) == ("H13", 33)      # o lote do mesmo item não mudou
        assert novo.item.codigo_mega is None
    # a mesma correção em outro lote reaproveita o item criado
    r = client.post(URL.format(ids["l33b"]), json={"liga": "D2", "espessura": 34, "descricao": "D2 34x105"},
                    headers=h)
    with SessionLocal() as db:
        assert db.get(Lote, ids["l33b"]).item_mp_id == db.get(Lote, ids["l33"]).item_mp_id


def test_bloqueios(amb):
    client, u, ids = amb
    h = entrar(client, u["admin"])
    assert "LOTE_ESTOQUE_MEGA" in _cod(client.post(URL.format(ids["lmega"]) + "/validar", json={"saldo_kg": 1},
                                                  headers=h).json())
    assert _cod(client.post(URL.format(ids["l33"]) + "/validar", json={"saldo_kg": 1000}, headers=h).json()) \
        == {"SEM_MUDANCA"}
    r = client.post(URL.format(ids["l33"]), json={"liga": "XYZ9"}, headers=h)
    assert r.status_code == 409 and "LIGA_INEXISTENTE" in _cod(r.json())
    r = client.post(URL.format(ids["l33"]), json={"formato": "REDONDO"}, headers=h)
    assert r.status_code == 409 and "MEDIDA_FALTANDO" in _cod(r.json())
    p = client.post(URL.format(ids["l33"]) + "/validar", json={"local_fisico": "ITU"}, headers=h).json()
    assert "LOCAL_ALTERADO" in _cod(p)
