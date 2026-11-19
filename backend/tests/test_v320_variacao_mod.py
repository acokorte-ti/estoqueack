"""Spec v3.20 T07 (Eduardo, 2026-11-19): a sugestão de lotes do A8 traz também o A8 MOD (e a do A8 MOD traz o A8),
porque é só uma variação; a distinção continua (cada liga na sua linha, com o selo `variacao_mod`)."""
import pytest

from tests.fluxo_util import catalogo_e_lotes, corpo_solicitacao, criar_usuarios, entrar, mega_falso

pytest.importorskip("fastapi")


@pytest.fixture()
def amb(client):
    u = criar_usuarios(client)
    ids = catalogo_e_lotes()
    ids.update(_ligas_mod())
    fab = mega_falso()
    yield client, u, ids
    fab.definir(None)


def _ligas_mod() -> dict:
    """A8 e A8MOD, CR8 e CR8MOD (fictícios), um lote RJ 33×105 de cada."""
    from app.core.db import SessionLocal
    from app.models import Conteiner, ItemMP, Liga
    from app.services import movimentos as mov
    with SessionLocal() as db:
        ligas = {c: Liga(codigo=c, nome=c, densidade=7.85, apelidos=[]) for c in ("A8", "A8MOD", "CR8", "CR8MOD")}
        ct = Conteiner(codigo="CH77MD")
        db.add_all([*ligas.values(), ct])
        db.flush()
        ids = {}
        for c, liga in ligas.items():
            item = ItemMP(descricao=f"{c} 33x105", liga_id=liga.id, formato="RETANGULAR", espessura=33, largura=105)
            db.add(item)
            db.flush()
            lote = mov.criar_lote(db, item=item, planta_fiscal="RJ", local_fisico="RJ", conteiner_id=ct.id,
                                  peso_inicial_kg=800)
            mov.lancar(db, lote, "SALDO_INICIAL", 800, usuario_id=None)
            ids[c] = lote.id
        db.commit()
        return ids


def _compativeis(client, liga):
    return client.get("/api/lotes/compativeis", params={"liga": liga, "espessura": 30, "largura": 100,
                                                        "comprimento": 250, "quantidade": 12}).json()


def test_a8_traz_a8mod_e_a8mod_traz_a8(amb):
    client, u, ids = amb
    entrar(client, u["itu"])
    r = _compativeis(client, "A8")
    assert {(x["id"], x["variacao_mod"], x["liga_equivalente"]) for x in r["itens"]} == {
        (ids["A8"], False, False), (ids["A8MOD"], True, False)}
    # a distinção continua: cada liga no seu grupo, o do MOD com o selo
    assert {(g["liga"], g["variacao_mod"]) for g in r["grupos"]} == {("A8", False), ("A8MOD", True)}
    r = _compativeis(client, "A8MOD")
    assert {(x["id"], x["variacao_mod"]) for x in r["itens"]} == {(ids["A8MOD"], False), (ids["A8"], True)}
    # vale para as outras ligas com normal e MOD; não mistura famílias
    assert {x["id"] for x in _compativeis(client, "CR8")["itens"]} == {ids["CR8"], ids["CR8MOD"]}
    assert all(x["variacao_mod"] is False for x in _compativeis(client, "H13")["itens"])


def test_lote_da_variacao_so_avisa(amb):
    client, u, ids = amb
    h = entrar(client, u["itu"])
    r = client.post("/api/solicitacoes/validar", headers=h, json=corpo_solicitacao(ids["A8MOD"], liga="A8"))
    oc = {o["codigo"]: o["nivel"] for o in r.json()["ocorrencias"]}
    assert oc.get("LIGA_VARIACAO_MOD") == "ALERTA" and "LIGA_DIFERENTE" not in oc
    # liga de outra família continua pedindo justificativa
    r = client.post("/api/solicitacoes/validar", headers=h, json=corpo_solicitacao(ids["CR8"], liga="A8"))
    assert {o["codigo"]: o["nivel"] for o in r.json()["ocorrencias"]}.get("LIGA_DIFERENTE") == "CIENCIA"
