"""Teste de carga simples (Parte C4, chat BANCO E TESTES): tempo de resposta das telas principais com o volume da
carga inicial (≈ 600 itens, 1.000 lotes, 8.300 linhas de SA, ~16 mil movimentos, 800 solicitações).

Não roda no CI normal. Uso (PostgreSQL de verdade; o banco é apagado):
    VOLUME=1 TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/test_volume.py -s
"""
import os
import random
import time
from datetime import date, timedelta

import pytest

from tests.conftest import PG
from tests.fluxo_util import criar_usuarios, entrar

pytestmark = pytest.mark.skipif(not (PG and os.environ.get("VOLUME")), reason="VOLUME=1 + PostgreSQL")

LIMITE_S = 1.5          # cada tela precisa responder abaixo disso com o volume da carga


def _semear():
    from app.core.db import SessionLocal
    from app.models import (CadastroSa, Conteiner, ItemMP, LiberacaoCorte, Liga, Lote, Movimento, Notificacao,
                            SolicitacaoCorte, Usuario)
    rnd = random.Random(42)
    with SessionLocal() as db:
        ligas = [Liga(codigo=f"L{i:02d}", nome=f"Liga {i}", densidade=7.85, apelidos=[]) for i in range(15)]
        db.add_all(ligas)
        db.flush()
        itens = [ItemMP(descricao=f"ITEM {i}", liga_id=ligas[i % 15].id, formato="RETANGULAR",
                        espessura=10 + i % 90, largura=50 + (i * 7) % 600, codigo_mega=50000 + i) for i in range(600)]
        cts = [Conteiner(codigo=f"CH{i:02d}X") for i in range(40)]
        db.add_all(itens + cts)
        db.flush()
        usuario = db.query(Usuario).filter_by(login="fabiano.camargo").one()
        lotes = []
        for i in range(1000):
            balde = ("RJ", "RJ") if i < 450 else (("RJ", "ITU") if i < 650 else ("ITU", "ITU"))
            lotes.append(Lote(codigo=f"L-{i + 1:06d}", item_mp_id=itens[i % 600].id, planta_fiscal=balde[0],
                              local_fisico=balde[1], tipo="ORIGINAL", conteiner_id=cts[i % 40].id if i < 650 else None,
                              origem_identificada=i < 450, peso_inicial_kg=5000, saldo_kg=0, status="ATIVO"))
        db.add_all(lotes)
        db.flush()
        movs = []
        for lote in lotes:
            saldo = 5000.0
            movs.append(Movimento(lote_id=lote.id, tipo="SALDO_INICIAL", kg=5000, usuario_id=usuario.id))
            for _ in range(15):
                kg = round(rnd.uniform(5, 200), 3)
                saldo -= kg
                movs.append(Movimento(lote_id=lote.id, tipo="SAIDA_CORTE_RJ", kg=-kg, op=90000 + rnd.randint(0, 9999),
                                      usuario_id=usuario.id))
            lote.saldo_kg = round(saldo, 3)
        db.add_all(movs)
        db.flush()
        sols = []
        situacoes = ["CONCLUIDA"] * 6 + ["ENVIADA", "CORTADA_PARCIAL", "EM_COP", "SA_PRONTO"]
        for i in range(800):
            s = situacoes[i % len(situacoes)]
            sols.append(SolicitacaoCorte(op=95000 + i, item_codigo=60000 + i % 3000, lote_id=lotes[i % 450].id,
                                         modo="CORTAR_RJ", quantidade=10, formato="RETANGULAR",
                                         peso_previsto_kg=80, situacao=s, prazo=date.today() + timedelta(days=i % 60),
                                         criado_por_id=usuario.id))
        db.add_all(sols)
        db.flush()
        db.add_all([LiberacaoCorte(solicitacao_id=s.id, lote_id=s.lote_id, pecas=10, peso_real_kg=82,
                                   data_corte=date.today()) for s in sols if s.situacao != "ENVIADA"])
        db.add_all([CadastroSa(origem="CARGA", data=date(2016, 1, 1) + timedelta(days=i % 3600), op=80000 + i,
                               item_codigo=60000 + i % 3000, sa_codigo=30000 + i % 4000,
                               situacao="CONFIRMADO" if i % 160 else "AGUARDANDO_MEGA", peso_kg=50, quantidade=5,
                               conteiner=f"CH{i % 40:02d}X") for i in range(8300)])
        db.add_all([Notificacao(usuario_id=usuario.id, tipo="TESTE", texto=f"aviso {i}") for i in range(2000)])
        db.commit()
        return lotes[0].id, lotes[700].id


def test_tempo_das_telas_com_volume_da_carga(client):
    from app.integrations.mega import fabrica
    from tests.fluxo_util import mega_falso
    u = criar_usuarios(client)
    t0 = time.perf_counter()
    lote_rj, lote_itu = _semear()
    print(f"\nsemeadura: {time.perf_counter() - t0:.1f} s")
    mega_falso()
    try:
        telas = {
            "T03 painel": "/api/painel/resumo",
            "T04 lotes": "/api/lotes?por_pagina=50",
            "T04 lotes agrupado": "/api/lotes/agrupado",
            "T05 lote": f"/api/lotes/{lote_rj}",
            "T05 movimentos": f"/api/lotes/{lote_rj}/movimentos",
            "T07 compatíveis": "/api/lotes/compativeis?liga=L03&espessura=10&largura=40&comprimento=200&quantidade=5",
            "T08 solicitações": "/api/solicitacoes",
            "T08 ativas": "/api/solicitacoes?situacao=ENVIADA&situacao=CORTADA_PARCIAL",
            "T09 fila RJ": "/api/fila-rj",
            "T11 COPs": "/api/cops",
            "T14 SA (pendentes)": "/api/sas",
            "T14 SA por OP": "/api/sas?op=80005",
            "sino": "/api/notificacoes?somente_nao_lidas=true",
        }
        entrar(client, u["itu"])
        tempos = {}
        for nome, url in telas.items():
            client.get(url)                                     # aquece
            ini = time.perf_counter()
            r = client.get(url)
            tempos[nome] = time.perf_counter() - ini
            assert r.status_code == 200, (nome, r.status_code, r.text[:300])
        print("\n".join(f"  {n:22s} {t * 1000:7.0f} ms" for n, t in tempos.items()))
        lentas = {n: round(t, 2) for n, t in tempos.items() if t > LIMITE_S}
        assert not lentas, f"telas acima de {LIMITE_S} s: {lentas}"
    finally:
        fabrica.definir(None)
