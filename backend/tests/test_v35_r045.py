"""Spec v3.5 (R045, P22(a), P24, P26 decisões do Eduardo de 2026-11-11) e revisão da 0007 (R044).

Dados fictícios: OPs, contêineres e pesos de exemplo (nada de dado real)."""
from __future__ import annotations

import pytest

from app.domain import regras
from app.domain.medidas import bitola_de_origem, chave_multiplo, interpretar
from tests.fluxo_util import catalogo_e_lotes, corpo_solicitacao, criar_usuarios, entrar, mega_falso

pytest.importorskip("fastapi")


# ---------------- domínio ----------------

def test_cr8mod_e_liga_distinta_de_cr8():
    assert interpretar("IMP-CR8MOD 7,5X55MM").liga == "CR8MOD"
    assert interpretar("CR8 MOD 7,5X87MM").liga == "CR8MOD"
    assert interpretar("CR8  13X510").liga == "CR8"


def test_redondo_so_com_marcador():
    m = interpretar("D6 97X2660")
    assert (m.formato, m.espessura, m.largura) == ("RETANGULAR", 97, 2660)
    m = interpretar("IMP-D2 RED 90X2425MM")
    assert (m.formato, m.diametro, m.comprimento) == ("REDONDO", 90, 2425)


def test_chave_multiplo():
    assert chave_multiplo("A8 MOD 21x204x1110 Múltiplo") == "1110"
    assert chave_multiplo("D2 FLAT BAR 4,8X600 (MÚLTIPLO DE 2020MM)") == "2020"
    assert chave_multiplo("H13 50X610", "MULT. 1820") == "1820"
    assert chave_multiplo("H13 50X610", "3110MM (MIN)") is None
    assert chave_multiplo("IMP-A8 21X203MM") is None


def test_chave_material_p28():
    from app.domain.medidas import chave_material
    def k(d):
        return chave_material(interpretar(d), d)
    assert k("1.2344 45,0 x 610mm") == k("IMP-H13 45X610MM")              # 1.2344 = H13, escrita não conta
    assert k("IMP-D2 RED 90X2425MM") != k("D2 Ø90")                       # comprimento informado diferencia
    assert k("A8 MOD 21x203") != k("IMP-A8 21X203MM")                     # MOD é outra liga
    assert k("H13 45X610") != k("H13 45X600") and k("D6 19x76,2") != k("D6 19,05x76,20")
    assert k("A8 21X204X1110MM MULT.") != k("A8 21X204X1110MM")           # múltiplo diferencia


def test_r055_item_sem_bitola_nao_quebra_a_chave():
    from app.domain.medidas import ChaveMaterial
    assert ChaveMaterial("4140", "RETANGULAR", None, None, None, None, False).texto == "4140 SEM BITOLA"
    assert ChaveMaterial("CR8", "REDONDO", None, None, None, None, False).texto == "CR8 SEM BITOLA"


def test_bitola_de_origem_normalizada():
    assert bitola_de_origem("IMP-D2 25X610MM", "D2") == bitola_de_origem("d2 25 x 610", "D2") == "25X610"
    assert bitola_de_origem("IMP-D2 30,5x610MM", "D2") == "30,5X610"
    assert bitola_de_origem("IMP-D2 36X510MM", "DC53") == "D2 36X510"
    assert bitola_de_origem("IMP-D2 45x510~610MM", "D2") == "IMP-D245X510~610MM"


def test_tolerancia_com_limite_na_mensagem():
    r = regras.validar_peso_real(100, 109, 8, limite_de="material do RJ")
    o = r.ocorrencias[0]
    assert o.codigo == "EXCESSO_TOLERANCIA" and "Limite: 8 % para material do RJ" in o.mensagem
    assert o.dados["limite_pct"] == 8
    assert not regras.validar_peso_real(100, 107.5, 8).ocorrencias


def test_barra_mais_leve_que_peca():
    o = regras.validar_barra_inteira(837, 800).ocorrencias
    assert [x.codigo for x in o] == ["BARRA_MAIS_LEVE_QUE_PECA"] and o[0].nivel.value == "ALERTA"
    assert not regras.validar_barra_inteira(837, 1288).ocorrencias


# ---------------- API ----------------

@pytest.fixture()
def amb(client):
    u = criar_usuarios(client)
    ids = catalogo_e_lotes()
    from app.core.db import SessionLocal
    from app.models import Lote
    from app.services import movimentos as mov
    with SessionLocal() as db:      # lote RJ em Itu, mesma liga e bitola do l33 (H13 33x105)
        item = db.get(Lote, ids["l33"]).item
        lote = mov.criar_lote(db, item=item, planta_fiscal="RJ", local_fisico="ITU", peso_inicial_kg=200)
        mov.lancar(db, lote, "SALDO_INICIAL", 200, usuario_id=None)
        db.commit()
        ids["litu"] = lote.id
    fab = mega_falso()
    yield client, u, ids, fab
    fab.definir(None)


def _codigos(v):
    return [o["codigo"] for o in v["ocorrencias"]]


def test_t13_oito_pct_no_material_rj_cinco_no_mega(amb):
    client, u, ids, _ = amb
    h = entrar(client, u["itu"])
    base = {"op": 100508, "pecas": 1, "previsto_kg": 100, "sobra_kg": 0}
    v = client.post("/api/cortes-itu/validar", headers=h,
                    json={**base, "lote_id": ids["litu"], "consumo_kg": 107, "peso_usado_kg": 110}).json()
    assert "EXCESSO_TOLERANCIA" not in _codigos(v) and v["resultado"]["tolerancia_excesso_pct"] == 8
    v = client.post("/api/cortes-itu/validar", headers=h,
                    json={**base, "lote_id": ids["litu"], "consumo_kg": 109, "peso_usado_kg": 110}).json()
    exc = next(o for o in v["ocorrencias"] if o["codigo"] == "EXCESSO_TOLERANCIA")
    assert "8 % para material do RJ" in exc["mensagem"]
    v = client.post("/api/cortes-itu/validar", headers=h,
                    json={**base, "lote_id": ids["lmega"], "consumo_kg": 107, "peso_usado_kg": 110}).json()
    assert "EXCESSO_TOLERANCIA" in _codigos(v) and v["resultado"]["tolerancia_excesso_pct"] == 5


def test_t13_limite_rj_vem_do_parametro(amb):
    client, u, ids, _ = amb
    from app.core.db import SessionLocal
    from app.models import Parametro
    with SessionLocal() as db:
        db.add(Parametro(chave="TOLERANCIA_EXCESSO_RJ_INTEIRO_PCT", valor="10", tipo="NUMERO", descricao="t"))
        db.commit()
    h = entrar(client, u["itu"])
    v = client.post("/api/cortes-itu/validar", headers=h, json={"op": 100508, "pecas": 1, "previsto_kg": 100,
                                                                "lote_id": ids["litu"], "consumo_kg": 109,
                                                                "peso_usado_kg": 110}).json()
    assert "EXCESSO_TOLERANCIA" not in _codigos(v)


def test_sugestao_agrupada_por_liga_e_bitola(amb):
    client, u, ids, _ = amb
    h = entrar(client, u["itu"])
    r = client.get("/api/lotes/compativeis", headers=h,
                   params={"liga": "H13", "formato": "RETANGULAR", "espessura": 30, "largura": 100,
                           "comprimento": 250, "quantidade": 12, "peso_necessario_kg": 2000}).json()
    # P28 (2026-11-11): 1.2344 = H13 na mesma linha; o lote equivalente vem marcado dentro do grupo
    g = next(x for x in r["grupos"] if x["chave"] == "H13 33X105")
    assert g["estoques"]["RJ_NO_RIO"]["disponivel_kg"] == 1700 and g["estoques"]["ITU"]["disponivel_kg"] == 200
    assert g["total_disponivel_kg"] == 1900 and g["falta_kg"] == 100 and "falta 100,0 kg" in g["frase"]
    assert {x["conteiner"] for x in g["estoques"]["RJ_NO_RIO"]["lotes"]} == {"CH33K", "CH40SH"}
    assert g["liga_equivalente"] is False
    assert "1.2344" in {x["liga"] for x in g["estoques"]["RJ_NO_RIO"]["lotes"]}            # mesma liga (P28(1))
    assert not any(x["liga_equivalente"] for x in g["estoques"]["RJ_NO_RIO"]["lotes"])
    assert {x["chave"] for x in r["grupos"]} >= {"H13 33X105", "H13 70X610"}       # bitolas nunca se juntam


def test_consumo_misto_sem_op_duplicada_e_marca(amb):
    client, u, ids, _ = amb
    h = entrar(client, u["itu"])
    c = client.post("/api/cortes-itu", headers=h, json={"op": 100592, "lote_id": ids["litu"], "consumo_kg": 40,
                                                        "peso_usado_kg": 40, "pecas": 2, "consumo_misto": True})
    assert c.status_code == 201, c.text
    assert c.json()["consumo_misto"] is True and c.json()["sa_id"]          # parte de Itu: caminho B2
    sem = client.post("/api/solicitacoes/validar", headers=h, json=corpo_solicitacao(ids["l33"])).json()
    assert "OP_DUPLICADA" in _codigos(sem)
    corpo = corpo_solicitacao(ids["l33"], consumo_misto=True)
    com = client.post("/api/solicitacoes/validar", headers=h, json=corpo).json()
    assert "OP_DUPLICADA" not in _codigos(com)
    r = client.post("/api/solicitacoes", headers=h, json={**corpo, "confirmacoes": {
        o["codigo"]: "ok" for o in com["ocorrencias"] if o["nivel"] == "CIENCIA"}})
    assert r.status_code == 201, r.text
    s = r.json()["solicitacoes"][0]
    assert s["consumo_misto"]["itu_kg"] == 40 and s["consumo_misto"]["rj_kg"] == s["peso_previsto_kg"]
    assert s["consumo_misto"]["texto"].startswith("OP com consumo misto: Itu 40,0 kg + RJ ")
    lista = client.get("/api/solicitacoes", headers=h, params={"op": 100592}).json()
    assert lista["itens"][0]["consumo_misto"]["itu_kg"] == 40


# ---------------- carga ----------------

def test_estoque_geral_com_nome_variavel(tmp_path):
    from app.carga import planilhas as P
    (tmp_path / "Materia Prima Geral 05nov.xlsx").write_bytes(b"")
    (tmp_path / "~$Materia Prima Geral 05nov.xlsx").write_bytes(b"")
    assert P.arquivo_geral(tmp_path) == "Materia Prima Geral 05nov.xlsx"
    (tmp_path / "Materia Prima Geral 20out.xlsx").write_bytes(b"")
    with pytest.raises(P.EstruturaMudou):
        P.arquivo_geral(tmp_path)


# ---------------- R044: pendencia_mega ----------------

def test_uma_entrada_aberta_por_codigo(client):
    from sqlalchemy.exc import IntegrityError

    from app.core.db import SessionLocal
    from app.models import PendenciaMega
    with SessionLocal() as db:
        db.add(PendenciaMega(tipo="ENTRADA", codigo=4242, kg=10, situacao="ABERTA"))
        db.add(PendenciaMega(tipo="ENTRADA", codigo=4242, kg=10, situacao="DESCARTADA", motivo="OUTRO"))
        db.commit()
        db.add(PendenciaMega(tipo="ENTRADA", codigo=4242, kg=12, situacao="ABERTA"))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        db.add(PendenciaMega(tipo="ENTRADA", codigo=4243, kg=12, situacao="XPTO"))
        with pytest.raises(IntegrityError):
            db.commit()


def test_p29_comprimento_do_historico_e_faixa():
    from app.carga import planilhas as P
    from app.carga.plano import _comprimentos_historico, chave_mat
    from app.domain.medidas import comprimento_texto
    assert interpretar("D2 Ø90×2425mm").comprimento == 2425                      # × = X
    assert comprimento_texto("H13 55x610x2800-6000", "RETANGULAR") == "2800-6000"
    assert comprimento_texto("A8 MOD 7.2x86x3230-4080mm", "RETANGULAR") == "3230-4080"
    e = P.LinhaEstoque2026(7, "CT01X", "D2 Ø90", None, 2, 300.0, 250.0, [], None, {"linha": 7})
    h = [{"linha": 3, "conteiner": "CT01X", "descricao": "D2 Ø90×2425mm", "entrada": 300.0},
         {"linha": 4, "conteiner": "CT02X", "descricao": "D2 Ø90×3000mm", "entrada": 10.0}]
    itu = [P.LinhaGeral(5, 90001, "IMP-D2 RED 90X2425MM", None, 0.0, 0.0, 0.0, None, None, None, None, [], {})]
    m = _comprimentos_historico([e], h, itu)
    assert m[7]["texto"] == "2425" and m[7]["usado"] and [x["linha"] for x in m[7]["hist"]] == [3]   # mesmo CT
    assert chave_mat("D2 Ø90", comprimento=m[7]["texto"]) == chave_mat("IMP-D2 RED 90X2425MM")
    # P31: Itu sem comprimento na descrição → ignorado na paridade; vários comprimentos → ignorado
    sem = [P.LinhaGeral(5, 90001, "IMP-D2 RED 90MM", None, 0.0, 0.0, 0.0, None, None, None, None, [], {})]
    assert _comprimentos_historico([e], h, sem)[7]["usado"] is False
    h2 = h + [{"linha": 5, "conteiner": "CT01X", "descricao": "D2 Ø90×3000mm", "entrada": 5.0}]
    assert _comprimentos_historico([e], h2, itu)[7]["usado"] is False
    assert chave_mat("H13 55x610x2800-6000") != chave_mat("H13 55x610x2800-5000")  # faixa diferente


def test_correcoes_da_carga_por_arquivo(tmp_path):
    """Correção respondida (fora do repo, `--correcoes`) troca a origem da parcela; a planilha fica como está."""
    from datetime import date

    from app.carga import planilhas as P
    from app.carga import plano
    from tests.test_auditoria_0611_banco import _com_reto_d2_dc53
    from tests.test_carga import _planilhas
    _planilhas(tmp_path)
    _com_reto_d2_dc53(tmp_path)
    corr = {"origem_reto": [{"linha_descricao": "IMP-DC53 RETO", "origem_planilha": "IMP-DC53 30X500MM",
                             "origem_correta": "IMP-DC53 31X500MM", "kg": 400, "fonte": "teste"}]}
    ctx = plano.Contexto({}, {}, None, lambda _o: None, date(2026, 11, 11), correcoes=corr)
    e, h = P.ler_estoque_2026(tmp_path)
    pl = plano.montar(ctx, e, h, P.ler_geral(tmp_path), P.ler_corte(tmp_path), P.ler_sa(tmp_path))
    lote = next(lp for lp in pl.lotes if (lp.origem or {}).get("bitola_origem") == "IMP-DC53 31X500MM")
    assert lote.saldo == 400 and any("na planilha: IMP-DC53 30X500MM" in n for n in lote.notas)
    assert pl.correcoes_aplicadas[0]["antes"] == "IMP-DC53 30X500MM"
    assert any(p.tipo == "CORRECAO_APLICADA" for p in pl.pendencias)


def test_r053_correcao_que_nao_casa_bloqueia_a_carga(tmp_path):
    """R053(4): correção do --correcoes sem parcela igual vira BLOQUEIA e a gravação é recusada."""
    from datetime import date

    from app.carga import gravar as G
    from app.carga import planilhas as P
    from app.carga import plano
    from tests.test_auditoria_0611_banco import _com_reto_d2_dc53
    from tests.test_carga import _planilhas
    _planilhas(tmp_path)
    _com_reto_d2_dc53(tmp_path)
    corr = {"origem_reto": [{"linha_descricao": "IMP-DC53 RETO", "origem_planilha": "IMP-DC53 99X999MM",
                             "origem_correta": "IMP-DC53 31X500MM", "kg": 400, "fonte": "teste"}]}
    ctx = plano.Contexto({}, {}, None, lambda _o: None, date(2026, 11, 11), correcoes=corr)
    e, h = P.ler_estoque_2026(tmp_path)
    pl = plano.montar(ctx, e, h, P.ler_geral(tmp_path), P.ler_corte(tmp_path), P.ler_sa(tmp_path))
    assert [p.gravidade for p in pl.pendencias if p.tipo == "CORRECAO_NAO_APLICADA"] == ["BLOQUEIA"]
    with pytest.raises(G.CargaRecusada, match="Correção não aplicada"):
        G.gravar(None, pl, usuario_id=None, arquivos={})


def test_r055_t04_com_item_mega_sem_bitola(amb):
    client, u, ids, _ = amb
    from app.core.db import SessionLocal
    from app.models import ItemMP, Liga
    from app.services import movimentos as mov
    with SessionLocal() as db:
        lg = Liga(codigo="4140", nome="4140", densidade=7.85, apelidos=[])
        db.add(lg)
        db.flush()
        it = ItemMP(descricao="4140 BARRA", liga_id=lg.id, formato="RETANGULAR", codigo_mega=99001)
        db.add(it)
        db.flush()
        lote = mov.criar_lote(db, item=it, planta_fiscal="ITU", local_fisico="ITU", peso_inicial_kg=10)
        mov.lancar(db, lote, "SALDO_INICIAL", 10, usuario_id=None)
        db.commit()
    h = entrar(client, u["itu"])
    assert client.get("/api/lotes", headers=h).status_code == 200
    g = client.get("/api/lotes/agrupado", headers=h, params={"liga": "4140"}).json()["itens"]
    assert g[0]["chave"] == "4140 SEM BITOLA" and g[0]["codigos_itu"] == [99001]
