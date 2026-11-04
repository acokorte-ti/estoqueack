"""T25 Carga inicial com planilhas sintéticas (as reais têm dados da empresa e não vão para o repositório)."""
from datetime import date, datetime

import pytest

pytest.importorskip("openpyxl")
pytest.importorskip("fastapi")


def _planilhas(pasta, *, cabecalho_ct="CONTÊINER"):
    import openpyxl
    from openpyxl.comments import Comment

    from app.carga import planilhas as P

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "ESTOQUE 2026"
    ws.append([cabecalho_ct, "MATÉRIA PRIMA", "VALOR UNITÁRIO", "QUANTIDADE CHAPA/BARRA", "PESO INICIAL",
               "TOTAL EM ESTOQUE (KG)", "ORDENS DE PRODUÇÃO", None, "TOTAL EM ESTOQUE (KG)"])
    ws.append(["CH33K", "H13 33X105", 8.5, 3, 1000, 820, 100, 80, 820])
    ws["G2"].comment = Comment("Autor:\nOP 100592\n28/10", "x")
    ws["H2"].comment = Comment("Autor:\nSEM OP\n04/06", "x")
    ws.append(["CH40SH", "A8 MOD 21x204x1110 Múltiplo", 9, 2, 500, 500, None, None, 500])
    h = wb.create_sheet("HISTORICO")
    h.append(["DATA DE ENTRADA", "CT", "DESCRIÇÃO", "QUANTIDADE CHAPA/BARRA", "ENTRADA", "TOTAL EM SUCATA",
              "TOTAL EM ESTOQUE", "Observações", "HISTÓRICO"])
    h.append([datetime(2025, 1, 10), "CH33K", "H13 33X105", 3, 1000, None, None, None, None])
    h.append([datetime(2024, 5, 1), "CH20K", "D2 Ø90", 1, 300, 10, None, "acabou", None])
    wb.save(pasta / P.ARQ_ESTOQUE)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Estoque Geral"
    ws.append(["ITEM", "DESCRIÇÃO", "COMPR. FIXADOS (MM)", "ESTOQUE MEGA", "UM", "ESTOQUE RJ (no Rio)", "OBSERVAÇÕES",
               "ESTOQUE RJ (em Itu)", "OBSERVAÇÕES", "CLIENTES / USO", "OBS:"])
    ws.append([78290, "IMP-H13 24X62MM", None, 5198, "KG", 0, None, 0, None, None, None])
    ws.append([1698, "IMP-H13 RETO", None, 2240, "KG", 0, None, 120.5, None, None, None])
    ws.append([4242, "IMP-H13 33X105MM", "MULT. 1820", 0, "KG", 820, "não usar para guilhotinas", 0, None, None, None])
    ws.append([4243, "IMP-A8 21X203X1110MM MULT.", None, 0, "KG", 500, None, 0, None, None, None])
    wb.save(pasta / P.ARQ_GERAL)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "CONTROLE - CORTE RJ"
    ws.append([])
    ws.append([])
    ws.append([])
    ws.append([])
    ws.append(["DATA SOLICITADA", "OP", "Item", "MEDIDA ACABADA", "Peso previsto (acabado)", "QTD", "MP", "CT", "PESO",
               "CLIENTE", "INFORMAÇÕES DO CORTE", "PRAZO", "QTDE PEÇAS CORTADAS", "DATA DE LIBERAÇÃO", "OBSERVAÇÃO",
               "PESO2", "LIBERAÇÃO FEITA", "RECEBIDO ACK?", "STATUS"])
    ws.append([datetime(2026, 10, 23), 100592, 19918, "32X99,5X155", None, 10, "H13 33X105", "CH33K",
               "INFORMAR APÓS CORTE", "GERDAU", "10 PEÇAS COM 160MM COMPRIMENTO", datetime(2026, 12, 3), 10,
               datetime(2026, 10, 28), "COP 600", 100, True, True, "Recebido em Itu"])
    ws.append([datetime(2026, 10, 29), 100664, 70536, "32X100X300", None, 4, "H13 33X105", "CH33K",
               "INFORMAR APÓS CORTE", "DALLEACO", "04 PEÇAS COM 305MM COMPRIMENTO", datetime(2026, 12, 10), None,
               None, "EM PROCESSO", None, False, False, "Normal (5 dias)"])
    ws.append([datetime(2026, 10, 29), 100700, 1, "10X10X10", None, 1, "XYZ 1X1", "CH99ZZ",
               "INFORMAR APÓS CORTE", "X", "01 PEÇA", None, None, None, None, None, False, False, "Normal"])
    wb.save(pasta / P.ARQ_CORTE)

    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for aba in P.ABAS_SA:
        ws = wb.create_sheet(aba)
        ws.append(list(P.COLS_SA.values()) + ["NF FIOCERTO/MEDIO VALE"])
    ws.append([datetime(2026, 10, 28), 100592, "GERDAU", 19918, "H13", "33X105", "CH33K", 10, 100, 12.5, 37983,
               "SA PECA - CÓD.19918", 84669490, 0.12, 0, None, 3215])
    wb.save(pasta / P.ARQ_SA)


def _rodar(pasta, *, limpar=False):
    from app.carga import gravar, planilhas, plano
    from app.core.db import SessionLocal
    from app.models import Liga
    with SessionLocal() as db:
        ligas = {l.codigo: float(l.densidade) for l in db.query(Liga)}
        ctx = plano.Contexto(ligas, {78290: {"saldo_kg": 5198.0, "descricao": "IMP-H13 24X62MM"},
                                     1698: {"saldo_kg": 2240.042, "descricao": "IMP-H13 RETO"}},
                             "2026-11-03", lambda op: op != 100700, date(2026, 11, 3))
        e, h = planilhas.ler_estoque_2026(pasta)
        pl = plano.montar(ctx, e, h, planilhas.ler_geral(pasta), planilhas.ler_corte(pasta), planilhas.ler_sa(pasta))
        if limpar:
            gravar.limpar(db)
        gravar.gravar(db, pl, usuario_id=None, arquivos={})
        conf = gravar.conferencia_banco(db)
        db.commit()
        return pl, conf


@pytest.fixture()
def base(client):
    from app.core.db import SessionLocal
    from app.models import Liga, MegaSaldo
    with SessionLocal() as db:
        for c, d in (("H13", 7.8), ("A8", 7.85), ("A8MOD", 7.85), ("D2", 7.7)):
            db.add(Liga(codigo=c, nome=c, densidade=d, apelidos=[]))
        db.add_all([MegaSaldo(codigo=78290, saldo_kg=5198.0, descricao="IMP-H13 24X62MM"),
                    MegaSaldo(codigo=1698, saldo_kg=2240.042, descricao="IMP-H13 RETO")])
        db.commit()
    return client


def test_carga_completa_e_reexecutavel(base, tmp_path):
    from sqlalchemy import func, select

    from app.core.db import SessionLocal
    from app.models import CadastroSa, Cop, Destinacao, Lote, Movimento, ParidadeRj, SolicitacaoCorte
    _planilhas(tmp_path)
    pl, conf = _rodar(tmp_path)
    tipos = {p.tipo for p in pl.pendencias}
    assert {"SEM_OP", "SOLICITACAO_SEM_LOTE", "OP_MAL_DIGITADA", "RJ_EM_ITU_SEM_ORIGEM", "PARIDADE_SEM_CM",
            "RESTRICAO_A_REVISAR"} <= tipos
    par = {p["descricao_rj"]: p for p in pl.paridades}
    assert par["A8 MOD 21x204x1110 Múltiplo"]["cm"] is None      # medidas não se juntam (§10.7): só no RJ
    c = {x["conferencia"][:3]: x for x in pl.conferencias}
    assert c["(b)"]["resultado"] == "OK" and c["(c)"]["resultado"] == "OK"
    assert conf[0]["resultado"] == "OK"                          # (a) lotes Mega = saldo Mega
    with SessionLocal() as db:
        rio = db.scalar(select(func.sum(Lote.saldo_kg)).where(Lote.planta_fiscal == "RJ", Lote.local_fisico == "RJ"))
        assert float(rio) == 1320                                # 820 + 500 (o esgotado do HISTORICO fica com 0)
        assert db.scalar(select(func.count(Lote.id)).where(Lote.status == "ESGOTADO")) == 1
        itu = db.scalars(select(Lote).where(Lote.planta_fiscal == "RJ", Lote.local_fisico == "ITU")).all()
        assert len(itu) == 1 and itu[0].saldo_kg == 120.5 and itu[0].origem_identificada is False
        reto = db.scalar(select(Lote).join(Lote.item).where(Lote.planta_fiscal == "ITU", Lote.tipo == "RETO"))
        assert reto is not None and reto.saldo_kg == 2240.042
        sols = {s.op: s for s in db.scalars(select(SolicitacaoCorte))}
        assert sols[100592].situacao == "CONCLUIDA" and sols[100664].situacao == "ENVIADA" and 100700 not in sols
        mov = db.scalar(select(Movimento).where(Movimento.op == 100592))
        assert mov.liberacao_id is not None and mov.solicitacao_id == sols[100592].id
        assert db.scalar(select(Cop.numero)) == 600
        sa = db.scalar(select(CadastroSa))
        assert sa.sa_codigo == 37983 and sa.solicitacao_id == sols[100592].id and sa.situacao == "CONFIRMADO"
        assert db.scalar(select(func.count(Destinacao.id))) == 1
        assert db.scalar(select(func.count(ParidadeRj.id))) == 2
        n_lotes = db.scalar(select(func.count(Lote.id)))
    # roda de novo: limpa e recarrega igual
    _rodar(tmp_path, limpar=True)
    with SessionLocal() as db:
        assert db.scalar(select(func.count(Lote.id))) == n_lotes
        assert db.scalar(select(func.count(SolicitacaoCorte.id))) == 2


def test_estrutura_mudou_para_a_carga(tmp_path):
    from app.carga import planilhas
    _planilhas(tmp_path, cabecalho_ct="CONTAINER")
    with pytest.raises(planilhas.EstruturaMudou):
        planilhas.ler_estoque_2026(tmp_path)


def test_fila_e_cortes_prontos_depois_da_carga(base, tmp_path):
    from tests.conftest import preparar_admin
    _planilhas(tmp_path)
    _rodar(tmp_path)
    preparar_admin(base)
    fila = base.get("/api/fila-rj").json()
    assert [f["op"] for f in fila] == [100664] and fila[0]["reserva_kg"] > 0
    assert base.get("/api/cops/cortes-prontos").json() == []          # o corte histórico já está no COP 600

def test_carga_nao_conta_como_excecao(base, tmp_path):
    from app.core.db import SessionLocal
    from app.services import painel
    _planilhas(tmp_path)
    _rodar(tmp_path)
    with SessionLocal() as db:
        assert painel.excecoes_da_semana(db) == []


def test_r036_ordem_estorno_nf_do_cop(base, tmp_path):
    from sqlalchemy import select

    from app.core.db import SessionLocal
    from app.models import CadastroSa, Cop, CopItem, Lote, Movimento
    from app.services import estoque
    from tests.conftest import preparar_admin
    _planilhas(tmp_path)
    _rodar(tmp_path)
    with SessionLocal() as db:
        lote = db.scalar(select(Lote).where(Lote.peso_inicial_kg == 1000, Lote.planta_fiscal == "RJ"))
        movs = estoque.movimentos(db, lote.id)
        assert movs[0]["tipo"] == "SALDO_INICIAL" and movs[0]["data"] == "2025-01-10"   # entrada do HISTORICO
        assert all(m["saldo_apos_kg"] >= 0 for m in movs)
        assert not any(m["estornavel"] for m in movs) and all(m["da_carga"] for m in movs)
        for l in db.scalars(select(Lote)):                       # nenhum movimento da carga é estornável
            assert not any(m["estornavel"] for m in estoque.movimentos(db, l.id)), l.codigo
        mov_id = db.scalar(select(Movimento.id).where(Movimento.lote_id == lote.id, Movimento.tipo == "SAIDA_CORTE_RJ"))
        item = db.scalar(select(CopItem).join(Cop).where(Cop.numero == 600))
        sa = db.scalar(select(CadastroSa))
        assert item.nf is not None and item.nf.numero == "3215" and sa.nf_id == item.nf_id and sa.cop_item_id == item.id
    h = preparar_admin(base)
    r = base.post(f"/api/movimentos/{mov_id}/estorno", json={"justificativa": "Teste de estorno da carga"}, headers=h)
    assert r.status_code == 400 and "ajuste" in r.json()["detail"]
    assert base.get("/api/cops").json()[0]["nfs"]


def test_r038_revisao_do_fabiano(base, tmp_path):
    """Paridade sem múltiplo, kardex de 2 anos, densidades revistas, CPR fora, solicitações revistas."""
    from app.carga import planilhas, plano
    from app.core.db import SessionLocal
    from app.models import Liga
    _planilhas(tmp_path)
    import openpyxl
    from app.carga import planilhas as P
    wb = openpyxl.load_workbook(tmp_path / P.ARQ_GERAL)
    ws = wb.active
    ws.append([4244, "IMP-A8 21X203MM", None, 0, "KG", 0, "RESERVADO CPR", 0, None, None, None])
    wb.save(tmp_path / P.ARQ_GERAL)
    wb = openpyxl.load_workbook(tmp_path / P.ARQ_ESTOQUE)
    wb["ESTOQUE 2026"].append(["CH50XX", "A8 MOD 21x203", 9, 1, 300, 300, None, None, 300])
    wb.save(tmp_path / P.ARQ_ESTOQUE)
    with SessionLocal() as db:
        ligas = {l.codigo: float(l.densidade) for l in db.query(Liga)}
    mega = {78290: {"saldo_kg": 10.0, "descricao": "IMP-H13 24X62MM"},
            90001: {"saldo_kg": 12.0, "descricao": "BRONZE TM23 RED 50MM"},
            90002: {"saldo_kg": 30.0, "descricao": "SAE-4130 RED 457,2MM"},
            90003: {"saldo_kg": 5.0, "descricao": "CANTONEIRA 2X2"}}
    ctx = plano.Contexto(ligas, mega, "2026-11-04", lambda op: True, date(2026, 11, 4),
                         lambda cods: {90001, 90003})                       # 90002 sem movimento em 2 anos
    e, h = planilhas.ler_estoque_2026(tmp_path)
    pl = plano.montar(ctx, e, h, planilhas.ler_geral(tmp_path), planilhas.ler_corte(tmp_path),
                      planilhas.ler_sa(tmp_path))
    par = {p["descricao_rj"]: p for p in pl.paridades}
    assert par["A8 MOD 21x203"]["cm"] == 4244                              # comum → comum, nunca o múltiplo 4243
    entraram = {k["codigo"]: k for k in pl.kardex_entraram}
    assert set(entraram) == {90001, 90003}
    assert entraram[90001]["liga"] == "BRONZE" and entraram[90001]["densidade"] == 8.8
    assert entraram[90003]["liga"] == "NAO-INFORMADA"
    assert any(p.tipo == "CM_FORA_SEM_MOVIMENTO" and "90002" in p.descricao for p in pl.pendencias)
    assert not any("CPR" in d for l in pl.lotes for _, d in l.destinacoes)
    sem_kardex = plano.Contexto(ligas, mega, "2026-11-04", lambda op: True, date(2026, 11, 4))
    pl2 = plano.montar(sem_kardex, e, h, planilhas.ler_geral(tmp_path), planilhas.ler_corte(tmp_path),
                       planilhas.ler_sa(tmp_path))
    assert any(p.tipo == "SEM_KARDEX" and p.gravidade == "BLOQUEIA" for p in pl2.pendencias)
