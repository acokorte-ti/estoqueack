"""Spec v3.11 §10.9 e §1.4 itens 7–8 (decisões de 2026-11-17): correções da carga antes da recarga.

Dados fictícios (contêineres CTxx, OPs 7xxxx, códigos 9xxxx). Cobre: faixa da seção pelo maior valor (R057 item 1),
arquivo de correções (`leitura`, `consumo_sem_op`, `paridade_manual`, `avisos`), B05 (contêiner do Controle de Corte
pelo da ESTOQUE 2026/SA), B07 (corte dividido), B08 (peso inicial = packing list) e B09 (restrição no item).
"""
from __future__ import annotations

from datetime import date

import pytest

from app.carga import planilhas as P
from app.carga import plano
from app.domain.medidas import comprimento_texto, faixa_na_secao, interpretar

HOJE = date(2026, 11, 17)
ORIG_E = {"arquivo": P.ARQ_ESTOQUE, "aba": "ESTOQUE 2026"}


def _e(linha, ct, mat, peso_ini, total, consumos=()):
    cs = [P.Consumo(kg, f"H{linha}", f"OP {op}\n10/10" if op else "OP -\n10/10", [op] if op else [],
                    [str(op)] if op else [], False, (10, 10), {**ORIG_E, "linha": linha, "celula": cel})
          for kg, op, cel in consumos]
    return P.LinhaEstoque2026(linha, ct, mat, None, 1, peso_ini, total, cs, None, {**ORIG_E, "linha": linha})


def _h(linha, ct, desc, kg, data=date(2025, 3, 1)):
    return {"linha": linha, "data": data, "conteiner": ct, "descricao": desc, "pecas": 1, "entrada": kg,
            "sucata": None, "estoque": None, "obs": None, "historico": None,
            "origem": {"arquivo": P.ARQ_ESTOQUE, "aba": "HISTORICO", "linha": linha}}


def _g(linha, cod, desc, rio=0.0, itu=0.0, obs_rj=None, mega=0.0):
    return P.LinhaGeral(linha, cod, desc, None, mega, rio, itu, obs_rj, None, None, None, [],
                        {"arquivo": "Materia Prima Geral x.xlsx", "aba": "Estoque Geral", "linha": linha})


def _c(linha, op, mp, ct, peso=None, peso2=None, cortadas=1, obs="COP 900"):
    return P.LinhaCorte(linha, date(2026, 10, 1), op, str(op), 1, "10X10X10", 1, mp, ct, peso, None, "CLIENTE X",
                        "01 PEÇA", None, None, cortadas, date(2026, 10, 10), obs, peso2, True, True, "Recebido",
                        {"arquivo": P.ARQ_CORTE, "aba": "CONTROLE - CORTE RJ", "linha": linha})


def _sa(linha, op, mat, dim, ct, peso=10.0, sa=95001):
    return P.LinhaSa(date(2026, 10, 11), op, "CLIENTE X", 1, mat, dim, ct, 1, peso, None, sa, str(sa), None, None,
                     None, None, None, {}, {"arquivo": P.ARQ_SA, "aba": "2025", "linha": linha})


def _montar(est, hist=(), geral=(), corte=(), sas=(), corr=None):
    ctx = plano.Contexto({}, {}, None, lambda _o: None, HOJE, correcoes=corr or {})
    return plano.montar(ctx, list(est), list(hist), list(geral), list(corte), list(sas))


def _bloqueios(pl):
    return [p.descricao for p in pl.pendencias if p.tipo == "CORRECAO_NAO_APLICADA"]


# ---------------- §1.4 item 7: faixa na seção ----------------

@pytest.mark.parametrize("desc,esp,larg", [
    ("IMP-A8 26X500~610MM", 26, 610), ("IMP-D2 15X510-620MM", 15, 620), ("IMP-A8 38X(400-600)MM", 38, 600),
    ("CR12MOV SHEET 3X(700-800)", 3, 800), ("H13 50x410-460x2210-5505", 50, 460)])
def test_faixa_da_secao_vale_o_maior(desc, esp, larg):
    m = interpretar(desc)
    assert (m.espessura, m.largura) == (esp, larg)
    assert faixa_na_secao(desc)


def test_faixa_do_comprimento_continua_faixa():
    assert comprimento_texto("H13 50x410-460x2210-5505", "RETANGULAR") == "2210-5505"
    assert comprimento_texto("A8 MOD 21X203X1110-3347", "RETANGULAR") == "1110-3347"
    assert interpretar("A8 MOD 21X203X1110-3347").largura == 203
    assert faixa_na_secao("A8 MOD 21X203X1110-3347") is None and faixa_na_secao("K-100 20X100") is None


def test_faixa_anotada_no_lote():
    pl = _montar([_e(5, "CT01X", "A8 26x500~610", 100, 100)])
    lote = pl.lotes[0]
    assert pl.itens[lote.item].largura == 610
    assert any("Faixa na medida da planilha: 26X500~610" in n for n in lote.notas)


def test_lista_na_secao_vale_o_maior_e_fica_na_nota():
    # Eduardo, 2026-11-19 (pendências de 18/11 item 12): lista de larguras com "/" = um lote só, com a MAIOR
    pl = _montar([], geral=[_g(9, None, "H13 20x400/450/500", itu=150)])
    lote = next(lp for lp in pl.lotes if lp.estoque == "RJ_EM_ITU")
    it = pl.itens[lote.item]
    assert (it.espessura, it.largura, lote.saldo) == (20, 500, 150)
    assert plano.chave_mat(it.descricao).texto == "H13 20X500"
    assert lote.notas == ["Lista de medidas da planilha: 20X400/450/500 (vale o maior valor: H13 20X500)."]


# ---------------- arquivo de correções ----------------

def test_leitura_troca_liga_e_conteiner_e_bloqueia_se_nao_casar():
    est = [_e(5, "CT01X", "1.2746 65X600", 1000, 1000), _e(6, "CT09Z", "S5 6X450", 50, 50)]
    hist = [_h(9, "CT01X", "H13 65X600X4500", 1000), _h(10, "CT02X", "?", 300), _h(11, "CT03X", "S5 6X450", 50)]
    corr = {"leitura": [
        {"aba": "ESTOQUE 2026", "conteiner": "CT01X", "liga_planilha": "1.2746", "liga_correta": "H13",
         "esperado": 1, "fonte": "teste"},
        {"aba": "HISTORICO", "linhas": [10], "descricao_planilha": "?", "descricao_correta": "CR8 12,7X51",
         "fonte": "teste"},
        {"aba": "ESTOQUE 2026", "conteiner": "CT09Z", "descricao_planilha": "S5 6X450", "conteiner_correto": "CT03X",
         "fonte": "teste"}]}
    pl = _montar(est, hist, corr=corr)
    assert not _bloqueios(pl)
    l5 = next(lp for lp in pl.lotes if lp.origem.get("linha") == 5)
    assert pl.itens[l5.item].liga == "H13"
    assert l5.movimentos[0].data == date(2025, 3, 1)               # agora casa com o HISTORICO (data de entrada)
    assert any("na planilha \"1.2746 65X600\"" in n for n in l5.notas)
    l6 = next(lp for lp in pl.lotes if lp.origem.get("linha") == 6)
    assert l6.conteiner == "CT03X"
    assert any(pl.itens[lp.item].liga == "CR8" for lp in pl.lotes if lp.conteiner == "CT02X")
    # não casa (esperado 2, casou 1) → BLOQUEIA
    corr["leitura"][0]["esperado"] = 2
    pl = _montar(est, hist, corr=corr)
    assert len(_bloqueios(pl)) == 1
    from app.carga import gravar as G
    with pytest.raises(G.CargaRecusada):
        G.gravar(None, pl, usuario_id=None, arquivos={})


def test_consumo_sem_op_e_paridade_manual_e_aviso():
    est = [_e(5, "CT01X", "A8 MOD 22x45", 500, 100, [(400, 989999, "J5")]),
           _e(6, "CT02X", "S5 250x320x4970", 300, 300)]
    geral = [_g(20, 90824, "IMP-S5 250X320MM", rio=300), _g(21, 90825, "IMP-H13 RETO", itu=50)]
    corr = {"consumo_sem_op": [{"celula": "J5", "op_planilha": 989999, "fonte": "teste"}],
            "paridade_manual": [{"descricao_rj": "S5 250x320x4970", "codigo_itu": 90824,
                                 "descricao_itu": "IMP-S5 250X320MM", "fonte": "teste"}],
            "avisos": [{"aba": "Estoque Geral", "linha": 21, "descricao_planilha": "IMP-H13 RETO",
                        "texto": "liga em dúvida", "fonte": "teste"}]}
    pl = _montar(est, geral=geral, corr=corr)
    assert not _bloqueios(pl)
    l5 = next(lp for lp in pl.lotes if lp.origem.get("linha") == 5)
    saida = next(m for m in l5.movimentos if m.tipo == "SAIDA_CORTE_RJ")
    assert saida.op is None and "OP que não existe" in saida.justificativa
    assert any(p.tipo == "CONSUMO_SEM_OP" for p in pl.pendencias)
    assert not any(p.tipo == "OP_MAL_DIGITADA" for p in pl.pendencias)
    par = next(p for p in pl.paridades if p["estoque"] == "RJ_NO_RIO" and "S5" in p["chave"])
    assert par["situacao"] == "MESMA LINHA" and par["chave"] == "S5 250X320" and par.get("paridade_manual")
    l6 = next(lp for lp in pl.lotes if lp.origem.get("linha") == 6)
    # P34(a): o lote mantém a própria medida; só a linha (T04/T07/relatório) é a do código de Itu
    assert plano.chave_mat(pl.itens[l6.item].descricao) == plano.chave_mat("S5 250x320x4970")
    assert pl.itens[l6.item].paridade_cm == 90824
    assert pl.itens[l6.item].codigo_mega is None                      # lote RJ nunca recebe código (v3.7)
    assert any(p.tipo == "PENDENTE_USUARIO" for p in pl.pendencias) and pl.avisos
    # paridade manual com código que não existe → BLOQUEIA
    corr["paridade_manual"][0]["codigo_itu"] = 12345
    assert _bloqueios(_montar(est, geral=geral, corr=corr))


# ---------------- B05 / B07 / B08 ----------------

def test_b05_conteiner_do_corte_pelo_da_estoque_2026():
    est = [_e(5, "CT34X", "A8 MOD 6x74", 1000, 600, [(400, 71001, "H5")])]
    pl = _montar(est, corte=[_c(30, 71001, "A8 6X74", "CT37X", peso2=400)])
    assert len(pl.solicitacoes) == 1 and pl.solicitacoes[0].lote.conteiner == "CT34X"
    assert pl.conteiner_corrigido[0]["conteiner"] == "CT34X"
    assert any(p.tipo == "CONTEINER_CORRIGIDO" for p in pl.pendencias)
    # sem consumo na ESTOQUE 2026: vale o contêiner do SA da mesma OP
    est2 = [_e(5, "CT34X", "A8 MOD 6x74", 1000, 1000)]
    pl = _montar(est2, corte=[_c(30, 71002, "A8 6X74", "CT37X", peso2=10, cortadas=None, obs="-")],
                 sas=[_sa(40, 71002, "A8", "6X74", "CT34X")])
    assert pl.solicitacoes[0].lote.conteiner == "CT34X" and pl.conteiner_corrigido[0]["fonte"] == "planilha de SA"
    # contêiner do Corte existe, mas a ESTOQUE 2026 e o SA dizem outro (§10.9 A.1) → vale o da ESTOQUE 2026/SA
    est3 = [_e(5, "CT34X", "A8 MOD 6x74", 1000, 600, [(400, 71001, "H5")]), _e(6, "CT37X", "A8 MOD 6x74", 50, 50)]
    corte3 = [_c(30, 71001, "A8 6X74", "CT37X", peso2=400)]
    pl = _montar(est3, corte=corte3, sas=[_sa(40, 71001, "A8", "6X74", "CT34X")])
    assert pl.solicitacoes[0].lote.conteiner == "CT34X"
    # a ESTOQUE 2026 e o SA discordam → fica o do Corte, com pendência [P34(d)]
    pl = _montar(est3, corte=corte3, sas=[_sa(40, 71001, "A8", "6X74", "CT37X")])
    assert pl.solicitacoes[0].lote.conteiner == "CT37X"
    assert any(p.tipo == "CONTEINER_DISCORDANTE" for p in pl.pendencias)


def test_tres_conteineres_diferentes_resolvido_pela_correcao_de_leitura():
    # Pendências de 18/11 item 14 (Eduardo, 2026-11-19): Corte, ESTOQUE 2026 e SA dizem três contêineres diferentes;
    # vale o da ESTOQUE 2026, por correção de leitura (contêiner) na linha do Corte e na do SA
    est = [_e(5, "CT21X", "CR12MOV Ø70", 100, 96, [(4, 71062, "G5")]), _e(6, "CT04X", "CR12MOV Ø70", 50, 50),
           _e(7, "CT10X", "CR12MOV Ø70", 50, 50)]
    corte = [_c(30, 71062, "CR12MOV Ø70", "CT04X", peso2=4)]
    sas = [_sa(40, 71062, "CR12MOV", "RED70", "CT10X", 4)]
    pl = _montar(est, corte=corte, sas=sas)
    assert pl.solicitacoes[0].lote.conteiner == "CT04X"                 # sem resposta: fica o do Corte [P34(d)]
    assert any(p.tipo == "CONTEINER_DISCORDANTE" for p in pl.pendencias)
    corr = {"leitura": [
        {"aba": "CONTROLE DE CORTE", "linhas": [30], "conteiner": "CT04X", "descricao_planilha": "CR12MOV Ø70",
         "conteiner_correto": "CT21X", "esperado": 1, "fonte": "teste"},
        {"aba": "SA", "linhas": [40], "conteiner": "CT10X", "contem": r"(Ø|RED)\s*70\b", "conteiner_correto": "CT21X",
         "esperado": 1, "fonte": "teste"}]}
    pl = _montar(est, corte=corte, sas=sas, corr=corr)
    assert not _bloqueios(pl)
    s = pl.solicitacoes[0]
    assert s.lote.conteiner == "CT21X" and [(lb.lote.conteiner, lb.peso_kg) for lb in s.liberacoes] == [("CT21X", 4)]
    assert not any(p.tipo in ("CONTEINER_DISCORDANTE", "CONSUMO_EM_OUTRO_MATERIAL") for p in pl.pendencias)
    assert pl.sas[0].solicitacao is s and pl.sas[0].lote.conteiner == "CT21X"
    assert sum(p.tipo == "CORRECAO_APLICADA" for p in pl.pendencias) == 2


def test_b07_corte_dividido_como_na_estoque_2026_e_sa_no_contêiner_certo():
    est = [_e(5, "CT02X", "A8 MOD 14X123", 1000, 802, [(198, 71003, "H5")]),
           _e(6, "CT39X", "A8 MOD 14x130", 1000, 548, [(452, 71003, "H6")])]
    sas = [_sa(40, 71003, "A8", "14X123", "CT02X", 198), _sa(41, 71003, "A8", "14X130", "CT39X", 452, 95002)]
    pl = _montar(est, corte=[_c(30, 71003, "A8 14X123", "CT02X", peso2=650, cortadas=4)], sas=sas)
    s = pl.solicitacoes[0]
    assert [(lb.lote.conteiner, lb.peso_kg) for lb in s.liberacoes] == [("CT02X", 198), ("CT39X", 452)]
    assert sum(lb.pecas for lb in s.liberacoes) == 4
    assert pl.cops[900]["itens"] == 2
    assert all(m.liberacao is not None for lp in pl.lotes for m in lp.movimentos if m.tipo == "SAIDA_CORTE_RJ")
    assert [x.solicitacao is s for x in pl.sas] == [True, True]
    conf = next(c for c in pl.conferencias if c["conferencia"].startswith("(d) Cortes"))
    assert conf["resultado"] == "OK"
    # peso do Corte não é a soma das partes → não divide
    pl = _montar(est, corte=[_c(30, 71003, "A8 14X123", "CT02X", peso2=198)])
    assert len(pl.solicitacoes[0].liberacoes) == 1 and not pl.cortes_divididos


def test_b08_peso_inicial_e_a_entrada_do_packing_list():
    est = [_e(5, "CT02X", "A8 MOD 14X123", 431.5, 233.5, [(198, 71003, "H5")])]
    hist = [_h(9, "CT02X", "A8 MOD 14X123X3000", 1510, date(2017, 8, 21))]
    pl = _montar(est, hist)
    lote = pl.lotes[0]
    assert lote.peso_inicial == 1510 and lote.abertura_kg == 431.5 and lote.saldo == 233.5
    tipos = [(m.tipo, m.kg, m.data) for m in lote.movimentos]
    assert tipos[0] == ("SALDO_INICIAL", 1510, date(2017, 8, 21))
    assert tipos[1] == ("AJUSTE_INVENTARIO", -1078.5, date(2025, 12, 31))
    conf = next(c for c in pl.conferencias if "abertura de 2026" in c["conferencia"])
    assert conf["resultado"] == "OK" and pl.peso_inicial_packing[0]["packing"] == 1510
    # sem entrada no HISTORICO → PESO INICIAL da ESTOQUE 2026 + pendência [P34(b)]
    pl = _montar(est, [])
    assert pl.lotes[0].peso_inicial == 431.5
    assert any(p.tipo == "PESO_INICIAL_SEM_PACKING_LIST" for p in pl.pendencias)
    # entrada menor que o PESO INICIAL → fica o PESO INICIAL e vai para revisão
    pl = _montar(est, [_h(9, "CT02X", "A8 MOD 14X123X3000", 300)])
    assert pl.lotes[0].peso_inicial == 431.5
    assert any(p.tipo == "PESO_INICIAL_MAIOR_QUE_ENTRADA" for p in pl.pendencias)


def test_sa_da_mesma_op_em_duas_linhas_entram_as_duas():
    est = [_e(5, "CT29X", "A8 18X301", 1000, 1000)]
    sas = [_sa(40, 71004, "A8", "18X301", "CT29X", 268), _sa(41, 71004, "A8", "18X301", "CT29X", 268)]
    assert len(_montar(est, sas=sas).sas) == 2


# ---------------- B09: restrição no item ----------------

def test_b09_restricao_gravada_no_item_tambem_sem_lote():
    est = [_e(5, "CT01X", "CR12MoV 18x610", 900, 894)]
    geral = [_g(30, 93432, "IMP-Cr12MoV 18X610MM", rio=894, obs_rj="não usar para guilhotinas"),
             _g(31, 93992, "IMP-Cr12MoV 20X344MM", obs_rj="não usar para guilhotinas")]
    pl = _montar(est, geral=geral)
    lote = pl.lotes[0]
    assert pl.itens[lote.item].restricao_uso == "não usar para guilhotinas"
    assert ("RESTRICAO", "não usar para guilhotinas") in lote.destinacoes
    sem_lote = [it for it in pl.itens.values() if it.chave[0] == "RJ" and "20X344" in it.descricao]
    assert len(sem_lote) == 1 and sem_lote[0].restricao_uso == "não usar para guilhotinas"
    assert pl.itens[("CM", 93992)].restricao_uso is None               # o código de Itu não muda


def test_b09_lote_novo_herda_a_restricao_do_item(client):
    from app.core.db import SessionLocal
    from app.models import ItemMP, Liga
    from app.services import movimentos as mov
    with SessionLocal() as db:
        liga = Liga(codigo="CR12MOV", nome="CR12MOV", densidade=7.7, apelidos=[])
        db.add(liga)
        db.flush()
        item = ItemMP(descricao="CR12MOV 20X344", liga_id=liga.id, formato="RETANGULAR", espessura=20, largura=344,
                      restricao_uso="não usar para guilhotinas")
        livre = ItemMP(descricao="CR12MOV 20X400", liga_id=liga.id, formato="RETANGULAR", espessura=20, largura=400)
        db.add_all([item, livre])
        db.flush()
        lote = mov.criar_lote(db, item=item, planta_fiscal="RJ", local_fisico="RJ", peso_inicial_kg=100)
        outro = mov.criar_lote(db, item=livre, planta_fiscal="RJ", local_fisico="RJ", peso_inicial_kg=100)
        db.commit()
        assert [(d.tipo, d.descricao) for d in mov.destinacoes_vigentes(db, lote.id)] == [
            ("RESTRICAO", "não usar para guilhotinas")]
        assert mov.destinacoes_vigentes(db, outro.id) == []
