"""Spec v3.15 (R074–R076, contrato §16.4): entrada enriquecida (T06, T15), T05 "Entrada e documentos",
"Completar dados da entrada" e documentos anexos. Dados fictícios."""
import io
from datetime import date, timedelta

import pytest

from tests.fluxo_util import catalogo_e_lotes, criar_usuarios, entrar

pytest.importorskip("fastapi")

PDF = b"%PDF-1.4\n% teste ficticio\n" + b"0" * 200
XLSX = b"PK\x03\x04" + b"1" * 200
HOJE = date.today()


def _db():
    from app.core.db import SessionLocal
    return SessionLocal()


@pytest.fixture()
def amb(client):
    u = criar_usuarios(client)
    ids = catalogo_e_lotes()
    yield client, u, ids


def _corpo(**kw) -> dict:
    c = {"numero": "54321", "serie": "1", "data_emissao": (HOJE - timedelta(days=2)).isoformat(),
         "data": HOJE.isoformat(), "fornecedor": "Fornecedor Ficticio", "cnpj": "12.345.678/0001-90",
         "chave_nfe": "3526 1112 3456 7800 0190 5500 1000 0543 2110 0000 0001", "conteiner": "CH81TS",
         "packing_list": "PL-001", "di_duimp": "26/0000001-0", "observacao": "Chegou com chuva",
         "itens": [{"liga": "H13", "formato": "RETANGULAR", "espessura": 50, "largura": 610, "pecas": 4,
                    "peso_kg": 9000, "peso_bruto_kg": 9120, "ncm": "7228.30.00", "custo_kg": 42.5,
                    "descricao_nf": "ACO H13 50X610", "observacao": "Barra 3 amassada"}]}
    c.update(kw)
    return c


def _codigos(v: dict) -> list[str]:
    return [o["codigo"] for o in v["ocorrencias"]]


def _enviar(client, h, url, nome, dados, tipo="NF", descricao=None, ctype="application/pdf"):
    params = {"tipo": tipo, "nome": nome}
    if descricao:
        params["descricao"] = descricao
    return client.post(url, params=params, content=dados, headers={**h, "Content-Type": ctype})


def _entrada(client, h) -> tuple[int, int]:
    r = client.post("/api/entradas-nf", json=_corpo(), headers=h)
    assert r.status_code == 201, r.text
    return r.json()["id"], r.json()["itens"][0]["lote_id"]


def test_t06_ocorrencias_novas_e_dados_no_t05(amb):
    client, u, _ = amb
    h = entrar(client, u["rj"])
    ruim = _corpo(data_emissao=(HOJE + timedelta(days=1)).isoformat(), chave_nfe="123")
    ruim["itens"][0]["ncm"] = "7228.30.0"
    v = client.post("/api/entradas-nf/validar", json=ruim, headers=h).json()
    assert {"EMISSAO_FUTURA", "CHAVE_NFE_INVALIDA", "NCM_INVALIDO#1", "ENTRADA_ANTES_DA_EMISSAO"} <= set(_codigos(v))
    assert next(o for o in v["ocorrencias"] if o["codigo"] == "CHAVE_NFE_INVALIDA")["nivel"] == "ALERTA"
    sem_emissao = _corpo()
    del sem_emissao["data_emissao"]
    assert client.post("/api/entradas-nf/validar", json=sem_emissao, headers=h).status_code == 422
    v = client.post("/api/entradas-nf/validar", json=_corpo(), headers=h).json()
    assert v["ocorrencias"] == [], v

    eid, lote = _entrada(client, h)
    d = client.get(f"/api/lotes/{lote}/entrada", headers=h).json()
    assert d["origem"] == "T06" and d["da_origem"] is None and d["pode_completar"] is True
    e, it = d["entrada"], d["item"]
    assert (e["numero"], e["serie"], e["cnpj"], e["packing_list"], e["conteiner"]) == \
        ("54321", "1", "12345678000190", "PL-001", "CH81TS")
    assert len(e["chave_nfe"]) == 44 and e["data_entrada"] == HOJE.isoformat()
    assert (it["ncm"], it["peso_bruto_kg"], it["custo_kg"], it["observacao"]) == \
        ("72283000", 9120, 42.5, "Barra 3 amassada")
    assert d["custo_kg"] == 42.5 and d["anexos"] == []
    lista = client.get("/api/entradas-nf", headers=h).json()
    assert lista[0]["serie"] == "1" and lista[0]["itens"][0]["ncm"] == "72283000"

    # NF duplicada considera a série (se uma das duas não tiver série, é a mesma NF)
    assert "NF_DUPLICADA" not in _codigos(client.post("/api/entradas-nf/validar", json=_corpo(serie="2"),
                                                      headers=h).json())
    assert "NF_DUPLICADA" in _codigos(client.post("/api/entradas-nf/validar", json=_corpo(serie=" 1 "),
                                                  headers=h).json())
    assert "NF_DUPLICADA" in _codigos(client.post("/api/entradas-nf/validar",
                                                  json=_corpo(serie=None, fornecedor="FORNECEDOR FICTICIO"),
                                                  headers=h).json())
    f = client.get("/api/entradas-nf/fornecedores", headers=h).json()
    assert f == [{"fornecedor": "Fornecedor Ficticio", "cnpj": "12345678000190"}]
    q = {"liga": "H13", "formato": "RETANGULAR", "espessura": 50, "largura": 610}
    assert client.get("/api/entradas-nf/ultimo-ncm", params=q, headers=h).json() == {"ncm": "72283000"}
    assert client.get("/api/entradas-nf/ultimo-ncm", params={"liga": "H13"}, headers=h).json() == {"ncm": None}


def test_completar_dados_nao_mexe_no_saldo_e_fica_na_auditoria(amb):
    client, u, ids = amb
    from sqlalchemy import select

    from app.models import Auditoria
    h = entrar(client, u["itu"])
    l33 = ids["l33"]
    d = client.get(f"/api/lotes/{l33}/entrada", headers=h).json()
    assert d["entrada"] is None and d["origem"] is None and d["pode_completar"] is True
    r = client.patch(f"/api/lotes/{l33}/entrada", headers=h,
                     json={"numero": "777", "ncm": "72283000", "custo_kg": 30, "chave_nfe": "123",
                           "data_emissao": (HOJE - timedelta(days=5)).isoformat()})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["origem"] == "T05" and d["entrada"]["numero"] == "777" and d["item"]["ncm"] == "72283000"
    assert d["custo_kg"] == 30 and any("44 dígitos" in a for a in d["avisos"])
    lote = client.get(f"/api/lotes/{l33}", headers=h).json()
    assert lote["saldo_kg"] == 1000 and lote["custo_kg"] == 30 and lote["documento_entrada"] == "NF 777"
    with _db() as db:
        a = db.scalars(select(Auditoria).where(Auditoria.acao == "ENTRADA_COMPLETADA")).all()
        assert len(a) == 1 and a[0].depois["ncm"] == "72283000" and a[0].antes["custo_kg"] is None
    # segunda vez reaproveita a entrada T05
    r = client.patch(f"/api/lotes/{l33}/entrada", headers=h, json={"custo_kg": 31.5})
    assert r.status_code == 200 and r.json()["entrada"]["id"] == d["entrada"]["id"] and r.json()["custo_kg"] == 31.5
    assert client.patch(f"/api/lotes/{l33}/entrada", headers=h, json={"ncm": "12"}).status_code == 400
    assert client.patch(f"/api/lotes/{l33}/entrada", headers=h, json={}).status_code == 400
    futuro = (HOJE + timedelta(days=1)).isoformat()
    assert client.patch(f"/api/lotes/{l33}/entrada", headers=h, json={"data_entrada": futuro}).status_code == 400
    # saldo e identidade do lote não entram (campo desconhecido é ignorado; nada para mudar → 400)
    assert client.patch(f"/api/lotes/{l33}/entrada", headers=h, json={"peso_kg": 1}).status_code == 400


def _filho(origem_id: int) -> int:
    from app.models import Lote
    from app.services import movimentos as mov
    with _db() as db:
        pai = db.get(Lote, origem_id)
        f = mov.criar_lote(db, item=pai.item, planta_fiscal="RJ", local_fisico="ITU", tipo="SOBRA", pai=pai,
                           conteiner_id=pai.conteiner_id, peso_inicial_kg=10)
        mov.lancar(db, f, "GERA_SOBRA", 10, usuario_id=None)
        db.commit()
        return f.id


def test_anexos_ligacao_tipo_tamanho_apagar_e_restaurar(amb):
    client, u, ids = amb
    h = entrar(client, u["rj"])
    eid, lote = _entrada(client, h)
    r = _enviar(client, h, f"/api/entradas-nf/{eid}/anexos", "NF 54321.pdf", PDF)
    assert r.status_code == 201, r.text
    nf = r.json()
    assert nf["ligado_a"] == "ENTRADA" and nf["tamanho_bytes"] == len(PDF) and nf["usuario"]
    r = _enviar(client, h, f"/api/lotes/{lote}/anexos", "precificador.xlsx", XLSX, tipo="PRECIFICADOR",
                ctype="application/octet-stream")
    assert r.status_code == 201 and r.json()["ligado_a"] == "CONTEINER"
    prec = r.json()
    r = _enviar(client, h, f"/api/lotes/{lote}/anexos", "foto.png", PDF, tipo="OUTRO", descricao="Foto da barra")
    assert r.status_code == 400 and "PDF, JPG ou PNG" in r.json()["detail"]      # conteúdo não é PNG
    r = _enviar(client, h, f"/api/lotes/{lote}/anexos", "nf.xlsx", XLSX, tipo="NF")
    assert r.status_code == 400 and "XLS" in r.json()["detail"]                  # planilha só no precificador
    assert _enviar(client, h, f"/api/lotes/{lote}/anexos", "x.pdf", PDF, tipo="OUTRO").status_code == 400
    assert _enviar(client, h, f"/api/lotes/{lote}/anexos", "vazio.pdf", b"").status_code == 400
    r = _enviar(client, h, f"/api/lotes/{lote}/anexos", "nota.exe", b"MZ\x90\x00")
    assert r.status_code == 400
    from app.models import Parametro
    with _db() as db:
        db.add(Parametro(chave="ANEXO_MAX_MB", valor="0,0001", tipo="NUMERO", descricao="teste"))
        db.commit()
    r = _enviar(client, h, f"/api/lotes/{lote}/anexos", "grande.pdf", PDF)
    assert r.status_code == 400 and "o limite é" in r.json()["detail"] and "MB" in r.json()["detail"]
    with _db() as db:
        db.delete(db.get(Parametro, "ANEXO_MAX_MB"))
        db.commit()

    d = client.get(f"/api/lotes/{lote}/entrada", headers=h).json()
    assert {a["id"] for a in d["anexos"]} == {nf["id"], prec["id"]}
    r = client.get(f"/api/anexos/{nf['id']}/arquivo", headers=h)
    assert r.status_code == 200 and r.content == PDF and r.headers["content-type"] == "application/pdf"
    assert r.headers["content-disposition"].startswith("inline") and r.headers["x-content-type-options"] == "nosniff"
    assert client.get(f"/api/anexos/{nf['id']}/arquivo?baixar=true", headers=h).headers[
        "content-disposition"].startswith("attachment")
    item = next(i for i in client.get("/api/lotes", headers=h).json()["itens"] if i["id"] == lote)
    assert item["indicadores"]["anexo"] is True and item["custo_kg"] == 42.5

    # lote filho (sobra em Itu) mostra entrada, R$/kg e anexos da origem
    hi = entrar(client, u["itu"])
    filho = _filho(lote)
    d = client.get(f"/api/lotes/{filho}/entrada", headers=hi).json()
    assert d["da_origem"] and d["pode_completar"] is False and d["custo_kg"] == 42.5
    assert d["entrada"]["numero"] == "54321" and {a["da_origem"] for a in d["anexos"]} == {d["da_origem"]}
    assert client.patch(f"/api/lotes/{filho}/entrada", headers=hi, json={"ncm": "72283000"}).status_code == 400
    sob = next(i for i in client.get("/api/lotes", headers=hi).json()["itens"] if i["id"] == filho)
    assert sob["custo_kg"] == 42.5 and sob["indicadores"]["anexo"] is True
    assert sob["indicadores"]["precificador"] is True

    # apagar esconde (justificativa obrigatória); só o Admin vê e restaura
    h = entrar(client, u["rj"])
    assert client.post(f"/api/anexos/{nf['id']}/apagar", json={"justificativa": " "}, headers=h).status_code == 400
    r = client.post(f"/api/anexos/{nf['id']}/apagar", json={"justificativa": "Arquivo errado"}, headers=h)
    assert r.status_code == 200 and r.json()["apagado"] is True
    assert [a["id"] for a in client.get(f"/api/lotes/{lote}/entrada", headers=h).json()["anexos"]] == [prec["id"]]
    assert client.get(f"/api/anexos/{nf['id']}/arquivo", headers=h).status_code == 404
    assert client.post(f"/api/anexos/{nf['id']}/restaurar", headers=h).status_code == 403
    ha = entrar(client, u["admin"])
    apag = next(a for a in client.get(f"/api/lotes/{lote}/entrada", headers=ha).json()["anexos"]
                if a["id"] == nf["id"])
    assert apag["apagado"] is True and apag["justificativa"] == "Arquivo errado" and apag["apagado_por"]
    assert client.get(f"/api/anexos/{nf['id']}/arquivo", headers=ha).status_code == 200
    r = client.post(f"/api/anexos/{nf['id']}/restaurar", headers=ha)
    assert r.status_code == 200 and r.json()["apagado"] is False
    with _db() as db:
        from sqlalchemy import select

        from app.models import Auditoria
        acoes = set(db.scalars(select(Auditoria.acao).where(Auditoria.entidade == "anexo")))
        assert {"ANEXO_CRIADO", "ANEXO_APAGADO", "ANEXO_RESTAURADO"} <= acoes

    # sem login não abre
    client.post("/api/auth/logout", headers=ha)
    client.cookies.clear()
    assert client.get(f"/api/anexos/{nf['id']}/arquivo").status_code == 401


def test_operacao_rj_nao_ve_anexo_de_itu(amb):
    client, u, ids = amb
    h = entrar(client, u["itu"])
    r = _enviar(client, h, f"/api/lotes/{ids['lmega']}/anexos", "laudo.pdf", PDF, tipo="OUTRO",
                descricao="Laudo do fornecedor")
    assert r.status_code == 201 and r.json()["ligado_a"] == "LOTE"
    aid = r.json()["id"]
    h = entrar(client, u["rj"])
    assert client.get(f"/api/anexos/{aid}/arquivo", headers=h).status_code == 404
    assert client.get(f"/api/lotes/{ids['lmega']}/entrada", headers=h).status_code == 404
    assert _enviar(client, h, f"/api/lotes/{ids['lmega']}/anexos", "x.pdf", PDF).status_code == 404
    assert client.post(f"/api/anexos/{aid}/apagar", json={"justificativa": "x"}, headers=h).status_code == 404


def test_excel_por_lote_tem_rs_kg_valor_e_anexos(amb):
    import openpyxl
    client, u, _ = amb
    h = entrar(client, u["rj"])
    eid, lote = _entrada(client, h)
    _enviar(client, h, f"/api/lotes/{lote}/anexos", "prec.xlsx", XLSX, tipo="PRECIFICADOR")
    ws = openpyxl.load_workbook(io.BytesIO(client.get("/api/exportar/lotes.xlsx", headers=h).content)).active
    cab = [c.value for c in ws[1]]
    assert {"R$/kg", "Valor R$", "Tem precificador", "Anexos"} <= set(cab)
    linha = next(r for r in ws.iter_rows(min_row=2, values_only=True) if r[2] == "CH81TS")
    assert linha[cab.index("R$/kg")] == 42.5 and linha[cab.index("Valor R$")] == 382500
    assert linha[cab.index("Tem precificador")] == "Sim" and linha[cab.index("Anexos")] == "Sim"


def test_t15_criar_lote_grava_dados_da_entrada(client):
    from app.integrations.mega import fabrica
    from app.integrations.mega.gateway import MegaFalso, MovimentoMega, SaldoMega
    from app.services import sync_mega
    u = criar_usuarios(client)
    catalogo_e_lotes()                                   # código 78290 com lote de 5.198 kg
    d = HOJE - timedelta(days=3)
    mega = MegaFalso(saldos=[SaldoMega(78290, "IMP-H13 24X62MM", "KG", 6648.0, 7.9)],
                     movimentos=[MovimentoMega(1, d, "ED", 1, "Entrada por Compras", "NF77", 78290, 1450, None, False,
                                               d, None, 1)])
    fabrica.definir(mega)
    try:
        with _db() as db:
            assert sync_mega.sincronizar_estoque(db).situacao == "OK"
        h = entrar(client, u["itu"])
        pid = next(p for p in client.get("/api/entradas-mega", headers=h).json()["itens"] if p["codigo"] == 78290)["id"]
        url = f"/api/entradas-mega/{pid}/criar-lote"
        corpo = {"peso_kg": 1450, "conteiner": "CH77AB", "nf": "NF77", "ncm": "72283", "fornecedor": "Usina Ficticia",
                 "serie": "3", "packing_list": "PL-9", "di_duimp": "26/1", "custo_kg": 18.75}
        v = client.post(url + "/validar", json=corpo, headers=h).json()
        assert "NCM_INVALIDO" in _codigos(v)
        corpo["ncm"] = "7228.30.00"
        r = client.post(url, json=corpo, headers=h)
        assert r.status_code == 201, r.text
        lote = r.json()["lote"]["id"]
        e = client.get(f"/api/lotes/{lote}/entrada", headers=h).json()
        assert e["origem"] == "T15" and e["entrada"]["fornecedor"] == "Usina Ficticia" and e["entrada"]["serie"] == "3"
        assert e["entrada"]["numero"] == "NF77" and e["item"]["ncm"] == "72283000" and e["custo_kg"] == 18.75
        assert client.get(f"/api/lotes/{lote}", headers=h).json()["custo_kg"] == 18.75
        # a entrada da T15 não aparece na lista da T06
        assert client.get("/api/entradas-nf", headers=h).json() == []
        r = _enviar(client, h, f"/api/lotes/{lote}/anexos", "nf77.pdf", PDF)
        assert r.status_code == 201 and r.json()["ligado_a"] == "ENTRADA"
    finally:
        fabrica.definir(None)
