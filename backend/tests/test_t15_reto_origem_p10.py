"""Auditoria de 06/11, parte 2: T15 mínima (entradas Mega a classificar), aba "RETO por origem" e vazamentos do P10."""
import io
from dataclasses import replace
from datetime import date, timedelta

import pytest

from tests.fluxo_util import catalogo_e_lotes, criar_usuarios, entrar

pytest.importorskip("fastapi")


def _db():
    from app.core.db import SessionLocal
    return SessionLocal()


@pytest.fixture()
def amb(client):
    from app.integrations.mega import fabrica
    from app.integrations.mega.gateway import MegaFalso, MovimentoMega, SaldoMega
    from app.services import sync_mega
    us = criar_usuarios(client)
    ids = catalogo_e_lotes()                       # código 78290 (H13 24x62) com lote de 5.198 kg
    d = date.today() - timedelta(days=3)

    def ed(lanc, doc, cod, kg):
        return MovimentoMega(lanc, d, "ED", 1, "Entrada por Compras", doc, cod, kg, None, False, d, None, 1)

    mega = MegaFalso(saldos=[SaldoMega(78290, "IMP-H13 24X62MM", "KG", 6648.0, 7.9),      # +1.450 kg
                             SaldoMega(90001, "IMP-H13 40X200MM", "KG", 800.0, 7.9),      # código novo
                             SaldoMega(90002, "PECA ESTRANHA SEM MEDIDA", "KG", 300.0, 7.9)],
                     movimentos=[ed(1, "NF77", 78290, 1450), ed(2, "NF88", 90001, 800), ed(3, "NF99", 90002, 300)])
    fabrica.definir(mega)
    with _db() as db:
        assert sync_mega.sincronizar_estoque(db).situacao == "OK"
    yield client, us, ids, mega
    fabrica.definir(None)


def _sync():
    from app.services import sync_mega
    with _db() as db:
        sync_mega.sincronizar_estoque(db)


def _pend(client, h, codigo, situacao="ABERTA"):
    r = client.get(f"/api/entradas-mega?situacao={situacao}", headers=h)
    assert r.status_code == 200, r.text
    return next(p for p in r.json()["itens"] if p["codigo"] == codigo)


def test_sync_cria_pendencias_e_perfis(amb):
    client, us, _, _ = amb
    h = entrar(client, us["itu"])
    r = client.get("/api/entradas-mega", headers=h).json()
    assert {p["codigo"] for p in r["itens"]} == {78290, 90001, 90002}
    p = _pend(client, h, 78290)
    assert p["diferenca_kg"] == 1450 and p["saldo_mega_kg"] == 6648 and p["ultima_entrada"]["nf"] == "NF77"
    assert "CODIGO_NOVO" in _pend(client, h, 90001)["etiquetas"]
    assert _pend(client, h, 90001)["item_sugerido"]["bitola"] == "40X200"
    _sync()                                           # não duplica
    assert client.get("/api/entradas-mega", headers=h).json()["total"] == 3
    assert client.get("/api/painel/pendencias", headers=h).json()["entradas_mega_a_classificar"]["quantidade"] == 3
    h = entrar(client, us["analise"])
    assert client.get("/api/entradas-mega", headers=h).status_code == 200
    assert client.post(f"/api/entradas-mega/{p['id']}/nao-e-entrada", json={}, headers=h).status_code == 403
    h = entrar(client, us["rj"])
    assert client.get("/api/entradas-mega", headers=h).status_code == 403


def test_criar_lote_erros_parcial_e_resolucao(amb):
    client, us, _, _ = amb
    h = entrar(client, us["itu"])
    pid = _pend(client, h, 78290)["id"]
    url = f"/api/entradas-mega/{pid}/criar-lote"
    r = client.post(url, json={"peso_kg": 2000, "conteiner": "CH77AB"}, headers=h)
    assert r.status_code == 409 and "não pode ter mais kg do que o Mega tem a mais" in r.text
    r = client.post(url, json={"peso_kg": 100}, headers=h)
    assert r.status_code == 409 and "Informe o contêiner ou marque" in r.text
    # parcial: a pendência continua aberta com o que sobrou
    r = client.post(url, json={"peso_kg": 500, "conteiner": "ch77ab", "nf": "NF77"}, headers=h)
    assert r.status_code == 201, r.text
    assert r.json()["diferenca_restante_kg"] == 950 and r.json()["pendencia"]["situacao"] == "ABERTA"
    lote = client.get(f"/api/lotes/{r.json()['lote']['id']}", headers=h).json()
    assert lote["estoque"] == "ESTOQUE_MEGA" and lote["conteiner"] == "CH77AB" and lote["saldo_kg"] == 500
    # mesmo contêiner e material: pede ciência
    r = client.post(url, json={"peso_kg": 950, "conteiner": "CH77AB"}, headers=h)
    assert r.status_code == 409 and "CONTEINER_REPETIDO" in r.text
    r = client.post(url, json={"peso_kg": 950, "conteiner": "CH77AB",
                               "confirmacoes": {"CONTEINER_REPETIDO": "Outra NF do mesmo contêiner"}}, headers=h)
    assert r.status_code == 201 and r.json()["pendencia"]["situacao"] == "RESOLVIDA"
    assert "Diferença restante: 0,0 kg" in r.json()["mensagem"]
    c = client.get("/api/conciliacao", headers=h).json()
    assert next(i for i in c["itens"] if i["codigo"] == 78290)["status"] == "OK"
    # sem contêiner: origem não identificada
    pid2 = _pend(client, h, 90001)["id"]
    r = client.post(f"/api/entradas-mega/{pid2}/criar-lote", json={"peso_kg": 800, "sem_conteiner": True}, headers=h)
    assert r.status_code == 201, r.text
    novo = client.get(f"/api/lotes/{r.json()['lote']['id']}", headers=h).json()
    assert novo["indicadores"]["origem_nao_identificada"] is True
    # tratada: segunda tentativa
    r = client.post(f"/api/entradas-mega/{pid2}/criar-lote", json={"peso_kg": 10, "sem_conteiner": True}, headers=h)
    assert r.status_code in (400, 409) and "já foi tratada" in r.text


def test_codigo_novo_cria_item_e_ilegivel_bloqueia(amb):
    client, us, _, _ = amb
    h = entrar(client, us["itu"])
    pid = _pend(client, h, 90001)["id"]
    r = client.post(f"/api/entradas-mega/{pid}/criar-lote", json={"peso_kg": 800, "conteiner": "CH90AA"}, headers=h)
    assert r.status_code == 201, r.text
    from app.models import ItemMP
    with _db() as db:
        it = db.query(ItemMP).filter_by(codigo_mega=90001).one()
        assert it.criado_pela_t15 and it.formato == "RETANGULAR" and (it.espessura, it.largura) == (40, 200)
    pid = _pend(client, h, 90002)["id"]
    r = client.post(f"/api/entradas-mega/{pid}/criar-lote", json={"peso_kg": 10, "sem_conteiner": True}, headers=h)
    assert r.status_code == 409 and "Não consegui ler liga e bitola" in r.text


def test_nao_e_entrada_nao_volta_e_reabrir(amb):
    client, us, _, mega = amb
    h = entrar(client, us["itu"])
    pid = _pend(client, h, 78290)["id"]
    url = f"/api/entradas-mega/{pid}/nao-e-entrada"
    r = client.post(url, json={"motivo": "OUTRO", "justificativa": "curta"}, headers=h)
    assert r.status_code == 400 and "pelo menos 10 caracteres" in r.text
    r = client.post(url, json={"motivo": "ACERTO_INVENTARIO_MEGA", "justificativa": "Acerto feito no Mega em 05/11"},
                    headers=h)
    assert r.status_code == 200 and r.json()["situacao"] == "DESCARTADA"
    _sync()
    assert 78290 not in {p["codigo"] for p in client.get("/api/entradas-mega", headers=h).json()["itens"]}
    c = next(i for i in client.get("/api/conciliacao", headers=h).json()["itens"] if i["codigo"] == 78290)
    assert c["explicada_na_t15"] and c["explicada_t15_kg"] == 1450 and c["diferenca_kg"] == 1450
    assert c["status"] == "OK" and c["explicacoes"][0]["justificativa"].startswith("Acerto")
    # o Mega sobe de novo: só o aumento gera nova pendência
    mega.saldos[0] = replace(mega.saldos[0], saldo_fisico=6748.0)
    _sync()
    assert _pend(client, h, 78290)["diferenca_kg"] == 100
    # reabrir: só Admin
    r = client.post(f"/api/entradas-mega/{pid}/reabrir", json={"justificativa": "Foi entrada mesmo"}, headers=h)
    assert r.status_code == 403
    ha = entrar(client, us["admin"])
    r = client.post(f"/api/entradas-mega/{pid}/reabrir", json={"justificativa": "Foi entrada mesmo, NF77"}, headers=ha)
    assert r.status_code == 200 and r.json()["situacao"] == "ABERTA"
    # 0008 (R044): já havia uma ABERTA do código; a reaberta soma nela (uma só ABERTA por código)
    assert r.json()["id"] != pid and r.json()["diferenca_kg"] == 1550


def test_encerrada_pelo_mega(amb):
    client, us, _, mega = amb
    h = entrar(client, us["itu"])
    pid = _pend(client, h, 78290)["id"]
    mega.saldos[0] = replace(mega.saldos[0], saldo_fisico=5198.0)                 # Mega estornou a NF
    _sync()
    r = client.get("/api/entradas-mega?situacao=TODAS", headers=h).json()["itens"]
    assert next(p for p in r if p["id"] == pid)["situacao"] == "ENCERRADA"


def _reto(db, ids):
    from app.models import ItemMP, Lote
    from app.services import movimentos as mov
    item = db.query(ItemMP).filter_by(codigo_mega=1698).one()
    pai = db.get(Lote, ids["l33"])
    out = {}
    for nome, kw, kg, pf, lf in (("com", {"pai": pai}, 100, "RJ", "ITU"),
                                 ("bitola", {"origem_ref": {"bitola_origem": "45X610"}}, 50, "RJ", "ITU"),
                                 ("sem", {}, 30, "ITU", "ITU")):
        lote = mov.criar_lote(db, item=item, planta_fiscal=pf, local_fisico=lf, tipo="RETO", peso_inicial_kg=kg,
                              origem_identificada=False, **kw)
        mov.lancar(db, lote, "SALDO_INICIAL", kg, usuario_id=None)
        out[nome] = lote.id
    db.commit()
    return out


def test_reto_por_origem_classes_totais_excel_e_p10(amb):
    client, us, ids, _ = amb
    with _db() as db:
        r = _reto(db, ids)
    h = entrar(client, us["itu"])
    j = client.get("/api/lotes/reto-por-origem", headers=h).json()
    t = j["totais"]
    assert (t["com_origem_kg"], t["so_bitola_kg"], t["sem_origem_kg"], t["total_kg"]) == (100, 50, 30, 180)
    h13 = j["ligas"][0]
    assert h13["liga"] == "H13" and [b["bitola_origem"] for b in h13["bitolas"]] == ["33X105", "45X610"]
    assert h13["bitolas"][0]["conteineres"][0]["conteiner"] == "CH33K"
    assert h13["bitolas"][1]["conteineres"][0]["conteiner_texto"] == "não informado"
    assert h13["sem_origem"]["saldo_kg"] == 30
    # total = T04 filtrada por formato RETO
    t04 = client.get("/api/lotes?formato=RETO&por_pagina=200", headers=h).json()["itens"]
    assert round(sum(i["saldo_kg"] for i in t04), 3) == t["total_kg"]
    assert client.get("/api/lotes/reto-por-origem?bitola_origem=45x610", headers=h).json()["totais"]["total_kg"] == 50
    assert client.get("/api/lotes/reto-por-origem?estoque=ESTOQUE_MEGA", headers=h).json()["totais"][
        "total_kg"] == 30
    x = client.get("/api/exportar/reto-por-origem.xlsx", headers=h)
    assert x.status_code == 200
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(x.content))
    assert wb.sheetnames == ["Resumo", "Lotes"] and wb["Lotes"].max_row >= 4 + 3
    # P10: Marcelo
    hm = entrar(client, us["rj"])
    j = client.get("/api/lotes/reto-por-origem?estoque=RJ_EM_ITU", headers=hm).json()
    assert j["vazio"] and j["mensagem_vazio"] == "Nenhum RETO no RJ no Rio" and j["totais"]["total_kg"] == 0
    assert client.get("/api/exportar/reto-por-origem.xlsx", headers=hm).status_code == 200
    # árvore do T05 sem o filho de Itu
    a = client.get(f"/api/lotes/{ids['l33']}/arvore", headers=hm).json()
    assert a["raiz"]["filhos"] == []
    h = entrar(client, us["itu"])
    a = client.get(f"/api/lotes/{ids['l33']}/arvore", headers=h).json()
    assert [f["id"] for f in a["raiz"]["filhos"]] == [r["com"]]


def test_p10_painel_e_sa(amb):
    client, us, _, _ = amb
    hm = entrar(client, us["rj"])
    resumo = client.get("/api/painel/resumo", headers=hm).json()
    assert set(resumo["baldes"]) == {"RJ_NO_RIO"} and resumo["total_kg"] == resumo["baldes"]["RJ_NO_RIO"]["kg"]
    p = client.get("/api/painel/pendencias", headers=hm).json()
    assert p["divergencias_mega"]["quantidade"] is None and p["entradas_mega_a_classificar"]["quantidade"] is None
    assert p["ultima_sincronizacao"]["terminado_em"] is None and set(p["grupos"]) == {"OPERACAO_RJ"}
    from app.models import CadastroSa
    with _db() as db:
        sa = CadastroSa(origem="CORTE_ITU", situacao="PENDENTE", op=100592, item_codigo=1)
        db.add(sa)
        db.commit()
        sa_id = sa.id
    assert client.get(f"/api/sas/{sa_id}", headers=hm).status_code == 404
    assert client.get("/api/sas?situacao=PENDENTE", headers=hm).json()["total"] == 0
    hi = entrar(client, us["itu"])
    assert client.get(f"/api/sas/{sa_id}", headers=hi).status_code == 200
    assert client.get("/api/sas?situacao=PENDENTE", headers=hi).json()["total"] == 1


def test_modelo_diferenca_explicada_revisao_banco(amb):
    """Revisão do BANCO E TESTES (R042): uma só pendência ABERTA por código, kg da explicada não se acumula em
    duplicidade e a conciliação reage quando o Mega volta depois de uma explicação ("Não é entrada")."""
    client, us, _, mega = amb
    h = entrar(client, us["itu"])
    pid = _pend(client, h, 78290)["id"]
    client.post(f"/api/entradas-mega/{pid}/nao-e-entrada",
                json={"motivo": "ESTORNO_BAIXA_MEGA", "justificativa": "Estorno de baixa feito no Mega"}, headers=h)
    from sqlalchemy import func, select

    from app.models import PendenciaMega
    for _ in range(3):                                                      # sincronizar de novo não cria duplicata
        _sync()
    with _db() as db:
        n_abertas = db.scalar(select(func.count(PendenciaMega.id)).where(
            PendenciaMega.codigo == 78290, PendenciaMega.situacao == "ABERTA"))
        assert n_abertas == 0
        p = db.get(PendenciaMega, pid)
        assert p.situacao == "DESCARTADA" and p.motivo == "ESTORNO_BAIXA_MEGA" and float(p.kg) == 1450
        assert float(p.saldo_mega_kg) == 6648 and p.justificativa
    # o Mega estorna a NF depois da explicação: a diferença explicada passa a ser maior que a real
    mega.saldos[0] = replace(mega.saldos[0], saldo_fisico=5198.0)
    _sync()
    c = next(i for i in client.get("/api/conciliacao", headers=h).json()["itens"] if i["codigo"] == 78290)
    assert c["diferenca_kg"] == 0 and c["explicada_t15_kg"] == 1450
    assert c["diferenca_nao_explicada_kg"] == -1450       # explicação maior que a diferença real
    assert c["status"] == "MEGA_MENOR"                    # a explicação órfã não esconde: vira alerta de Mega menor
