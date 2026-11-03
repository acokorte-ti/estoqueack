"""OP no Mega: situações mapeadas em 2026-11-03 (AB/EN/CA/SI/PL/FP/LB), cliente e pedido (PRO_ORIGEM 'D')."""
from datetime import date

import pytest

from app.integrations.mega import consultas
from tests.fluxo_util import catalogo_e_lotes, corpo_solicitacao, criar_usuarios, entrar, mega_falso

pytest.importorskip("fastapi")


def test_situacoes_op_mapeadas():
    s = consultas.SITUACOES_OP
    assert s["AB"][1] is True
    assert s["EN"][1] is False and s["CA"][1] is False
    assert all(s[c][1] is None for c in ("SI", "PL", "FP", "LB"))


def test_consulta_op_traz_cliente_e_pedido():
    sql = consultas.ORDEM_PRODUCAO
    assert "PRO_ORIGEM" in sql and "ORI_CH_TIPOORIGEM = 'D'" in sql
    assert "AGN_ST_FANTASIA" in sql and "ORD_ST_ALTERNATIVO" in sql
    assert sql.count(":numero") == 2      # filtro também dentro da subconsulta de origem (desempenho)


def _op(numero, situacao):
    from app.integrations.mega.gateway import OrdemProducao
    return OrdemProducao(numero, 777, "PECA 30X100X250MM", "CLIENTE W", situacao, date(2026, 10, 1), 12,
                         date(2026, 12, 9), pedido="82403", cliente_codigo=1785, tipo="OP001")


@pytest.fixture()
def amb(client):
    u = criar_usuarios(client)
    ids = catalogo_e_lotes()
    fab = mega_falso(_op(200001, "EN"), _op(200002, "CA"), _op(200003, "FP"), _op(200004, "XX"))
    yield client, u, ids
    fab.definir(None)


@pytest.mark.parametrize("op,codigo", [(200001, "OP_ENCERRADA"), (200002, "OP_ENCERRADA"),
                                       (200003, "OP_NAO_ABERTA"), (200004, "OP_SITUACAO_DESCONHECIDA")])
def test_validacao_por_situacao(amb, op, codigo):
    client, u, ids = amb
    h = entrar(client, u["itu"])
    r = client.post("/api/solicitacoes/validar", json=corpo_solicitacao(ids["l33"], op=op), headers=h)
    assert r.status_code == 200, r.text
    codigos = [o["codigo"] for o in r.json()["ocorrencias"]]
    assert codigo in codigos
    nivel = {o["codigo"]: o["nivel"] for o in r.json()["ocorrencias"]}[codigo]
    assert nivel == ("ERRO" if codigo == "OP_ENCERRADA" else "ALERTA")


def test_rota_op_devolve_pedido_e_cliente(amb):
    client, u, _ = amb
    entrar(client, u["itu"])
    j = client.get("/api/mega/op/200003").json()
    assert j["pedido"] == "82403" and j["cliente_codigo"] == 1785 and j["tipo"] == "OP001"
    assert j["situacao_descricao"] == "Firme planejada" and j["aberta"] is None


def _estrutura(fab):
    from app.integrations.mega.gateway import ComponenteOp
    fab.obter().estruturas[200003] = [ComponenteOp(37983, "SA FACA TESOURA T1 - 32X99,5X155MM - CÓD.19918", "CO", "PC",
                                                   10, 1, 10)]
    fab.obter().estruturas[200001] = [ComponenteOp(5838, "IMP-A8 RETO", "MP", "KG", 80, 20, 80)]


def test_rota_op_traz_estrutura_sa_e_mp(amb):
    from app.integrations.mega import fabrica
    client, u, _ = amb
    _estrutura(fabrica)
    entrar(client, u["itu"])
    est = client.get("/api/mega/op/200003").json()["estrutura"]
    assert est[0]["codigo"] == 37983 and est[0]["tipo"] == "SA"
    est = client.get("/api/mega/op/200001").json()["estrutura"]
    assert est[0]["tipo"] == "MP" and est[0]["qtd_necessaria"] == 80


def test_sugestao_de_sa_vem_da_estrutura_da_op(amb):
    from app.core.db import SessionLocal
    from app.integrations.mega import fabrica
    from app.services import sas
    _estrutura(fabrica)
    with SessionLocal() as db:
        s = sas.sugerir(db, 19918, op=200003)
        assert s.codigo == 37983 and s.descricao.startswith("SA FACA")
        assert sas.sugerir(db, 19918, op=200001).codigo is None     # OP de MP Itu: sem SA na estrutura
        assert sas.sugerir(db, 19918).codigo is None                # sem OP e sem histórico
