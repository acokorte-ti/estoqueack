"""R061 (chat BANCO E TESTES, 2026-11-17): o que faltava testar da 0009, do R058 e do §10.9 (spec v3.11).

Complementa `test_r058_peso_real.py` e `test_v311_correcoes_carga.py` (TÉCNICO). Dados fictícios.
- R058: limite exato (14 dias avisa, 15 bloqueia); prazo vem da T23; "para todos" inclui a Análise; o SA da peça
  inteira e a NF ficam com o previsto e só o lote RJ em Itu recebe o consumo real; encerrar fica na auditoria e não
  impede a T13 depois; dois "Encerrar" ao mesmo tempo (PostgreSQL): só um passa.
- §1.4 item 8 / §10.9 B (paridade manual, coluna da 0009): o item RJ fica na linha do item de Itu na T04, o lote RJ
  continua sem código do Mega, e sem a paridade as duas medidas ficam em linhas separadas.
"""
from __future__ import annotations

import threading

import pytest

from tests.conftest import PG
from tests.fluxo_util import catalogo_e_lotes, corpo_solicitacao, criar_usuarios, entrar, mega_falso
from tests.test_fluxo_itu_operacoes import _peca_inteira_recebida
from tests.test_r058_peso_real import _envelhecer

pytest.importorskip("fastapi")


@pytest.fixture()
def amb(client):
    u = criar_usuarios(client)
    ids = catalogo_e_lotes()
    fab = mega_falso()
    yield client, u, ids, fab
    fab.definir(None)


def _niveis(r) -> dict[str, str]:
    return {o["codigo"]: o["nivel"] for o in r.json()["ocorrencias"]}


def _validar(client, h, ids, op, **kw):
    r = client.post("/api/solicitacoes/validar", json=corpo_solicitacao(ids["l33"], op=op, **kw), headers=h)
    assert r.status_code == 200, r.text
    return _niveis(r)


def _definir_prazo(dias: int) -> None:
    from app.core.db import SessionLocal
    from app.models import Parametro
    with SessionLocal() as db:
        p = db.get(Parametro, "PENDENCIA_PESO_REAL_DIAS")
        if p is None:
            db.add(Parametro(chave="PENDENCIA_PESO_REAL_DIAS", valor=str(dias), tipo="NUMERO", descricao="teste"))
        else:
            p.valor = str(dias)
        db.commit()


# ---------------- R058: prazo ----------------

def test_r058_sete_dias_ainda_avisa_oito_bloqueia(amb):
    """'Mais de 14 dias' (era 7 até 2026-11-19): no 14º dia do recebimento ainda é aviso cinza; no 15º bloqueia."""
    client, u, ids, fab = amb
    _peca_inteira_recebida(client, u, ids, fab)
    h = entrar(client, u["itu"])
    _envelhecer(14)
    assert _validar(client, h, ids, 100600).get("PESO_REAL_AGUARDANDO") == "ALERTA"
    assert "PESO_REAL_PENDENTE" not in _validar(client, h, ids, 100600)
    _envelhecer(15)
    assert _validar(client, h, ids, 100600)["PESO_REAL_PENDENTE"] == "ERRO"


def test_r058_prazo_vem_da_t23(amb):
    client, u, ids, fab = amb
    _peca_inteira_recebida(client, u, ids, fab)
    _envelhecer(4)
    h = entrar(client, u["itu"])
    assert "PESO_REAL_PENDENTE" not in _validar(client, h, ids, 100601)          # 4 dias, prazo 7
    _definir_prazo(3)
    s = client.get("/api/pendencias-peso-real", headers=h).json()
    assert s["dias_limite"] == 3 and s["bloqueado"] is True and "mais de 3 dias" in s["mensagem"]
    assert _validar(client, h, ids, 100601)["PESO_REAL_PENDENTE"] == "ERRO"
    _definir_prazo(10)
    assert "PESO_REAL_PENDENTE" not in _validar(client, h, ids, 100601)


def test_r058_rascunho_gravado_antes_tambem_nao_e_enviado(amb):
    """O bloqueio é no "Enviar ao RJ", também quando se envia um rascunho que já existia (T08)."""
    client, u, ids, fab = amb
    _peca_inteira_recebida(client, u, ids, fab)
    h = entrar(client, u["itu"])
    r = client.post("/api/solicitacoes", json=corpo_solicitacao(ids["l33"], op=100602, enviar=False), headers=h)
    assert r.status_code == 201, r.text
    rid = r.json()["solicitacoes"][0]["id"]
    _envelhecer(16)
    r = client.post(f"/api/solicitacoes/{rid}/enviar", json={"confirmacoes": {}}, headers=h)
    assert r.status_code == 409 and _niveis(r)["PESO_REAL_PENDENTE"] == "ERRO", r.text
    assert client.get(f"/api/solicitacoes/{rid}", headers=h).json()["situacao"] == "RASCUNHO"


# ---------------- R058 (1): o SA não é corrigido ----------------

def test_r058_peso_real_da_t13_nao_muda_sa_nem_nf_so_o_lote_rj_em_itu(amb):
    from app.core.db import SessionLocal
    from app.models import CadastroSa, Lote, Movimento
    client, u, ids, fab = amb
    sid, lote_itu, previsto = _peca_inteira_recebida(client, u, ids, fab)
    with SessionLocal() as db:
        sa = db.query(CadastroSa).filter_by(solicitacao_id=sid).one()
        sa_antes = (sa.peso_kg, sa.quantidade, sa.sa_codigo, sa.nf_id)
        saldo_antes = float(db.get(Lote, lote_itu).saldo_kg)
    real = round(previsto * 1.06, 1)                          # pesou mais que o previsto (dentro dos 8 %)
    h = entrar(client, u["itu"])
    corpo = {"op": 100092, "lote_id": lote_itu, "consumo_kg": real, "sobra_kg": 300, "sobra_na_bitola": True,
             "pecas": 1, "peso_usado_kg": 1288, "confirmacoes": {"PERDA_CORTE_ALTA": "Barra com ponta torta"}}
    r = client.post("/api/cortes-itu", json=corpo, headers=h)
    assert r.status_code == 201, r.text
    assert r.json()["pendencia_peso_real_resolvida"] is True and r.json()["sa_id"] is None
    with SessionLocal() as db:
        sa = db.query(CadastroSa).filter_by(solicitacao_id=sid).one()
        assert (sa.peso_kg, sa.quantidade, sa.sa_codigo, sa.nf_id) == sa_antes
        assert float(sa.peso_kg) == pytest.approx(previsto)
        movs = db.query(Movimento).filter_by(lote_id=lote_itu).order_by(Movimento.id).all()
        saidas = [float(m.kg) for m in movs if float(m.kg) < 0]
        assert saidas and saidas[0] == pytest.approx(-real)                    # o consumo real sai do lote RJ em Itu
        lote = db.get(Lote, lote_itu)
        assert float(lote.saldo_kg) == pytest.approx(sum(float(m.kg) for m in movs))
        assert float(lote.saldo_kg) < saldo_antes
        assert lote.item.codigo_mega is None


def test_r058_encerrar_fica_na_auditoria_e_t13_continua_possivel(amb):
    from app.core.db import SessionLocal
    from app.models import Auditoria
    client, u, ids, fab = amb
    sid, lote_itu, previsto = _peca_inteira_recebida(client, u, ids, fab)
    _envelhecer(17)
    h = entrar(client, u["itu"])
    r = client.post(f"/api/pendencias-peso-real/{sid}/encerrar", json={"justificativa": "Peça vai para outra OP"},
                    headers=h)
    assert r.status_code == 200, r.text
    with SessionLocal() as db:
        a = db.query(Auditoria).filter_by(acao="PESO_REAL_PENDENCIA_ENCERRADA").one()
        assert a.entidade == "solicitacao" and a.entidade_id == str(sid)
        assert a.depois["justificativa"] == "Peça vai para outra OP"
    corpo = {"op": 100092, "lote_id": lote_itu, "consumo_kg": round(previsto, 1), "sobra_kg": 300,
             "sobra_na_bitola": True, "pecas": 1, "peso_usado_kg": 1288,
             "confirmacoes": {"PERDA_CORTE_ALTA": "Barra com ponta torta"}}
    r = client.post("/api/cortes-itu", json=corpo, headers=h)
    assert r.status_code == 201, r.text
    assert client.get(f"/api/solicitacoes/{sid}", headers=h).json()["situacao"] == "CONCLUIDA"
    s = client.get("/api/pendencias-peso-real", headers=h).json()
    assert s["quantidade"] == 0 and s["bloqueado"] is False


@pytest.mark.skipif(not PG, reason="trava (FOR UPDATE) só no PostgreSQL")
def test_r058_dois_encerrar_ao_mesmo_tempo_so_um_passa(amb):
    from fastapi.testclient import TestClient

    from app.core.db import SessionLocal
    from app.main import app
    from app.models import Auditoria
    client, u, ids, fab = amb
    sid, _, _ = _peca_inteira_recebida(client, u, ids, fab)
    _envelhecer(17)
    resultados: list[int] = []
    barreira = threading.Barrier(2)

    def encerrar(texto: str):
        with TestClient(app) as c:
            hh = entrar(c, u["itu"])
            barreira.wait(10)
            resultados.append(c.post(f"/api/pendencias-peso-real/{sid}/encerrar", json={"justificativa": texto},
                                     headers=hh).status_code)

    ts = [threading.Thread(target=encerrar, args=(f"Encerrada pelo teste {i}",)) for i in (1, 2)]
    for t in ts:
        t.start()
    for t in ts:
        t.join(30)
    assert sorted(resultados) == [200, 400], resultados
    with SessionLocal() as db:
        assert db.query(Auditoria).filter_by(acao="PESO_REAL_PENDENCIA_ENCERRADA").count() == 1


# ---------------- §1.4 item 8 / §10.9 B: paridade manual (item_mp.paridade_item_id, 0009) ----------------

def _itens_paridade(com_paridade: bool) -> tuple[int, int]:
    from app.core.db import SessionLocal
    from app.models import ItemMP, Liga
    from app.services import movimentos as mov
    with SessionLocal() as db:
        s5 = Liga(codigo="S5", nome="S5", densidade=7.8, apelidos=[])
        db.add(s5)
        db.flush()
        itu = ItemMP(descricao="IMP-S5 250X320MM", liga_id=s5.id, formato="RETANGULAR", espessura=250, largura=320,
                     codigo_mega=90824)
        db.add(itu)
        db.flush()
        rj = ItemMP(descricao="S5 250x320x4970", liga_id=s5.id, formato="RETANGULAR", espessura=250, largura=320,
                    paridade_item_id=itu.id if com_paridade else None)
        db.add(rj)
        db.flush()
        out = []
        for item, pf, kg in ((itu, "ITU", 800), (rj, "RJ", 300)):
            lote = mov.criar_lote(db, item=item, planta_fiscal=pf, local_fisico=pf, peso_inicial_kg=kg)
            mov.lancar(db, lote, "SALDO_INICIAL", kg, usuario_id=None)
            out.append(lote.id)
        db.commit()
        return out[0], out[1]


def _linhas_s5(client, h) -> list[dict]:
    r = client.get("/api/lotes/agrupado", params={"por_pagina": 200}, headers=h)
    assert r.status_code == 200, r.text
    return [g for g in r.json()["itens"] if g["liga"] == "S5"]


@pytest.mark.parametrize("com_paridade", [True, False])
def test_paridade_manual_poe_o_rj_na_linha_do_itu_sem_dar_codigo(client, com_paridade):
    u = criar_usuarios(client)
    l_itu, l_rj = _itens_paridade(com_paridade)
    h = entrar(client, u["itu"])
    linhas = _linhas_s5(client, h)
    if com_paridade:
        assert len(linhas) == 1
        g = linhas[0]
        assert g["paridade_manual"] is True and g["codigos_itu"] == [90824]
        assert g["por_estoque"]["ESTOQUE_MEGA"] == 800 and g["por_estoque"]["RJ_NO_RIO"] == 300
    else:                                     # o comprimento 4970 na descrição do RJ separa as linhas (P29)
        assert len(linhas) == 2 and not any(g["paridade_manual"] for g in linhas)
    lote_rj = client.get(f"/api/lotes/{l_rj}", headers=h).json()
    assert lote_rj["codigo_mega"] is None                         # v3.7: lote RJ nunca tem código do Mega
    assert client.get(f"/api/lotes/{l_itu}", headers=h).json()["codigo_mega"] == 90824
