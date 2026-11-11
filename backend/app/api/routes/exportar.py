"""Exportações para Excel (T04 consulta de estoque, T08 solicitações, T14 SA no layout da planilha de SA).

Usam os mesmos filtros e a mesma visibilidade das telas (Operação RJ só RJ no Rio).
"""
from __future__ import annotations

import io
import unicodedata
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api import deps
from app.api.routes.lotes import _visivel, filtros, filtros_reto, reto_visivel
from app.core.db import get_db
from app.models import Usuario
from app.services import estoque, sas, solicitacoes

router = APIRouter(prefix="/exportar", tags=["exportações"])
VER_SA = deps.exigir_perfil("ESTOQUE", "OPERACAO_RJ", "ANALISE")
ESTOQUES = {"ESTOQUE_MEGA": "Estoque Mega", "RJ_NO_RIO": "RJ no Rio", "RJ_EM_ITU": "RJ em Itu"}
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _planilha(nome: str, cab: list[str], linhas: list[list[Any]], larguras: list[int]) -> StreamingResponse:
    import openpyxl
    from openpyxl.styles import Font, PatternFill
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = nome[:31]
    ws.append(cab)
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="3A3F44")
    for l in linhas:
        ws.append(l)
    for i, w in enumerate(larguras, start=1):
        ws.column_dimensions[ws.cell(1, i).column_letter].width = w
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    base = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode().lower().replace(" ", "_")
    arquivo = f"{base}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return StreamingResponse(buf, media_type=XLSX, headers={"Content-Disposition": f'attachment; filename="{arquivo}"'})


def _d(v: str | None) -> date | None:
    return date.fromisoformat(v[:10]) if v else None


@router.get("/lotes.xlsx")
def lotes(f: dict = Depends(filtros), db: Session = Depends(get_db),
          u: Usuario = Depends(deps.usuario_liberado)) -> StreamingResponse:
    itens = estoque.lote_resumo(db, estoque.consulta_lotes(db, _visivel(f, u)))
    linhas = [[i["codigo"], ESTOQUES.get(i["estoque"], i["estoque"]), i["conteiner"], i["liga"], i["bitola"],
               i["descricao"], i["codigo_mega"], i["tipo"], i["saldo_kg"], i["reservado_kg"], i["disponivel_kg"],
               (f"{i['origem']['conteiner'] or '-'} {i['origem']['bitola']}" if i["origem"] else None),
               "Sim" if i["indicadores"]["destinacao"] else None,
               "Não" if i["indicadores"]["origem_nao_identificada"] else None] for i in itens]
    return _planilha("Estoque por lote", ["Lote", "Estoque", "Contêiner", "Liga", "Bitola", "Descrição", "Código Mega",
                                          "Tipo", "Saldo kg", "Reservado kg", "Disponível kg", "Origem",
                                          "Reserva/restrição", "Origem identificada"],
                     linhas, [11, 13, 10, 9, 11, 34, 11, 10, 11, 11, 12, 22, 10, 10])


@router.get("/lotes-agrupado.xlsx")
def lotes_agrupado(f: dict = Depends(filtros), db: Session = Depends(get_db),
                   u: Usuario = Depends(deps.usuario_liberado)) -> StreamingResponse:
    g = estoque.agrupado(estoque.lote_resumo(db, estoque.consulta_lotes(db, _visivel(f, u))))
    linhas = [[a["liga"], a["formato"], a["bitola"], a["lotes"], a["por_estoque"]["ESTOQUE_MEGA"],
               a["por_estoque"]["RJ_NO_RIO"], a["por_estoque"]["RJ_EM_ITU"], a["saldo_kg"], a["reservado_kg"],
               a["disponivel_kg"]] for a in g]
    return _planilha("Estoque por item", ["Liga", "Formato", "Bitola", "Lotes", "Estoque Mega kg", "RJ no Rio kg",
                                          "RJ em Itu kg", "Total kg", "Reservado kg", "Disponível kg"],
                     linhas, [9, 12, 11, 7, 14, 13, 13, 12, 12, 13])


@router.get("/solicitacoes.xlsx")
def solicitacoes_xlsx(situacao: list[str] = Query(default=[]), op: int | None = None, cliente: str | None = None,
                      liga: str | None = None, conteiner: str | None = None, de: date | None = None,
                      ate: date | None = None, somente_atrasadas: bool = False, db: Session = Depends(get_db),
                      u: Usuario = Depends(deps.usuario_liberado)) -> StreamingResponse:
    sols = solicitacoes.listar(db, u, {"situacao": situacao, "op": op, "cliente": cliente, "liga": liga,
                                       "conteiner": conteiner, "de": de, "ate": ate,
                                       "somente_atrasadas": somente_atrasadas})
    linhas = []
    for s in sols:
        r = solicitacoes.resumo(db, s)
        linhas.append([r["numero"], _d(r["data"]), r["op"], r["item_codigo"], r["item_descricao"], r["cliente"],
                       f"{r['lote']['liga']} {r['lote']['bitola']}", r["lote"]["conteiner"], r["lote"]["codigo"],
                       r["modo"], r["quantidade"], r["pecas_cortadas"], r["peso_previsto_kg"], r["peso_real_kg"],
                       _d(r["prazo"]), r["situacao"], r["atraso"], r["dias_em_aberto"], ", ".join(map(str, r["cops"])),
                       r["instrucao"], r["instrucao_processo"],
                       r["consumo_misto"]["texto"] if r["consumo_misto"] else None])
    return _planilha("Solicitações de corte", ["Nº", "Data", "OP", "Item", "Descrição do item", "Cliente", "MP/bitola",
                                               "Contêiner", "Lote", "Modo", "Qtd", "Peças cortadas", "Peso previsto",
                                               "Peso real", "Prazo", "Situação", "Atraso", "Dias em aberto", "COP",
                                               "Informações do corte", "Instrução de processo", "Consumo misto"],
                     linhas, [10, 11, 9, 9, 30, 18, 14, 10, 10, 14, 6, 8, 11, 10, 11, 18, 10, 8, 8, 30, 24, 30])


@router.get("/sas.xlsx")
def sas_xlsx(ids: list[int] = Query(default=[]), situacao: list[str] = Query(default=[]),
             origem: list[str] = Query(default=[]), op: int | None = None, cop: int | None = None,
             nao_exportados: bool = False, db: Session = Depends(get_db),
             u: Usuario = Depends(VER_SA)) -> StreamingResponse:
    """Layout da planilha de SA ("Exportar pedidos selecionados"), para facilitar o lançamento no Mega."""
    if ids:
        linhas_sa = [sas.obter(db, i, usuario=u) for i in ids]
    else:
        if not situacao and not op and not cop:
            situacao = ["PENDENTE", "PREPARADO", "AGUARDANDO_MEGA"]
        linhas_sa = sas.listar(db, {"situacao": situacao, "origem": origem or ["COP", "CORTE_ITU"], "op": op,
                                    "cop": cop, "nao_exportados": nao_exportados})
    linhas = []
    for s in linhas_sa:
        d = sas.para_dict(db, s)
        linhas.append([_d(d["data"]), d["op"], d["cliente"], d["item_codigo"], d["material"], d["dimensao"],
                       d["conteiner"], d["quantidade"], d["peso_kg"], d["valor_precificador"], d["sa_codigo"],
                       d["sa_descricao"], d["ncm"], d["icms"], d["ipi"], d["pedido"],
                       d["nf"]["numero"] if d["nf"] else None, d["cop"]["numero"] if d["cop"] else None,
                       d["situacao"], "SA novo – cadastrar no Mega" if d["sa_novo"] else None])
    return _planilha("SA", ["DATA", "OP", "CLIENTE", "COD. ITEM", "MATERIAL", "DIMENSÃO", "ORIGEM", "QTDE", "PESO",
                            "VALOR PRECIFICADOR POR KG/PÇ", "COD.MEGA SEMI ACAB.", "DESCRIÇÃO", "NCM", "ICMS", "IPI",
                            "PEDIDO", "NF FIOCERTO/MEDIO VALE", "COP", "SITUAÇÃO NO SISTEMA", "OBS"],
                     linhas, [11, 9, 18, 10, 10, 11, 10, 7, 9, 14, 12, 44, 11, 7, 7, 10, 12, 7, 16, 24])


CLASSES_TXT = {"COMPLETA": "Origem completa", "SO_BITOLA": "Só a bitola", "SEM_ORIGEM": "Sem origem"}


@router.get("/reto-por-origem.xlsx")
def reto_por_origem_xlsx(f: dict = Depends(filtros_reto), db: Session = Depends(get_db),
                         u: Usuario = Depends(deps.usuario_liberado)) -> StreamingResponse:
    """Duas abas: "Resumo" (linhas agrupadas e totais) e "Lotes" (um lote por linha). Cabeçalho com filtros e data."""
    import openpyxl
    from openpyxl.styles import Font, PatternFill
    f = reto_visivel(f, u)
    r = estoque.reto_por_origem(db, f)
    usados = "; ".join(f"{k}={v}" for k, v in f.items() if v not in (None, [], False)) or "(sem filtros)"
    cab = [f"RETO por origem — gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}", f"Filtros: {usados}"]
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Resumo"
    for t in cab:
        ws.append([t])
    ws.append([])
    cols = ["Liga", "Bitola de origem", "Contêiner de origem", "Classe", "Estoque", "Nº de lotes", "Saldo kg",
            "Reservado kg", "Disponível kg"]
    ws.append(cols)
    topo = ws.max_row
    for lg in r["ligas"]:
        for b in lg["bitolas"]:
            for c in b["conteineres"]:
                ws.append([lg["liga"], b["bitola_origem"], c["conteiner_texto"], CLASSES_TXT[c["classe"]],
                           ESTOQUES.get(c["estoque"], c["estoque"]), c["lotes"], c["saldo_kg"], c["reservado_kg"],
                           c["disponivel_kg"]])
        s = lg["sem_origem"]
        if s:
            ws.append([lg["liga"], "Sem origem identificada", None, CLASSES_TXT["SEM_ORIGEM"], None, s["lotes"],
                       s["saldo_kg"], s["reservado_kg"], s["disponivel_kg"]])
        t = lg["totais"]
        ws.append([f"Total {lg['liga']}", f"Com origem {t['com_origem_kg']:.1f} kg · Só bitola {t['so_bitola_kg']:.1f}"
                   f" kg · Sem origem {t['sem_origem_kg']:.1f} kg", None, None, None, t["lotes"], t["total_kg"],
                   t["reservado_kg"], t["disponivel_kg"]])
        ws.cell(ws.max_row, 1).font = Font(bold=True)
    t = r["totais"]
    ws.append(["TOTAL GERAL", f"Com origem {t['com_origem_kg']:.1f} kg · Só bitola {t['so_bitola_kg']:.1f} kg · "
               f"Sem origem {t['sem_origem_kg']:.1f} kg · Total RETO {t['total_kg']:.1f} kg", None, None, None,
               t["lotes"], t["total_kg"], t["reservado_kg"], t["disponivel_kg"]])
    ws.cell(ws.max_row, 1).font = Font(bold=True)
    wl = wb.create_sheet("Lotes")
    for tx in cab:
        wl.append([tx])
    wl.append([])
    wl.append(["Lote", "Estoque", "Liga", "Bitola de origem", "Contêiner de origem", "Classe de origem", "Saldo kg",
               "Reservado kg", "Data de criação", "Nota"])
    for x in r["lotes"]:
        wl.append([x["lote"], ESTOQUES.get(x["estoque"], x["estoque"]), x["liga"], x["bitola_origem"],
                   x["conteiner_origem"] or ("não informado" if x["classe"] == "SO_BITOLA" else None),
                   CLASSES_TXT[x["classe"]], x["saldo_kg"], x["reservado_kg"], _d(x["criado_em"]), x["nota"]])
    for folha, linha_cab in ((ws, topo), (wl, 4)):
        for c in folha[linha_cab]:
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = PatternFill("solid", fgColor="3A3F44")
        for i, w in enumerate([12, 26, 20, 16, 14, 11, 12, 12, 13, 40], start=1):
            folha.column_dimensions[folha.cell(1, i).column_letter].width = w
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    arquivo = f"reto_por_origem_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return StreamingResponse(buf, media_type=XLSX, headers={"Content-Disposition": f'attachment; filename="{arquivo}"'})
