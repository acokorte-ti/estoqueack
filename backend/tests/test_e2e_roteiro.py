"""Ensaio do ponta a ponta (app/jobs/e2e_caminhos.py) com o Mega falso: garante que o roteiro do ponta a ponta roda
de ponta a ponta nos 5 caminhos antes de usá-lo na cópia da homologação."""
from datetime import date

import pytest

from tests.fluxo_util import catalogo_e_lotes, criar_usuarios

pytest.importorskip("fastapi")


def _preparar(client):
    from app.core.db import SessionLocal
    from app.models import ItemMP, Lote
    from app.services import movimentos as mov

    u = criar_usuarios(client)
    ids = catalogo_e_lotes()
    with SessionLocal() as db:   # um lote RJ em Itu (sobra que já está em Itu, origem não identificada)
        item = db.query(ItemMP).filter_by(descricao="H13 70x610").one()
        lote = mov.criar_lote(db, item=item, planta_fiscal="RJ", local_fisico="ITU", peso_inicial_kg=200,
                              origem_identificada=False)
        mov.lancar(db, lote, "SALDO_INICIAL", 200, usuario_id=None)
        db.commit()
        assert db.query(Lote).count() == 6
    return u, ids


def _rodar():
    from app.core.db import SessionLocal
    from app.integrations.mega import fabrica
    from app.integrations.mega.gateway import ComponenteOp, MegaFalso, OrdemProducao, SituacaoSa
    from app.jobs import e2e_caminhos
    from app.main import app

    ops = [OrdemProducao(n, 700 + i, f"PECA {i}", "CLIENTE", "AB", date.today(), 2) for i, n in
           enumerate((200101, 200102, 200103, 200104))]
    estruturas = {o.numero: [ComponenteOp(60000 + i, f"SA PECA {i} - CÓD.{700 + i}", "CO", "PC", 2, 1, 0)]
                  for i, o in enumerate(ops)}
    situacoes = {60000 + i: SituacaoSa(60000 + i, True, f"SA PECA {i}", True, date(2020, 1, 1), 0) for i in range(4)}
    rel = e2e_caminhos.executar(app, SessionLocal, MegaFalso(ops=ops, estruturas=estruturas, situacoes_sa=situacoes),
                                [o.numero for o in ops])
    fabrica.definir(None)
    return rel


def test_roteiro_e2e_cinco_caminhos(client):
    _preparar(client)
    rel = _rodar()
    falhas = {k: v.get("erro") for k, v in rel["caminhos"].items() if not v.get("ok")}
    assert not falhas, falhas
    assert rel["caminhos"]["A"]["situacao_final"] == "CONCLUIDA"
    assert rel["caminhos"]["B"]["situacao_final"] == "CONCLUIDA" and rel["caminhos"]["B"]["lote_reto"]
    assert "Baixar" in rel["caminhos"]["C"]["instrucao_mega"]
    assert rel["conferencia"] == {"negativos": 0, "saldo_diferente_da_soma": [], "qtd_diferentes": 0,
                                  "lotes_rj_com_codigo_mega": 0}
    assert rel["caminhos"]["B2"]["consumo_misto"].startswith("OK")          # P26 opção A (só prévia)
    assert rel["caminhos"]["D"]["lote"]
    assert rel["ok"] and set(rel["sa_confirmacao_simulada"]) == {60000, 60001, 60002}
    # R058: sem pendência na base; no B o envio bloqueia com o recebimento vencido, a T13 libera, o SA fica previsto
    assert rel["peso_real_na_copia"] == {"ok": True, "quantidade": 0, "vencidas": 0, "dias_limite": 7,
                                         "encerradas_na_copia": []}
    pr = rel["caminhos"]["B"]["peso_real"]
    assert pr["bloqueio"] == "OK: envio com ERRO PESO_REAL_PENDENTE; rascunho só com aviso; sai depois da T13"
    assert pr["sa"].startswith("SA com o previsto")


def test_roteiro_e2e_com_peca_inteira_vencida_na_base(client):
    """A cópia da homologação pode ter peça inteira sem peso real há mais de 7 dias (carga ou uso). O ponta a ponta
    confere que o envio está bloqueado, encerra a pendência (só na cópia) e segue."""
    from tests.fluxo_util import mega_falso
    from tests.test_fluxo_itu_operacoes import _peca_inteira_recebida
    from tests.test_r058_peso_real import _envelhecer

    u, ids = _preparar(client)
    fab = mega_falso()
    _peca_inteira_recebida(client, u, ids, fab)
    _envelhecer(12)
    rel = _rodar()
    falhas = {k: v.get("erro") for k, v in rel["caminhos"].items() if not v.get("ok")}
    assert not falhas, falhas
    pc = rel["peso_real_na_copia"]
    assert pc["ok"] and pc["quantidade"] == 1 and pc["vencidas"] == 1
    assert [(x["op"], x["dias"]) for x in pc["encerradas_na_copia"]] == [(100092, 12)]
    assert rel["ok"]
