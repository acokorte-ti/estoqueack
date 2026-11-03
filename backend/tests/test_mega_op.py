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
