"""Auditoria de 06/11 (BANCO E TESTES): RETO do RJ em Itu em sub-lotes por origem na carga, lido de planilha
sintética (as reais não vão para o repositório); leitor de medidas; modelo da diferença explicada da T15."""
import pytest

pytest.importorskip("openpyxl")
pytest.importorskip("fastapi")

from tests.test_carga import _planilhas, _rodar, base  # noqa: F401,E402  (fixture `base` reaproveitada)


def _com_reto_d2_dc53(pasta):
    import openpyxl
    from openpyxl.comments import Comment

    from app.carga import planilhas as P
    wb = openpyxl.load_workbook(pasta / P.ARQ_GERAL)
    ws = wb["Estoque Geral"]
    ws.append([90101, "IMP-D2 RETO", None, 0, "KG", 0, None, 1100, None, None, None])
    ws.append([90102, "IMP-DC53 RETO", None, 0, "KG", 0, None, 1022, None, None, None])
    ws.append([90103, "IMP-D2 RETO SEM COMENTARIO", None, 0, "KG", 0, None, 77, None, None, None])
    ws.cell(ws.max_row - 2, 8).comment = Comment(
        "Autor:\n381kg de sobra (MEDIDA ORIGINAL IMP-D2 25X610MM)\n"
        "Resp:\n54kg de sobra (MEDIDA ORIGINAL IMP-D2 45X510MM)", "x")
    ws.cell(ws.max_row - 1, 8).comment = Comment("Autor:\n400kg de sobra (MEDIDA ORIGINAL IMP-DC53 30X500MM)", "x")
    wb.save(pasta / P.ARQ_GERAL)


def test_reto_rj_em_itu_d2_e_dc53_somam_o_saldo_da_celula(base, tmp_path):  # noqa: F811
    from sqlalchemy import func, select

    from app.core.db import SessionLocal
    from app.models import ItemMP, Liga, Lote, Movimento
    from app.services import estoque
    with SessionLocal() as db:
        db.add(Liga(codigo="DC53", nome="DC53", densidade=7.8, apelidos=[]))
        db.commit()
    _planilhas(tmp_path)
    _com_reto_d2_dc53(tmp_path)
    pl, conf = _rodar(tmp_path)
    # spec v3.7 (2026-11-11): o lote RJ em Itu não tem código do Mega; a linha do Estoque Geral identifica a célula
    from app.carga import planilhas as P
    linha_cod = {g.linha: g.codigo for g in P.ler_geral(tmp_path)}
    por_cod = {}
    for lp in pl.lotes:
        if lp.estoque == "RJ_EM_ITU" and lp.tipo == "RETO":
            assert pl.itens[lp.item].codigo_mega is None
            por_cod.setdefault(linha_cod[lp.origem["linha"]], []).append(round(lp.saldo, 3))
    assert sorted(por_cod[90101]) == [54.0, 381.0, 665.0] and round(sum(por_cod[90101]), 3) == 1100.0
    assert sorted(por_cod[90102]) == [400.0, 622.0] and round(sum(por_cod[90102]), 3) == 1022.0
    assert por_cod[90103] == [77.0]                         # sem comentário: um lote só, sem origem
    with SessionLocal() as db:
        for cod, total in ((90101, 1100.0), (90102, 1022.0), (90103, 77.0)):
            lotes = [lo for lo in db.scalars(select(Lote).join(ItemMP, Lote.item_mp_id == ItemMP.id)
                                             .where(ItemMP.codigo_mega.is_(None), Lote.local_fisico == "ITU",
                                                    Lote.planta_fiscal == "RJ"))
                     if linha_cod.get((lo.origem_ref or {}).get("linha")) == cod]
            assert all(lo.tipo == "RETO" for lo in lotes)                    # marcado RETO, não ORIGINAL
            assert round(sum(float(lo.saldo_kg) for lo in lotes), 3) == total
            for lo in lotes:                                                # saldo = soma dos movimentos
                soma = db.scalar(select(func.coalesce(func.sum(Movimento.kg), 0))
                                 .where(Movimento.lote_id == lo.id))
                assert round(float(soma), 3) == round(float(lo.saldo_kg), 3)
        origens = sorted(lo.origem_ref["bitola_origem"] for lo in db.scalars(select(Lote).where(Lote.tipo == "RETO"))
                         if (lo.origem_ref or {}).get("bitola_origem") and "D2" in lo.origem_ref["bitola_origem"])
        assert origens == ["IMP-D2 25X610MM", "IMP-D2 45X510MM"]
        # a aba RETO por origem soma por liga: o RETO sem lote-pai aparece com a medida de origem
        r = estoque.reto_por_origem(db, {})
        d2 = next(lg for lg in r["ligas"] if lg["liga"] == "D2")
        # R044 (0008): a medida de origem vem normalizada no formato da bitola do cadastro
        assert {b["bitola_origem"] for b in d2["bitolas"]} >= {"25X610", "45X510"}
