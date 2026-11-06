"""Ensaio do ponta a ponta (app/jobs/e2e_caminhos.py) com o Mega falso: garante que o roteiro do ponta a ponta roda
de ponta a ponta nos 5 caminhos antes de usá-lo na cópia da homologação."""
from datetime import date

import pytest

from tests.fluxo_util import catalogo_e_lotes, criar_usuarios

pytest.importorskip("fastapi")


def test_roteiro_e2e_cinco_caminhos(client):
    from app.core.db import SessionLocal
    from app.integrations.mega import fabrica
    from app.integrations.mega.gateway import ComponenteOp, MegaFalso, OrdemProducao, SituacaoSa
    from app.jobs import e2e_caminhos
    from app.main import app
    from app.models import ItemMP, Lote
    from app.services import movimentos as mov

    criar_usuarios(client)
    catalogo_e_lotes()
    with SessionLocal() as db:   # um lote RJ em Itu (sobra que já está em Itu, origem não identificada)
        item = db.query(ItemMP).filter_by(descricao="H13 70x610").one()
        lote = mov.criar_lote(db, item=item, planta_fiscal="RJ", local_fisico="ITU", peso_inicial_kg=200,
                              origem_identificada=False)
        mov.lancar(db, lote, "SALDO_INICIAL", 200, usuario_id=None)
        db.commit()
        assert db.query(Lote).count() == 6

    ops = [OrdemProducao(n, 700 + i, f"PECA {i}", "CLIENTE", "AB", date.today(), 2) for i, n in
           enumerate((200101, 200102, 200103, 200104))]
    estruturas = {o.numero: [ComponenteOp(60000 + i, f"SA PECA {i} - CÓD.{700 + i}", "CO", "PC", 2, 1, 0)]
                  for i, o in enumerate(ops)}
    situacoes = {60000 + i: SituacaoSa(60000 + i, True, f"SA PECA {i}", True, date(2020, 1, 1), 0) for i in range(4)}
    rel = e2e_caminhos.executar(app, SessionLocal, MegaFalso(ops=ops, estruturas=estruturas, situacoes_sa=situacoes),
                                [o.numero for o in ops])
    fabrica.definir(None)
    falhas = {k: v.get("erro") for k, v in rel["caminhos"].items() if not v.get("ok")}
    assert not falhas, falhas
    assert rel["caminhos"]["A"]["situacao_final"] == "CONCLUIDA"
    assert rel["caminhos"]["B"]["situacao_final"] == "CONCLUIDA" and rel["caminhos"]["B"]["lote_reto"]
    assert "Baixar" in rel["caminhos"]["C"]["instrucao_mega"]
    assert rel["conferencia"] == {"negativos": 0, "saldo_diferente_da_soma": [], "qtd_diferentes": 0}
    assert rel["ok"] and set(rel["sa_confirmacao_simulada"]) == {60000, 60001, 60002}
