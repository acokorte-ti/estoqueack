"""R058 (spec v3.11 §2.2 passo 7, T07, §9, T23; contrato §16.2): pendência do peso real da peça inteira do RJ e
bloqueio `PESO_REAL_PENDENTE` de "Enviar ao RJ" pelas propostas padrão da P33. Dados fictícios."""
from datetime import datetime, timedelta, timezone

import pytest

from tests.fluxo_util import catalogo_e_lotes, corpo_solicitacao, criar_usuarios, entrar, mega_falso
from tests.test_fluxo_itu_operacoes import _peca_inteira_recebida

pytest.importorskip("fastapi")


@pytest.fixture()
def amb(client):
    u = criar_usuarios(client)
    ids = catalogo_e_lotes()
    fab = mega_falso()
    yield client, u, ids, fab
    fab.definir(None)


def _envelhecer(dias: int) -> None:
    from app.core.db import SessionLocal
    from app.models import CopItem
    with SessionLocal() as db:
        for ci in db.query(CopItem).filter(CopItem.lote_itu_id.is_not(None)):
            ci.recebido_em = datetime.now(timezone.utc) - timedelta(days=dias)
        db.commit()


def _codigos(v: dict) -> dict[str, str]:
    return {o["codigo"]: o["nivel"] for o in v["ocorrencias"]}


def test_sem_pendencia_nada_muda(amb):
    client, u, ids, _ = amb
    h = entrar(client, u["itu"])
    s = client.get("/api/pendencias-peso-real", headers=h).json()
    assert s["quantidade"] == 0 and s["bloqueado"] is False and s["dias_limite"] == 7 and s["aviso"] is None
    v = client.post("/api/solicitacoes/validar", json=corpo_solicitacao(ids["l33"]), headers=h).json()
    assert "PESO_REAL_PENDENTE" not in _codigos(v) and "PESO_REAL_AGUARDANDO" not in _codigos(v)


def test_aviso_antes_do_prazo_e_bloqueio_depois(amb):
    client, u, ids, fab = amb
    sol_id, lote_itu, _ = _peca_inteira_recebida(client, u, ids, fab)
    h = entrar(client, u["itu"])
    s = client.get("/api/pendencias-peso-real", headers=h).json()
    assert s["quantidade"] == 1 and s["bloqueado"] is False and "aguardando peso real" in s["aviso"]
    assert s["itens"][0]["solicitacao_id"] == sol_id and s["itens"][0]["lote_itu_id"] == lote_itu
    v = client.post("/api/solicitacoes/validar", json=corpo_solicitacao(ids["l33"], op=100600), headers=h).json()
    assert _codigos(v).get("PESO_REAL_AGUARDANDO") == "ALERTA"           # aviso cinza, não bloqueia
    # passou de 7 dias do recebimento do COP → bloqueia "Enviar ao RJ" para todos
    _envelhecer(8)
    s = client.get("/api/pendencias-peso-real", headers=h).json()
    assert s["bloqueado"] is True and s["vencidas"] == 1 and "sem peso real há mais de 7 dias" in s["mensagem"]
    corpo = corpo_solicitacao(ids["l33"], op=100601)
    r = client.post("/api/solicitacoes", json=corpo, headers=h)
    assert r.status_code == 409 and _codigos(r.json())["PESO_REAL_PENDENTE"] == "ERRO"
    h_adm = entrar(client, u["admin"])                                    # o Admin também não libera
    r = client.post("/api/solicitacoes", json={**corpo, "confirmacoes": {"PESO_REAL_PENDENTE": "x" * 20}},
                    headers=h_adm)
    assert r.status_code == 409
    h = entrar(client, u["itu"])
    r = client.post("/api/solicitacoes", json={**corpo, "enviar": False}, headers=h)     # rascunho continua
    assert r.status_code == 201 and r.json()["solicitacoes"][0]["situacao"] == "RASCUNHO"
    # Painel e sino
    p = client.get("/api/painel/pendencias", headers=h).json()
    card = next(c for c in p["grupos"]["ESTOQUE"] if c["codigo"] == "PECA_INTEIRA_AGUARDANDO_CORTE")
    assert card["nivel"] == "ALERTA" and card["itens"][0]["vencida"] is True
    assert card["itens"][0]["dias_desde_recebimento"] == 8
    from app.core.db import SessionLocal
    from app.services import avisos
    with SessionLocal() as db:
        assert avisos.rodar(db)["peso_real"] == 1
        db.commit()
        assert avisos.rodar(db)["peso_real"] == 0                          # uma vez por peça
    # Operação RJ não enxerga a pendência de Itu
    h_rj = entrar(client, u["rj"])
    assert client.get("/api/pendencias-peso-real", headers=h_rj).json()["itens"] == []


def test_encerrar_pendencia_com_justificativa_desbloqueia(amb):
    client, u, ids, fab = amb
    sol_id, _, _ = _peca_inteira_recebida(client, u, ids, fab)
    _envelhecer(10)
    h = entrar(client, u["itu"])
    url = f"/api/pendencias-peso-real/{sol_id}/encerrar"
    assert client.post(url, json={"justificativa": "curta"}, headers=h).status_code == 422
    r = client.post(url, json={"justificativa": "OP cancelada pelo cliente"}, headers=h)
    assert r.status_code == 200 and r.json()["justificativa"] == "OP cancelada pelo cliente"
    assert client.post(url, json={"justificativa": "OP cancelada pelo cliente"}, headers=h).status_code == 400
    s = client.get("/api/pendencias-peso-real", headers=h).json()
    assert s["quantidade"] == 0 and s["bloqueado"] is False
    sol = client.get(f"/api/solicitacoes/{sol_id}", headers=h).json()
    assert sol["situacao"] == "AGUARDANDO_CORTE_ITU"                      # a T13 ainda pode ser feita
    v = client.post("/api/solicitacoes/validar", json=corpo_solicitacao(ids["l33"], op=100602), headers=h).json()
    assert "PESO_REAL_PENDENTE" not in _codigos(v) and "PESO_REAL_AGUARDANDO" not in _codigos(v), v
    h_rj = entrar(client, u["rj"])
    assert client.post(url, json={"justificativa": "OP cancelada pelo cliente"}, headers=h_rj).status_code == 403


def test_t13_resolve_a_pendencia_e_rascunho_so_avisa(amb):
    client, u, ids, fab = amb
    sid, lote_itu, previsto = _peca_inteira_recebida(client, u, ids, fab)
    _envelhecer(9)
    h = entrar(client, u["itu"])
    v = client.post("/api/solicitacoes/validar", json=corpo_solicitacao(ids["l33"], op=100603, enviar=False),
                    headers=h).json()
    assert _codigos(v).get("PESO_REAL_AGUARDANDO") == "ALERTA" and "PESO_REAL_PENDENTE" not in _codigos(v)
    p = client.get("/api/painel/pendencias", headers=h).json()
    card = next(c for c in p["grupos"]["ESTOQUE"] if c["codigo"] == "PECA_INTEIRA_AGUARDANDO_CORTE")
    assert card["limite_dias"] == 7 and card["vencidas"] == 1
    item = card["itens"][0]
    assert item["pendencia_id"] == sid and item["lote_id"] == lote_itu and item["dias"] == 9 and item["lote"]
    corpo = {"op": 100092, "lote_id": lote_itu, "consumo_kg": round(previsto, 1), "sobra_kg": 300,
             "sobra_na_bitola": True, "pecas": 1, "peso_usado_kg": 1288,
             "confirmacoes": {"PERDA_CORTE_ALTA": "Barra com ponta torta descartada"}}
    r = client.post("/api/cortes-itu", json=corpo, headers=h)
    assert r.status_code == 201, r.text
    assert r.json()["pendencia_peso_real_resolvida"] is True
    s = client.get("/api/pendencias-peso-real", headers=h).json()
    assert s["quantidade"] == 0 and s["bloqueado"] is False
