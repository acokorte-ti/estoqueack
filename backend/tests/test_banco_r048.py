"""BANCO E TESTES, rodada de 2026-11-12 (R048): regras novas da spec v3.5 a v3.9 vistas pelo lado do banco e do
aceite. Complementa `test_v35_r045.py` (do TÉCNICO) sem repetir os mesmos casos: limites exatos (8 % × 5 %),
consumo misto na ordem inversa, peça inteira pela API, mesma linha 1.2379 = D2, lote RJ sem código do Mega e a carga
com o arquivo de correções pela linha de comando.

Dados fictícios: OPs, contêineres e pesos de exemplo (nada de dado real)."""
from __future__ import annotations

import json

import pytest

from app.domain import regras
from app.domain.medidas import chave_material, interpretar
from tests.fluxo_util import catalogo_e_lotes, corpo_solicitacao, criar_usuarios, entrar, mega_falso

pytest.importorskip("fastapi")


def _k(desc, fixado=None):
    return chave_material(interpretar(desc), desc, fixado)


# ---------------- domínio: mesma linha (P28) ----------------

def test_1_2379_e_d2_na_mesma_linha_e_medida_diferente_separa():
    assert _k("1.2379 45X610") == _k("IMP-D2 45X610MM") == _k("d2 45,0 x 610 mm")
    assert _k("1.2379 45X610") != _k("IMP-D2 45X600MM")                    # bitola diferente nunca junta
    assert _k("1.2379 RED 90X2425") == _k("IMP-D2 Ø90X2425MM")             # redondo com comprimento
    assert _k("IMP-D2 Ø90X2425MM") != _k("IMP-D2 Ø90X3000MM")              # comprimentos diferentes
    assert _k("1.2344 33X105") == _k("H13 33X105") != _k("1.2379 33X105")


def test_mod_e_cr8mod_ficam_em_linha_propria():
    assert _k("CR8MOD 7,5X55") == _k("IMP-CR8 MOD 7,5X55MM")
    assert _k("CR8MOD 7,5X55") != _k("CR8 7,5X55")
    assert _k("A8 MOD 21X203") != _k("A8 21X203") and _k("A8 MOD 21X203") == _k("IMP-A8MOD 21X203MM")


def test_multiplo_nao_e_o_mesmo_que_comprimento():
    """'MULT. 1820' (múltiplo) e '...X1820' (comprimento informado) têm o mesmo número, mas são linhas diferentes."""
    assert _k("H13 33X105", "MULT. 1820") != _k("H13 33X105X1820")
    assert _k("H13 33X105", "MULT. 1820") == _k("IMP-H13 33X105MM", "MULT. 1820")
    assert _k("H13 33X105", "MULT. 1820") != _k("H13 33X105", "MULT. 2020")


# ---------------- domínio: limites exatos ----------------

@pytest.mark.parametrize("real,limite,estoura", [(108.0, 8, False), (108.01, 8, True), (105.0, 5, False),
                                                 (105.01, 5, True), (107.9, 5, True)])
def test_limite_exato_da_tolerancia(real, limite, estoura):
    cods = [o.codigo for o in regras.validar_peso_real(100, real, limite).ocorrencias]
    assert ("EXCESSO_TOLERANCIA" in cods) is estoura


def test_barra_igual_a_peca_nao_avisa_e_sem_previsto_nao_avisa():
    assert not regras.validar_barra_inteira(837, 837).ocorrencias
    assert [o.codigo for o in regras.validar_barra_inteira(837, 836.9).ocorrencias] == ["BARRA_MAIS_LEVE_QUE_PECA"]
    assert not regras.validar_barra_inteira(None, 10).ocorrencias


# ---------------- API ----------------

@pytest.fixture()
def amb(client):
    u = criar_usuarios(client)
    ids = catalogo_e_lotes()
    from app.core.db import SessionLocal
    from app.models import Lote
    from app.services import movimentos as mov
    with SessionLocal() as db:
        item = db.get(Lote, ids["l33"]).item                      # lote RJ em Itu (inteiro), sem código do Mega
        lote = mov.criar_lote(db, item=item, planta_fiscal="RJ", local_fisico="ITU", peso_inicial_kg=200)
        mov.lancar(db, lote, "SALDO_INICIAL", 200, usuario_id=None)
        reto = mov.item_reto(db, item.liga_id, com_codigo=False)   # RETO RJ em Itu: item RETO sem código
        lreto = mov.criar_lote(db, item=reto, planta_fiscal="RJ", local_fisico="ITU", peso_inicial_kg=150,
                               tipo="RETO")
        mov.lancar(db, lreto, "SALDO_INICIAL", 150, usuario_id=None)
        db.commit()
        ids["litu"], ids["lreto_rj"] = lote.id, lreto.id
    fab = mega_falso()
    yield client, u, ids, fab
    fab.definir(None)


def _codigos(v):
    return [o["codigo"] for o in v["ocorrencias"]]


def _validar_itu(client, h, lote_id, consumo, usado=110):
    return client.post("/api/cortes-itu/validar", headers=h, json={
        "op": 100508, "pecas": 1, "previsto_kg": 100, "sobra_kg": 0, "lote_id": lote_id,
        "consumo_kg": consumo, "peso_usado_kg": usado}).json()


def test_t13_limite_exato_rj_inteiro_reto_e_mega(amb):
    client, u, ids, _ = amb
    h = entrar(client, u["itu"])
    for lote in ("litu", "lreto_rj"):                      # 8 %: lote RJ em Itu inteiro e RETO RJ em Itu
        assert "EXCESSO_TOLERANCIA" not in _codigos(_validar_itu(client, h, ids[lote], 108))
        v = _validar_itu(client, h, ids[lote], 108.5)
        exc = next(o for o in v["ocorrencias"] if o["codigo"] == "EXCESSO_TOLERANCIA")
        assert "8 % para material do RJ" in exc["mensagem"] and v["resultado"]["tolerancia_excesso_pct"] == 8
    assert "EXCESSO_TOLERANCIA" not in _codigos(_validar_itu(client, h, ids["lmega"], 105))
    v = _validar_itu(client, h, ids["lmega"], 105.5)
    exc = next(o for o in v["ocorrencias"] if o["codigo"] == "EXCESSO_TOLERANCIA")
    assert "5 % para lote do Estoque Mega" in exc["mensagem"]


def test_t10_peca_inteira_barra_mais_leve_avisa_e_nao_aplica_tolerancia(amb):
    client, u, ids, _ = amb
    h = entrar(client, u["itu"])
    corpo = corpo_solicitacao(ids["l70"], op=100092,
                              medida={"formato": "RETANGULAR", "espessura": 65, "largura": 600, "comprimento": 200})
    corpo["itens"] = [{"lote_id": ids["l70"], "modo": "TRAZER_INTEIRA", "quantidade": 1}]
    s = client.post("/api/solicitacoes", json=corpo, headers=h).json()["solicitacoes"][0]
    h = entrar(client, u["rj"])
    leve = {"linhas": [{"lote_id": ids["l70"], "pecas": 1, "peso_real_kg": round(s["peso_previsto_kg"] / 2, 1)}]}
    v = client.post(f"/api/solicitacoes/{s['id']}/corte/validar", json=leve, headers=h).json()
    assert _codigos(v) == ["BARRA_MAIS_LEVE_QUE_PECA"] and v["ocorrencias"][0]["nivel"] == "ALERTA"
    pesada = {"linhas": [{"lote_id": ids["l70"], "pecas": 1, "peso_real_kg": s["peso_previsto_kg"] * 3}]}
    v = client.post(f"/api/solicitacoes/{s['id']}/corte/validar", json=pesada, headers=h).json()
    assert "EXCESSO_TOLERANCIA" not in _codigos(v) and "BARRA_MAIS_LEVE_QUE_PECA" not in _codigos(v)
    r = client.post(f"/api/solicitacoes/{s['id']}/corte", json=leve, headers=h)    # só aviso: não bloqueia
    assert r.status_code == 201, r.text


def test_consumo_misto_rj_primeiro_depois_itu(amb):
    """Opção A na ordem inversa do teste do TÉCNICO: a solicitação ao RJ marcada vem antes do corte em Itu."""
    client, u, ids, _ = amb
    h = entrar(client, u["itu"])
    corpo = corpo_solicitacao(ids["l33"], consumo_misto=True)
    v = client.post("/api/solicitacoes/validar", headers=h, json=corpo).json()
    assert "OP_DUPLICADA" not in _codigos(v)
    r = client.post("/api/solicitacoes", headers=h, json={**corpo, "confirmacoes": {
        o["codigo"]: "ok" for o in v["ocorrencias"] if o["nivel"] == "CIENCIA"}})
    assert r.status_code == 201, r.text
    c = client.post("/api/cortes-itu", headers=h, json={"op": 100592, "lote_id": ids["litu"], "consumo_kg": 30,
                                                        "peso_usado_kg": 30, "pecas": 2, "consumo_misto": True})
    assert c.status_code == 201, c.text
    s = client.get("/api/solicitacoes", headers=h, params={"op": 100592}).json()["itens"][0]
    assert s["consumo_misto"]["itu_kg"] == 30 and s["consumo_misto"]["texto"].startswith("OP com consumo misto: Itu 30")
    # terceira solicitação da mesma OP sem a marca: continua avisando OP_DUPLICADA
    assert "OP_DUPLICADA" in _codigos(client.post("/api/solicitacoes/validar", headers=h,
                                                  json=corpo_solicitacao(ids["l33b"])).json())


def test_consumo_misto_nao_esconde_corte_itu_sem_marca(amb):
    """Corte em Itu SEM a marca gera SA da OP: a solicitação marcada depois ainda avisa OP_DUPLICADA."""
    client, u, ids, _ = amb
    h = entrar(client, u["itu"])
    c = client.post("/api/cortes-itu", headers=h, json={"op": 100592, "lote_id": ids["litu"], "consumo_kg": 30,
                                                        "peso_usado_kg": 30, "pecas": 2})
    assert c.status_code == 201, c.text
    assert c.json()["consumo_misto"] is False
    v = client.post("/api/solicitacoes/validar", headers=h,
                    json=corpo_solicitacao(ids["l33"], consumo_misto=True)).json()
    assert "OP_DUPLICADA" in _codigos(v)


def test_lote_rj_sem_codigo_do_mega_na_entrada_nf_e_na_sugestao(amb):
    """v3.7 §1.4: entrada NF do RJ com a mesma bitola de um código do Estoque Mega (H13 24X62 = 78290) cria item
    SEM código; o código só aparece no Estoque Mega, e a sugestão põe os dois na mesma linha."""
    client, u, ids, _ = amb
    from datetime import date
    h = entrar(client, u["rj"])
    corpo = {"numero": "880011", "data": date.today().isoformat(), "fornecedor": "FORNECEDOR TESTE",
             "conteiner": "CT90TS", "itens": [{"liga": "H13", "formato": "RETANGULAR", "espessura": 24, "largura": 62,
                                               "pecas": 2, "peso_kg": 300}]}
    r = client.post("/api/entradas-nf", json=corpo, headers=h)
    assert r.status_code == 201, r.text
    novo = r.json()["itens"][0]["lote_id"]
    lo = client.get(f"/api/lotes/{novo}", headers=h).json()
    assert lo["estoque"] == "RJ_NO_RIO" and lo["codigo_mega"] is None
    from app.core.db import SessionLocal
    from app.models import Lote
    with SessionLocal() as db:
        a, b = db.get(Lote, novo), db.get(Lote, ids["lmega"])
        assert a.item_mp_id != b.item_mp_id and a.item.codigo_mega is None and b.item.codigo_mega == 78290
    h = entrar(client, u["itu"])
    g = client.get("/api/lotes/compativeis", headers=h, params={
        "liga": "H13", "formato": "RETANGULAR", "espessura": 22, "largura": 60, "comprimento": 100, "quantidade": 1,
        "peso_necessario_kg": 50}).json()
    grupo = next(x for x in g["grupos"] if x["chave"] == "H13 24X62")
    assert grupo["estoques"]["RJ_NO_RIO"]["disponivel_kg"] == 300
    assert [x["codigo_mega"] for x in grupo["estoques"]["RJ_NO_RIO"]["lotes"]] == [None]
    lista = client.get("/api/lotes", headers=h).json()["itens"]
    assert all(x["codigo_mega"] is None for x in lista if x["estoque"] != "ESTOQUE_MEGA")


def test_p28_liga_mesma_linha_nao_pede_ciencia(amb):         # R053(1) corrigido pelo TÉCNICO em 2026-11-12
    client, u, ids, _ = amb
    h = entrar(client, u["itu"])
    v = client.post("/api/solicitacoes/validar", headers=h, json=corpo_solicitacao(ids["l2344"])).json()
    assert "LIGA_EQUIVALENTE" not in [c.split("#")[0] for c in _codigos(v)]


# ---------------- carga: arquivo de correções pela linha de comando ----------------

from tests.test_carga import _planilhas, base  # noqa: E402,F401  (fixture `base` reaproveitada)


def _dc53_com_candidato(pasta):
    """RETO DC53 RJ em Itu com parcela de 400 kg 'IMP-DC53 30X500MM' e um ÚNICO lote DC53 31X500 na ESTOQUE 2026
    (o candidato da origem corrigida). Pela spec v3.5 §10.8 o RETO não ganha lote-pai por candidato único."""
    import openpyxl
    from openpyxl.comments import Comment

    from app.carga import planilhas as P
    wb = openpyxl.load_workbook(pasta / P.ARQ_GERAL)
    ws = wb["Estoque Geral"]
    ws.append([90102, "IMP-DC53 RETO", None, 0, "KG", 0, None, 1022, None, None, None])
    ws.cell(ws.max_row, 8).comment = Comment("Autor:\n400kg de sobra (MEDIDA ORIGINAL IMP-DC53 30X500MM)", "x")
    wb.save(pasta / P.ARQ_GERAL)
    wb = openpyxl.load_workbook(pasta / P.ARQ_ESTOQUE)
    wb["ESTOQUE 2026"].append(["CT77TS", "DC53 31X500", 9, 1, 700, 700, None, None, 700])
    wb.save(pasta / P.ARQ_ESTOQUE)


def _main(tmp_path, monkeypatch, *extra):
    from app.carga import __main__ as cli
    monkeypatch.setattr(cli, "_kardex", lambda: (lambda _c: None))
    saida = tmp_path / "saida"
    saida.mkdir(exist_ok=True)
    return cli.main(["--pasta", str(tmp_path), "--saida", str(saida), "--sem-conferir-ops", *extra]), saida


def test_carga_cli_correcoes_ilegivel_para(base, tmp_path, monkeypatch):  # noqa: F811
    _planilhas(tmp_path)
    ruim = tmp_path / "corr.json"
    ruim.write_text("{ isto não é json", encoding="utf-8")
    rc, saida = _main(tmp_path, monkeypatch, "--correcoes", str(ruim))
    assert rc == 2 and not list(saida.iterdir())                            # parou antes de gerar relatório
    rc, _ = _main(tmp_path, monkeypatch, "--correcoes", str(tmp_path / "nao_existe.json"))
    assert rc == 2


def test_carga_cli_correcoes_gravadas_e_reto_sem_pai(base, tmp_path, monkeypatch):  # noqa: F811
    import openpyxl
    from sqlalchemy import func, select

    from app.core.db import SessionLocal
    from app.models import Liga, Lote, Movimento, Nota
    with SessionLocal() as db:
        db.add(Liga(codigo="DC53", nome="DC53", densidade=7.8, apelidos=[]))
        db.commit()
    _planilhas(tmp_path)
    _dc53_com_candidato(tmp_path)
    corr = tmp_path / "corr.json"       # escrita diferente (minúsculas, espaços) e kg conferido: deve aplicar
    corr.write_text(json.dumps({"origem_reto": [
        {"linha_descricao": "imp-dc53  reto", "origem_planilha": "IMP-DC53 30 X 500MM",
         "origem_correta": "IMP-DC53 31X500MM", "kg": 400, "fonte": "teste fictício"}]}), encoding="utf-8")
    # a que não casa com nenhuma parcela agora bloqueia a carga (R053(4)): `test_r053_correcao_que_nao_casa_...`
    rc, saida = _main(tmp_path, monkeypatch, "--importar", "--correcoes", str(corr))
    assert rc == 0
    with SessionLocal() as db:
        lo = next(x for x in db.scalars(select(Lote).where(Lote.tipo == "RETO", Lote.planta_fiscal == "RJ"))
                  if (x.origem_ref or {}).get("bitola_origem") == "IMP-DC53 31X500MM")
        assert float(lo.saldo_kg) == 400 and lo.lote_pai_id is None and lo.origem_identificada is False
        nota = db.scalar(select(Nota.texto).where(Nota.entidade == "LOTE", Nota.entidade_id == lo.id))
        assert "teste fictício" in nota and "na planilha: IMP-DC53 30X500MM" in nota
        # conferência final do ensaio: nenhum saldo negativo e saldo = soma dos movimentos em todos os lotes
        for x in db.scalars(select(Lote)):
            soma = db.scalar(select(func.coalesce(func.sum(Movimento.kg), 0)).where(Movimento.lote_id == x.id))
            assert float(x.saldo_kg) >= 0 and round(float(soma), 3) == round(float(x.saldo_kg), 3)
    rel = next(saida.glob("carga_resultado_*.xlsx"))
    ws = openpyxl.load_workbook(rel, read_only=True)["Correções aplicadas"]
    linhas = [r for r in ws.iter_rows(values_only=True) if r and r[0] == "IMP-DC53 RETO"]
    assert len(linhas) == 1 and linhas[0][2] == "IMP-DC53 30X500MM" and linhas[0][3] == "IMP-DC53 31X500MM"


def test_carga_correcao_com_kg_diferente_nao_aplica(base, tmp_path):  # noqa: F811
    from datetime import date

    from app.carga import planilhas as P
    from app.carga import plano
    _planilhas(tmp_path)
    _dc53_com_candidato(tmp_path)
    corr = {"origem_reto": [{"linha_descricao": "IMP-DC53 RETO", "origem_planilha": "IMP-DC53 30X500MM",
                             "origem_correta": "IMP-DC53 31X500MM", "kg": 401, "fonte": "kg errado"}]}
    ctx = plano.Contexto({"H13": 7.8, "A8": 7.85, "A8MOD": 7.85, "DC53": 7.8}, {}, None, lambda _o: None,
                         date(2026, 11, 12), correcoes=corr)
    e, h = P.ler_estoque_2026(tmp_path)
    pl = plano.montar(ctx, e, h, P.ler_geral(tmp_path), P.ler_corte(tmp_path), P.ler_sa(tmp_path))
    assert pl.correcoes_aplicadas == []
    assert any((lp.origem or {}).get("bitola_origem") == "IMP-DC53 30X500MM" for lp in pl.lotes)
