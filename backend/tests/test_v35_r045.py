"""Spec v3.5 (R045, P22(a), P24, P26 decisões do Eduardo de 2026-11-11) e revisão da 0007 (R044).

Dados fictícios: OPs, contêineres e pesos de exemplo (nada de dado real)."""
from __future__ import annotations

import pytest

from app.domain import regras
from app.domain.medidas import bitola_de_origem, chave_multiplo, interpretar
from tests.fluxo_util import catalogo_e_lotes, corpo_solicitacao, criar_usuarios, entrar, mega_falso

pytest.importorskip("fastapi")


# ---------------- domínio ----------------

def test_cr8mod_e_liga_distinta_de_cr8():
    assert interpretar("IMP-CR8MOD 7,5X55MM").liga == "CR8MOD"
    assert interpretar("CR8 MOD 7,5X87MM").liga == "CR8MOD"
    assert interpretar("CR8  13X510").liga == "CR8"


def test_redondo_so_com_marcador():
    m = interpretar("D6 97X2660")
    assert (m.formato, m.espessura, m.largura) == ("RETANGULAR", 97, 2660)
    m = interpretar("IMP-D2 RED 90X2425MM")
    assert (m.formato, m.diametro, m.comprimento) == ("REDONDO", 90, 2425)


def test_chave_multiplo():
    assert chave_multiplo("A8 MOD 21x204x1110 Múltiplo") == "1110"
    assert chave_multiplo("D2 FLAT BAR 4,8X600 (MÚLTIPLO DE 2020MM)") == "2020"
    assert chave_multiplo("H13 50X610", "MULT. 1820") == "1820"
    assert chave_multiplo("H13 50X610", "3110MM (MIN)") is None
    assert chave_multiplo("IMP-A8 21X203MM") is None


def test_bitola_de_origem_normalizada():
    assert bitola_de_origem("IMP-D2 25X610MM", "D2") == bitola_de_origem("d2 25 x 610", "D2") == "25X610"
    assert bitola_de_origem("IMP-D2 30,5x610MM", "D2") == "30,5X610"
    assert bitola_de_origem("IMP-D2 36X510MM", "DC53") == "D2 36X510"
    assert bitola_de_origem("IMP-D2 45x510~610MM", "D2") == "IMP-D245X510~610MM"


def test_tolerancia_com_limite_na_mensagem():
    r = regras.validar_peso_real(100, 109, 8, limite_de="material do RJ")
    o = r.ocorrencias[0]
    assert o.codigo == "EXCESSO_TOLERANCIA" and "Limite: 8 % para material do RJ" in o.mensagem
    assert o.dados["limite_pct"] == 8
    assert not regras.validar_peso_real(100, 107.5, 8).ocorrencias


def test_barra_mais_leve_que_peca():
    o = regras.validar_barra_inteira(837, 800).ocorrencias
    assert [x.codigo for x in o] == ["BARRA_MAIS_LEVE_QUE_PECA"] and o[0].nivel.value == "ALERTA"
    assert not regras.validar_barra_inteira(837, 1288).ocorrencias


# ---------------- API ----------------

@pytest.fixture()
def amb(client):
    u = criar_usuarios(client)
    ids = catalogo_e_lotes()
    from app.core.db import SessionLocal
    from app.models import Lote
    from app.services import movimentos as mov
    with SessionLocal() as db:      # lote RJ em Itu, mesma liga e bitola do l33 (H13 33x105)
        item = db.get(Lote, ids["l33"]).item
        lote = mov.criar_lote(db, item=item, planta_fiscal="RJ", local_fisico="ITU", peso_inicial_kg=200)
        mov.lancar(db, lote, "SALDO_INICIAL", 200, usuario_id=None)
        db.commit()
        ids["litu"] = lote.id
    fab = mega_falso()
    yield client, u, ids, fab
    fab.definir(None)


def _codigos(v):
    return [o["codigo"] for o in v["ocorrencias"]]


def test_t13_oito_pct_no_material_rj_cinco_no_mega(amb):
    client, u, ids, _ = amb
    h = entrar(client, u["itu"])
    base = {"op": 100508, "pecas": 1, "previsto_kg": 100, "sobra_kg": 0}
    v = client.post("/api/cortes-itu/validar", headers=h,
                    json={**base, "lote_id": ids["litu"], "consumo_kg": 107, "peso_usado_kg": 110}).json()
    assert "EXCESSO_TOLERANCIA" not in _codigos(v) and v["resultado"]["tolerancia_excesso_pct"] == 8
    v = client.post("/api/cortes-itu/validar", headers=h,
                    json={**base, "lote_id": ids["litu"], "consumo_kg": 109, "peso_usado_kg": 110}).json()
    exc = next(o for o in v["ocorrencias"] if o["codigo"] == "EXCESSO_TOLERANCIA")
    assert "8 % para material do RJ" in exc["mensagem"]
    v = client.post("/api/cortes-itu/validar", headers=h,
                    json={**base, "lote_id": ids["lmega"], "consumo_kg": 107, "peso_usado_kg": 110}).json()
    assert "EXCESSO_TOLERANCIA" in _codigos(v) and v["resultado"]["tolerancia_excesso_pct"] == 5


def test_t13_limite_rj_vem_do_parametro(amb):
    client, u, ids, _ = amb
    from app.core.db import SessionLocal
    from app.models import Parametro
    with SessionLocal() as db:
        db.add(Parametro(chave="TOLERANCIA_EXCESSO_RJ_INTEIRO_PCT", valor="10", tipo="NUMERO", descricao="t"))
        db.commit()
    h = entrar(client, u["itu"])
    v = client.post("/api/cortes-itu/validar", headers=h, json={"op": 100508, "pecas": 1, "previsto_kg": 100,
                                                                "lote_id": ids["litu"], "consumo_kg": 109,
                                                                "peso_usado_kg": 110}).json()
    assert "EXCESSO_TOLERANCIA" not in _codigos(v)


def test_sugestao_agrupada_por_liga_e_bitola(amb):
    client, u, ids, _ = amb
    h = entrar(client, u["itu"])
    r = client.get("/api/lotes/compativeis", headers=h,
                   params={"liga": "H13", "formato": "RETANGULAR", "espessura": 30, "largura": 100,
                           "comprimento": 250, "quantidade": 12, "peso_necessario_kg": 1700}).json()
    g = next(x for x in r["grupos"] if x["liga"] == "H13" and x["bitola"] == "33X105")
    assert g["estoques"]["RJ_NO_RIO"]["disponivel_kg"] == 1400 and g["estoques"]["ITU"]["disponivel_kg"] == 200
    assert g["total_disponivel_kg"] == 1600 and g["falta_kg"] == 100 and "falta 100,0 kg" in g["frase"]
    assert {x["conteiner"] for x in g["estoques"]["RJ_NO_RIO"]["lotes"]} == {"CH33K", "CH40SH"}
    eq = next(x for x in r["grupos"] if x["liga"] == "1.2344")
    assert eq["liga_equivalente"] is True and r["grupos"][-1]["liga_equivalente"] is True
    assert {x["bitola"] for x in r["grupos"] if x["liga"] == "H13"} >= {"33X105", "70X610"}   # nunca se juntam


def test_consumo_misto_sem_op_duplicada_e_marca(amb):
    client, u, ids, _ = amb
    h = entrar(client, u["itu"])
    c = client.post("/api/cortes-itu", headers=h, json={"op": 100592, "lote_id": ids["litu"], "consumo_kg": 40,
                                                        "peso_usado_kg": 40, "pecas": 2, "consumo_misto": True})
    assert c.status_code == 201, c.text
    assert c.json()["consumo_misto"] is True and c.json()["sa_id"]          # parte de Itu: caminho B2
    sem = client.post("/api/solicitacoes/validar", headers=h, json=corpo_solicitacao(ids["l33"])).json()
    assert "OP_DUPLICADA" in _codigos(sem)
    corpo = corpo_solicitacao(ids["l33"], consumo_misto=True)
    com = client.post("/api/solicitacoes/validar", headers=h, json=corpo).json()
    assert "OP_DUPLICADA" not in _codigos(com)
    r = client.post("/api/solicitacoes", headers=h, json={**corpo, "confirmacoes": {
        o["codigo"]: "ok" for o in com["ocorrencias"] if o["nivel"] == "CIENCIA"}})
    assert r.status_code == 201, r.text
    s = r.json()["solicitacoes"][0]
    assert s["consumo_misto"]["itu_kg"] == 40 and s["consumo_misto"]["rj_kg"] == s["peso_previsto_kg"]
    assert s["consumo_misto"]["texto"].startswith("OP com consumo misto: Itu 40,0 kg + RJ ")
    lista = client.get("/api/solicitacoes", headers=h, params={"op": 100592}).json()
    assert lista["itens"][0]["consumo_misto"]["itu_kg"] == 40


# ---------------- carga ----------------

def test_estoque_geral_com_nome_variavel(tmp_path):
    from app.carga import planilhas as P
    (tmp_path / "Materia Prima Geral 05nov.xlsx").write_bytes(b"")
    (tmp_path / "~$Materia Prima Geral 05nov.xlsx").write_bytes(b"")
    assert P.arquivo_geral(tmp_path) == "Materia Prima Geral 05nov.xlsx"
    (tmp_path / "Materia Prima Geral 20out.xlsx").write_bytes(b"")
    with pytest.raises(P.EstruturaMudou):
        P.arquivo_geral(tmp_path)


# ---------------- R044: pendencia_mega ----------------

def test_uma_entrada_aberta_por_codigo(client):
    from sqlalchemy.exc import IntegrityError

    from app.core.db import SessionLocal
    from app.models import PendenciaMega
    with SessionLocal() as db:
        db.add(PendenciaMega(tipo="ENTRADA", codigo=4242, kg=10, situacao="ABERTA"))
        db.add(PendenciaMega(tipo="ENTRADA", codigo=4242, kg=10, situacao="DESCARTADA", motivo="OUTRO"))
        db.commit()
        db.add(PendenciaMega(tipo="ENTRADA", codigo=4242, kg=12, situacao="ABERTA"))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        db.add(PendenciaMega(tipo="ENTRADA", codigo=4243, kg=12, situacao="XPTO"))
        with pytest.raises(IntegrityError):
            db.commit()
