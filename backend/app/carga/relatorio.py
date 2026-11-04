"""Relatório da carga (prévia ou resultado) em Excel, para o Fabiano revisar com o FUNCIONAL."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .plano import Plano

CORES = {"BLOQUEIA": "F8D7DA", "REVISAR": "FFF3CD", "INFO": "E2E3E5", "OK": "D4EDDA", "DIFERENTE": "F8D7DA"}


def _aba(wb, nome: str, cab: list[str], linhas: list[list[Any]], larguras: list[int] | None = None, cor_col=None):
    from openpyxl.styles import Font, PatternFill
    ws = wb.create_sheet(nome)
    ws.append(cab)
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="3A3F44")
    for l in linhas:
        ws.append(["; ".join(map(str, v)) if isinstance(v, list) else v for v in l])
        if cor_col is not None and l[cor_col] in CORES:
            ws.cell(ws.max_row, cor_col + 1).fill = PatternFill("solid", fgColor=CORES[l[cor_col]])
    for i, w in enumerate(larguras or [], start=1):
        ws.column_dimensions[ws.cell(1, i).column_letter].width = w
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    return ws


def gerar(pl: Plano, destino: Path, *, titulo: str, conferencia_banco: list[dict] | None = None,
          resumo_gravado: dict | None = None) -> Path:
    import openpyxl
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    from collections import Counter
    pend = Counter((p.tipo, p.gravidade) for p in pl.pendencias)
    linhas = [["Relatório", titulo], ["Saldo do Mega usado", pl.data_mega or "—"]]
    linhas += [[k, v] for k, v in pl.contagens.items()]
    if resumo_gravado:
        linhas += [["(gravado) " + k, str(v)] for k, v in resumo_gravado.items()]
    linhas += [["", ""], ["Pendências por tipo", ""]] + [[f"{t} ({g})", n] for (t, g), n in sorted(pend.items())]
    _aba(wb, "Resumo", ["Item", "Valor"], linhas, [60, 40])
    conf = [[c["conferencia"], c["planilha"], c["sistema"], c["diferenca"], c["tolerancia"], c["resultado"],
             c["observacao"]] for c in pl.conferencias + (conferencia_banco or [])]
    _aba(wb, "Conferência", ["Conferência", "Planilha", "Sistema", "Diferença", "Tolerância", "Resultado",
                             "Observação"], conf, [70, 14, 14, 14, 12, 12, 80], cor_col=5)
    _aba(wb, "Pendências", ["Tipo", "Gravidade", "Descrição", "Sugestão", "Arquivo", "Aba", "Linha", "Célula"],
         [[p.tipo, p.gravidade, p.descricao, p.sugestao, (p.origem or {}).get("arquivo"), (p.origem or {}).get("aba"),
           (p.origem or {}).get("linha"), (p.origem or {}).get("celula")] for p in pl.pendencias],
         [26, 11, 100, 50, 34, 18, 10, 8], cor_col=1)
    _aba(wb, "Paridade RJ x CM", ["Material RJ (ESTOQUE 2026)", "Código Mega", "Descrição no Estoque Geral",
                                  "kg ESTOQUE 2026", "kg RJ no Rio (Geral)", "Situação", "Outros candidatos",
                                  "Confirmado pelo Fabiano (S/N)", "Correção"],
         [[p["descricao_rj"], p["cm"], p.get("descricao_geral"), p["kg_rj_planilha"], p["kg_rj_geral"],
           p["situacao"], p.get("outros_candidatos") or None, None, None] for p in pl.paridades],
         [40, 12, 42, 14, 14, 16, 60, 14, 30])
    lot = []
    for n, l in enumerate(pl.lotes, start=1):
        it = pl.itens[l.item]
        lot.append([f"L-{n:06d}", l.estoque, l.conteiner, it.liga, it.descricao, it.codigo_mega, l.tipo,
                    l.peso_inicial, l.saldo, l.conferencia_kg, "Não" if not l.origem_identificada else "Sim",
                    len(l.movimentos), "; ".join(f"{t}: {d}" for t, d in l.destinacoes) or None,
                    (l.origem or {}).get("arquivo"), (l.origem or {}).get("linha")])
    _aba(wb, "Lotes", ["Lote (previsto)", "Estoque", "Contêiner", "Liga", "Item", "Código Mega", "Tipo",
                       "Peso inicial", "Saldo", "Conferência planilha", "Origem identificada", "Movimentos",
                       "Restrições", "Arquivo", "Linha"], lot, [12, 22, 10, 9, 40, 11, 9, 11, 11, 11, 10, 9, 40, 30, 8])
    _aba(wb, "Solicitações", ["OP", "Item", "Cliente", "Lote (contêiner)", "Modo", "Qtd", "Peso previsto",
                              "Situação", "Cortes", "Peso cortado", "COP", "Prazo", "Linha"],
         [[s.op, s.item_codigo, s.cliente, s.lote.conteiner, s.modo, s.quantidade, s.peso_previsto, s.situacao,
           len(s.liberacoes), round(sum(x.peso_kg for x in s.liberacoes), 3) or None,
           ", ".join(str(x.cop) for x in s.liberacoes if x.cop) or None, s.prazo, (s.origem or {}).get("linha")]
          for s in pl.solicitacoes], [10, 10, 18, 14, 15, 6, 12, 22, 7, 12, 10, 12, 8])
    _aba(wb, "Kardex 2 anos", ["Código Mega", "Descrição no Mega", "Liga", "Densidade", "kg no Mega"],
         [[k["codigo"], k["descricao"], k["liga"], k["densidade"], k["kg"]] for k in pl.kardex_entraram],
         [12, 50, 16, 10, 12])
    _aba(wb, "Ligas novas", ["Liga", "Densidade usada"], [[k, v] for k, v in sorted(pl.ligas_novas.items())],
         [20, 16])
    destino.parent.mkdir(parents=True, exist_ok=True)
    wb.save(destino)
    return destino
