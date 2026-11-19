"""Spec v3.13 (R063) e R065: regra do RETO na sobra da T13, código do SA pela Análise (P36), correções da carga
(P37(a) Planilha1, prazo sem ano, consumo em outro material), totais da T16 e código de Itu da paridade manual.

Dados fictícios (contêineres CTxx, OPs 7xxxx/100508, códigos 9xxxx/78290 do fluxo_util)."""
from __future__ import annotations

from datetime import date

import pytest

from app.carga import correcoes as C
from app.carga import planilhas as P
from app.domain.regras import regra_reto
from tests.fluxo_util import catalogo_e_lotes, criar_usuarios, entrar, mega_falso
from tests.test_v311_correcoes_carga import _c, _e, _montar

pytest.importorskip("fastapi")


# ---------------- regra do RETO (domínio) ----------------

@pytest.mark.parametrize("esp,larg,vai", [(40, 180, True), (40, 200, False), (60, 240, True), (60, 250, False),
                                          (50, 199.9, True), (50, 200, False), (50.5, 249, True)])
def test_regra_reto_exemplos_da_spec(esp, larg, vai):
    ok, regra, resultado = regra_reto(esp, larg, 50, 200, 250)
    assert ok is vai
    assert "espessura até 50 mm → largura abaixo de 200 mm" in regra
    assert ("vai para RETO" in resultado) and (("não vai" in resultado) is (not vai))


# ---------------- T13 (API) ----------------

@pytest.fixture()
def amb(client):
    u = criar_usuarios(client)
    ids = catalogo_e_lotes()
    fab = mega_falso()
    yield client, u, ids, fab
    fab.definir(None)


def _corpo(lote_id, **kw):
    return {"op": 100508, "lote_id": lote_id, "consumo_kg": 104.5, "sobra_kg": 12, "sobra_na_bitola": False,
            "pecas": 128, "peso_usado_kg": 117, **kw}


def _codigos(v):
    return {o["codigo"]: o for o in v["ocorrencias"]}


def test_t13_sobra_fora_da_bitola_exige_medida_e_conferencia(amb):
    client, u, ids, _ = amb
    h = entrar(client, u["itu"])
    v = client.post("/api/cortes-itu/validar", json=_corpo(ids["lmega"]), headers=h).json()
    oc = _codigos(v)
    assert oc["MEDIDA_SOBRA_OBRIGATORIA"]["nivel"] == "ERRO" and oc["REGRA_RETO_NAO_CONFERIDA"]["nivel"] == "ERRO"
    assert v["resultado"]["regra_reto"]["texto_regra"].startswith("Regra do RETO")
    r = client.post("/api/cortes-itu", json=_corpo(ids["lmega"], sobra_espessura_mm=40, sobra_largura_mm=180),
                    headers=h)
    assert r.status_code == 409 and "REGRA_RETO_NAO_CONFERIDA" in r.text
    # sobra na bitola: nada muda (sem E × L nem caixa)
    v = client.post("/api/cortes-itu/validar", json=_corpo(ids["lmega"], sobra_na_bitola=True), headers=h).json()
    assert v["resultado"]["regra_reto"] is None and "REGRA_RETO_NAO_CONFERIDA" not in _codigos(v)


def test_t13_fora_da_regra_vira_lote_novo_no_codigo_de_origem(amb):
    from app.core.db import SessionLocal
    from app.models import MegaSaldo
    client, u, ids, _ = amb
    with SessionLocal() as db:
        db.add(MegaSaldo(codigo=78290, saldo_kg=5198.0 - 105, descricao="IMP-H13 24X62MM"))
        db.commit()
    h = entrar(client, u["itu"])
    corpo = _corpo(ids["lmega"], sobra_espessura_mm=40, sobra_largura_mm=200, conferi_regra_reto=True)
    v = client.post("/api/cortes-itu/validar", json=corpo, headers=h).json()
    rr = v["resultado"]["regra_reto"]
    assert rr["destino"] == "LOTE_NOVO" and rr["vai_para_reto"] is False and rr["limites"]["esp_limite_mm"] == 50
    assert "não vai para RETO" in rr["texto_resultado"] and _codigos(v)["REGRA_RETO"]["nivel"] == "ALERTA"
    assert "Novo lote H13 40X200 com 12,0 kg" in v["resultado"]["frase"]
    assert v["resultado"]["instrucao_mega"] == "Baixar 105,0 kg do código 78290 na OP 100508."   # sem transferência
    r = client.post("/api/cortes-itu", json=corpo, headers=h)
    assert r.status_code == 201, r.text
    c = r.json()
    assert c["lote_reto"] is None and c["sobra_destino"] == "LOTE_NOVO" and c["lote_sobra"]["bitola"] == "40X200"
    assert c["sobra_espessura_mm"] == 40 and c["sobra_largura_mm"] == 200
    novo = client.get(f"/api/lotes/{c['lote_sobra']['id']}").json()
    assert novo["tipo"] == "SOBRA" and novo["estoque"] == "ESTOQUE_MEGA" and novo["saldo_kg"] == 12
    assert novo["codigo_mega"] == 78290                    # o kg continua no código do lote de origem no Mega
    entrar(client, u["analise"])
    t16 = client.get("/api/conciliacao").json()
    it = next(x for x in t16["itens"] if x["codigo"] == 78290)
    assert it["soma_lotes_kg"] == pytest.approx(5198 - 105) and it["status"] == "OK" and it["lotes"] == 2
    # o próximo corte do lote novo baixa do código de origem
    h = entrar(client, u["itu"])
    v = client.post("/api/cortes-itu/validar", headers=h,
                    json={"op": 100508, "lote_id": c["lote_sobra"]["id"], "consumo_kg": 12, "pecas": 1}).json()
    assert v["resultado"]["instrucao_mega"] == "Baixar 12,0 kg do código 78290 na OP 100508."


def test_t13_limites_vem_da_t23(amb):
    from app.core.db import SessionLocal
    from app.models import Parametro
    client, u, ids, _ = amb
    with SessionLocal() as db:
        db.add(Parametro(chave="RETO_LARG_MAX_ATE_LIMITE", valor="210", tipo="NUMERO", descricao="teste"))
        db.commit()
    h = entrar(client, u["itu"])
    v = client.post("/api/cortes-itu/validar", headers=h,
                    json=_corpo(ids["lmega"], sobra_espessura_mm=40, sobra_largura_mm=200,
                                conferi_regra_reto=True)).json()
    assert v["resultado"]["regra_reto"]["destino"] == "RETO"
    assert "Transferir 12,0 kg" in v["resultado"]["instrucao_mega"]
    v = client.post("/api/cortes-itu/validar", headers=h,
                    json=_corpo(ids["lmega"], sobra_espessura_mm=200, sobra_largura_mm=40,
                                conferi_regra_reto=True)).json()
    assert "MEDIDA_SOBRA_INVERTIDA" in _codigos(v)


def test_t13_redondo_sobra_fica_no_lote(amb):
    """Eduardo, 2026-11-19 (pendências item 2): o redondo nunca sai da bitola; a sobra fica no lote."""
    from app.core.db import SessionLocal
    from app.models import ItemMP, Liga
    from app.services import movimentos as mov
    client, u, ids, _ = amb
    with SessionLocal() as db:
        h13 = db.query(Liga).filter_by(codigo="H13").one()
        it = ItemMP(descricao="H13 Ø100", liga_id=h13.id, formato="REDONDO", diametro=100)
        db.add(it)
        db.flush()
        lote = mov.criar_lote(db, item=it, planta_fiscal="RJ", local_fisico="ITU", peso_inicial_kg=300)
        mov.lancar(db, lote, "ENTRADA", 300, usuario_id=None)
        db.commit()
        lid = lote.id
    h = entrar(client, u["itu"])
    base = {"op": 100508, "lote_id": lid, "consumo_kg": 100, "sobra_kg": 50, "sobra_na_bitola": False,
            "peso_usado_kg": 155, "pecas": 1, "conferi_regra_reto": True}
    v = client.post("/api/cortes-itu/validar", json=base, headers=h).json()
    assert "SOBRA_REDONDO_NA_BITOLA" in _codigos(v) and v["resultado"]["regra_reto"]["aplicavel"] is False
    r = client.post("/api/cortes-itu", json={**base, "sobra_vai_para_reto": True}, headers=h)
    assert r.status_code == 409 and "SOBRA_REDONDO_NA_BITOLA" in r.text
    r = client.post("/api/cortes-itu", json={**base, "sobra_na_bitola": True}, headers=h)
    assert r.status_code == 201, r.text
    c = r.json()
    assert not c.get("lote_sobra") and not c.get("lote_reto")
    assert client.get(f"/api/lotes/{lid}").json()["saldo_kg"] == 195     # 300 − 155 usados + 50 de sobra no lote


# ---------------- R065(2) e R065(4) ----------------

def test_conciliacao_totais_de_todos_os_codigos(amb):
    from app.core.db import SessionLocal
    from app.models import MegaSaldo
    client, u, ids, _ = amb
    with SessionLocal() as db:
        db.add(MegaSaldo(codigo=78290, saldo_kg=5198.0, descricao="IMP-H13 24X62MM"))
        db.commit()
    entrar(client, u["analise"])
    todos = client.get("/api/conciliacao").json()
    so_div = client.get("/api/conciliacao", params={"somente_divergentes": True}).json()
    assert so_div["itens"] == [] and so_div["totais"] == todos["totais"]
    assert todos["totais"]["ok"] == 1 and todos["totais"]["saldo_mega_kg"] == 5198


def test_agrupado_mostra_codigo_da_paridade_manual_sem_lote_no_estoque_mega(amb):
    from app.core.db import SessionLocal
    from app.models import ItemMP, Liga
    from app.services import movimentos as mov
    client, u, ids, _ = amb
    with SessionLocal() as db:
        s5 = Liga(codigo="S5", nome="S5", densidade=7.76)
        db.add(s5)
        db.flush()
        itu = ItemMP(descricao="IMP-S5 250X320MM", liga_id=s5.id, formato="RETANGULAR", espessura=250, largura=320,
                     codigo_mega=96001)
        db.add(itu)
        db.flush()
        rj = ItemMP(descricao="S5 250x320x4970", liga_id=s5.id, formato="RETANGULAR", espessura=250, largura=320,
                    paridade_item_id=itu.id)
        db.add(rj)
        db.flush()
        lote = mov.criar_lote(db, item=rj, planta_fiscal="RJ", local_fisico="RJ", peso_inicial_kg=900)
        mov.lancar(db, lote, "ENTRADA", 900, usuario_id=None)
        db.commit()
    entrar(client, u["itu"])
    r = client.get("/api/lotes/agrupado", params={"liga": "S5"}).json()
    linhas = r["itens"] if isinstance(r, dict) else r
    linha = next(x for x in linhas if x["paridade_manual"])
    assert linha["codigos_itu"] == [96001]


# ---------------- carga ----------------

def _p1(linha, op, mp, ct, peso2=98.5):
    return P.LinhaCorte(linha, date(2025, 9, 11), op, str(op), 1, "5X69X471", 50, mp, ct, None, "INFORMAR APÓS CORTE",
                        "CLIENTE X", "50 PEÇAS", None, date(2025, 10, 7), 50, date(2025, 9, 18), "-", peso2, False,
                        False, None, {"arquivo": P.ARQ_CORTE, "aba": P.ABA_PLANILHA1, "linha": linha})


def test_carga_planilha1_so_com_correcao_e_concluida():
    est = [_e(10, "CT01", "A8 6X74", 500, 400)]
    corr = {"corte_planilha1": [{"linha": 4, "op": 70001, "conteiner": "CT01", "fonte": "P37(a) teste"}]}
    assert C.linhas_planilha1(corr) == {4}
    pl = _montar(est, corte=[_p1(4, 70001, "A8 6X74", "CT01")], corr=corr)
    s = next(x for x in pl.solicitacoes if x.op == 70001)
    assert s.situacao == "CONCLUIDA" and s.liberacoes[0].peso_kg == 98.5
    assert sum(len(lp.movimentos) for lp in pl.lotes) == len(pl.lotes[0].movimentos)   # saldo não muda
    assert not [p for p in pl.pendencias if p.tipo == "CORRECAO_NAO_APLICADA"]
    # OP errada na correção → bloqueia; sem correção a linha da Planilha1 não entra
    pl = _montar(est, corte=[_p1(4, 70001, "A8 6X74", "CT01")],
                 corr={"corte_planilha1": [{"linha": 4, "op": 70002}]})
    assert [p for p in pl.pendencias if p.tipo == "CORRECAO_NAO_APLICADA"]
    assert not [x for x in pl.solicitacoes if x.op == 70001]
    pl = _montar(est, corte=[_p1(4, 70001, "A8 6X74", "CT01")])
    assert not [x for x in pl.solicitacoes if x.op == 70001]


def test_carga_prazo_sem_ano_vai_para_o_ano_seguinte():
    import dataclasses
    est = [_e(10, "CT01", "H13 30X100", 900, 800)]
    longe = dataclasses.replace(_c(20, 70010, "H13 30X100", "CT01", cortadas=None, obs="-"),
                                data=date(2026, 11, 16), prazo=date(2026, 1, 10), liberacao_feita=False,
                                recebido=False, status="Normal")
    perto = dataclasses.replace(longe, linha=21, op=70011, prazo=date(2026, 9, 1))
    pl = _montar(est, corte=[longe, perto])
    prazos = {s.op: s.prazo for s in pl.solicitacoes}
    assert prazos == {70010: date(2027, 1, 10), 70011: date(2026, 9, 1)}
    assert [p.tipo for p in pl.pendencias].count("PRAZO_ANO_CORRIGIDO") == 1


def test_carga_consumo_em_outro_material_do_conteiner():
    est = [_e(10, "CT01", "H13 50X410", 900, 373, consumos=[(527, 70020, "H10")]),
           _e(11, "CT01", "H13 50X460", 600, 600)]
    pl = _montar(est, corte=[_c(20, 70020, "H13 50X460", "CT01", peso2=527)])
    assert [p for p in pl.pendencias if p.tipo == "CONSUMO_EM_OUTRO_MATERIAL"]
