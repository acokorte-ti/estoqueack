"""Sincronização com o Mega: saldo + preço médio, janela de movimentos (inclusão, alteração, exclusão), agendamento
06h/13h, falha avisando o Admin e "Sincronizar agora" por perfil."""
from datetime import date, datetime, timedelta

import pytest

from tests.fluxo_util import criar_usuarios, entrar

pytest.importorskip("fastapi")


def _mov(lanc, dias_atras, kg, es="SD", tpm=13, doc="100508", codigo=1698, alterado=None):
    from app.integrations.mega.gateway import MovimentoMega
    d = date.today() - timedelta(days=dias_atras)
    return MovimentoMega(lanc, d, es, tpm, "Requisição", doc, codigo, kg, None, False, d, alterado, 70)


@pytest.fixture()
def fab(client):
    from app.integrations.mega import fabrica
    from app.integrations.mega.gateway import MegaFalso, SaldoMega
    m = MegaFalso(saldos=[SaldoMega(1698, "IMP-H13 RETO", "KG", 2240.042, 7.9),
                          SaldoMega(5838, "IMP-A8 RETO", "KG", 0.0, 7.9),
                          SaldoMega(9999, "SEM SALDO NEM PRECO", "KG", 0.0, None)],
                  precos={1698: (7.939533, date(2026, 10, 9)), 5838: (10.7352, date(2026, 10, 5))},
                  movimentos=[_mov(10, 400, 50, "ED", 1, "NF1"), _mov(11, 30, 20), _mov(12, 2, 5)])
    fabrica.definir(m)
    yield m
    fabrica.definir(None)


def _db():
    from app.core.db import SessionLocal
    return SessionLocal()


def test_primeira_sincronizacao_grava_saldo_preco_e_movimentos(fab):
    from app.models import MegaMovimento, MegaSaldo
    from app.services import sync_mega
    with _db() as db:
        s = sync_mega.sincronizar_estoque(db)
        assert s.situacao == "OK" and s.detalhes["primeira_carga"] is True
        assert s.ultimo_lancamento == 12
        saldos = {x.codigo: x for x in db.query(MegaSaldo)}
        assert set(saldos) == {1698, 5838}                         # 9999 sem saldo e sem preço fica fora
        assert float(saldos[1698].preco_medio) == pytest.approx(7.9395, abs=1e-4)
        assert saldos[1698].preco_medio_data == date(2026, 10, 9)
        # 1ª carga desde 2025-01-01: o de 400 dias atrás só entra se for depois dessa data
        lancs = {m.lancamento for m in db.query(MegaMovimento)}
        assert {11, 12} <= lancs


def test_janela_pega_alteracao_e_exclusao(fab):
    from app.models import MegaMovimento
    from app.services import sync_mega
    with _db() as db:
        sync_mega.sincronizar_estoque(db)
        # no Mega: o 11 foi alterado (kg), o 12 foi estornado (some da visão) e entrou o 13
        fab.movimentos = [_mov(10, 400, 50, "ED", 1, "NF1"), _mov(11, 30, 22, alterado=datetime.now()),
                          _mov(13, 0, 7)]
        s = sync_mega.sincronizar_estoque(db)
        assert s.situacao == "OK" and s.ultimo_lancamento == 13
        movs = {m.lancamento: float(m.kg) for m in db.query(MegaMovimento)}
        assert movs.get(11) == 22 and 12 not in movs and movs.get(13) == 7


def test_falha_registra_erro_e_avisa_admin(client, fab):
    from app.models import Notificacao, SyncMega
    from app.services import sync_mega
    criar_usuarios(client)
    fab.falhar = True
    with _db() as db:
        s = sync_mega.sincronizar_estoque(db)
        assert s.situacao == "ERRO" and "fora do ar" in s.detalhes["erro"]
        assert db.query(SyncMega).filter_by(situacao="ERRO").count() == 1
        assert db.query(Notificacao).filter_by(tipo="SYNC_MEGA_FALHOU").count() >= 1


def test_agendamento_06h_13h(fab):
    from app.services import sync_mega
    from app.services.sync_mega import FUSO
    with _db() as db:
        dia = datetime.now(FUSO).replace(hour=7, minute=0, second=0, microsecond=0)
        assert sync_mega.rodar_agendado(db, dia) == {"estoque": "OK"}       # 06:00 de hoje venceu
        assert sync_mega.rodar_agendado(db, dia + timedelta(minutes=5)) == {}   # já rodou depois das 06:00
        assert sync_mega.rodar_agendado(db, dia.replace(hour=13, minute=2)) == {"estoque": "OK"}


def test_sincronizar_agora_por_perfil(client, fab):
    u = criar_usuarios(client)
    h = entrar(client, u["rj"])
    assert client.post("/api/mega/sincronizar", headers=h).status_code == 403
    h = entrar(client, u["itu"])
    r = client.post("/api/mega/sincronizar", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["estoque"]["situacao"] == "OK" and r.json()["sa"]["situacao"] == "OK"
    j = client.get("/api/mega/sincronizacoes").json()
    assert j["ultima_ok"]["tipo"] == "ESTOQUE" and len(j["itens"]) == 2
