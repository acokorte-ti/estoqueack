"""Apoio aos testes do fluxo da Fase 1: usuários por perfil, catálogo, lotes e Mega falso."""
from __future__ import annotations

from datetime import date

from tests.conftest import preparar_admin

SENHA = "123456"


def criar_usuarios(client) -> dict:
    h = preparar_admin(client)
    for login, perfil, planta in (("fabiano.camargo", "ESTOQUE", "ITU"), ("marcello.teixeira", "OPERACAO_RJ", "RJ"),
                                  ("renato.pinto", "ANALISE", "ITU")):
        r = client.post("/api/usuarios", json={"login": login, "nome": login.replace(".", " ").title(),
                                               "email": f"{login}@acokorte.com.br", "perfil": perfil,
                                               "planta": planta, "senha": SENHA, "trocar_senha": False}, headers=h)
        assert r.status_code == 201, r.text
    client.post("/api/auth/logout", headers=h)
    return {"admin": ("admin", "NovaSenha2026x"), "itu": ("fabiano.camargo", SENHA),
            "rj": ("marcello.teixeira", SENHA), "analise": ("renato.pinto", SENHA)}


def entrar(client, credencial: tuple[str, str]) -> dict:
    if client.cookies.get("ack_sessao"):
        client.post("/api/auth/logout", headers={"X-CSRF-Token": client.cookies.get("ack_csrf")})
    client.cookies.clear()
    r = client.post("/api/auth/login", json={"login": credencial[0], "senha": credencial[1]})
    assert r.status_code == 200, r.text
    return {"X-CSRF-Token": r.json()["csrf"]}


def catalogo_e_lotes() -> dict:
    """H13 (7,8) e 1.2344 equivalente; lotes RJ/RJ 33×105/CH33K (1.000 kg) e 70×610/CH25K (5.000 kg)."""
    from app.core.db import SessionLocal
    from app.models import Conteiner, ItemMP, Liga, LigaEquivalente
    from app.services import movimentos as mov
    with SessionLocal() as db:
        h13 = Liga(codigo="H13", nome="H13", densidade=7.8, apelidos=[])
        l2344 = Liga(codigo="1.2344", nome="1.2344", densidade=7.8, apelidos=[])
        db.add_all([h13, l2344])
        db.flush()
        db.add(LigaEquivalente(liga_a_id=l2344.id, liga_b_id=h13.id))
        b33 = ItemMP(descricao="H13 33x105", liga_id=h13.id, formato="RETANGULAR", espessura=33, largura=105)
        b70 = ItemMP(descricao="H13 70x610", liga_id=h13.id, formato="RETANGULAR", espessura=70, largura=610)
        b2344 = ItemMP(descricao="1.2344 33x105", liga_id=l2344.id, formato="RETANGULAR", espessura=33, largura=105)
        reto = ItemMP(descricao="IMP-H13 RETO", liga_id=h13.id, formato="RETO", codigo_mega=1698)
        mega = ItemMP(descricao="IMP-H13 24X62MM", liga_id=h13.id, formato="RETANGULAR", espessura=24, largura=62,
                      codigo_mega=78290)
        c33, c25, c40 = Conteiner(codigo="CH33K"), Conteiner(codigo="CH25K"), Conteiner(codigo="CH40SH")
        db.add_all([b33, b70, b2344, reto, mega, c33, c25, c40])
        db.flush()
        ids = {}
        for nome, item, ct, kg, pf, lf in (("l33", b33, c33, 1000, "RJ", "RJ"), ("l70", b70, c25, 5000, "RJ", "RJ"),
                                           ("l33b", b33, c40, 400, "RJ", "RJ"), ("l2344", b2344, c40, 300, "RJ", "RJ"),
                                           ("lmega", mega, None, 5198, "ITU", "ITU")):
            lote = mov.criar_lote(db, item=item, planta_fiscal=pf, local_fisico=lf, conteiner_id=ct.id if ct else None,
                                  peso_inicial_kg=kg)
            mov.lancar(db, lote, "SALDO_INICIAL", kg, usuario_id=None)
            ids[nome] = lote.id
        db.commit()
        return ids


def mega_falso(*ops_extra):
    from app.integrations.mega import fabrica
    from app.integrations.mega.gateway import MegaFalso, OrdemProducao
    ops = [OrdemProducao(100592, 777, "PECA 30X100X250MM", "CLIENTE X", "AB", date(2026, 10, 1), 12,
                         date(2026, 12, 9), pedido="1-4521"),
           OrdemProducao(100092, 888, "BLOCO 65X600X200MM", "CLIENTE Y", "AB", date(2026, 10, 1), 1,
                         date(2026, 12, 20)),
           OrdemProducao(100508, 68092, "PARTE 12X54X90MM", "CLIENTE Z", "AB", date(2026, 10, 16), 128,
                         date(2026, 12, 9)),
           *ops_extra]
    fabrica.definir(MegaFalso(ops=ops))
    return fabrica


def corpo_solicitacao(lote_id: int, **kw) -> dict:
    base = {"op": 100592, "liga": "H13",
            "medida": {"formato": "RETANGULAR", "espessura": 30, "largura": 100, "comprimento": 250},
            "itens": [{"lote_id": lote_id, "modo": "CORTAR_RJ", "quantidade": 12}], "enviar": True, "confirmacoes": {}}
    base.update(kw)
    return base
