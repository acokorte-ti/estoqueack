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
    # R049 / P28: paridade RJ × Itu por liga + bitola (sem ligar código), para o Eduardo e o Fabiano conferirem
    _aba(wb, "Paridade RJ x Itu", ["Material RJ", "Estoque RJ", "kg RJ", "Liga × bitola (chave)", "Situação",
                                   "Motivo", "Código(s) Itu", "Descrição Itu", "kg Itu (Estoque Mega)",
                                   "kg RJ no Rio (Estoque Geral)", "Diferença ESTOQUE 2026 × Geral",
                                   "Escritas no RJ", "Arquivo", "Linha", "Confere (S/N)", "Correção"],
         [[p["descricao_rj"], p["estoque"], p["kg_rj"], p["chave"], p["situacao"], p["motivo"],
           "; ".join(str(x["codigo"]) for x in p["itu"]) or None,
           "; ".join(x["descricao"] for x in p["itu"]) or None,
           sum(x["kg"] or 0 for x in p["itu"]) if p["itu"] else None, p["kg_rj_geral"], p["diferenca_kg"],
           "; ".join(p.get("descricoes_rj") or []) or None, (p.get("origem") or {}).get("arquivo"),
           (p.get("origem") or {}).get("linha"), None, None] for p in pl.paridades],
         [36, 12, 12, 26, 14, 34, 16, 50, 14, 14, 14, 50, 30, 8, 10, 30])
    # P29: linha a linha dos materiais RJ que pegaram o comprimento do HISTORICO (ex.: CH39SH D2 Ø90)
    from .plano import chave_mat
    itu = {p["chave"]: p for p in pl.paridades if p["estoque"] == "RJ_NO_RIO"}
    lin = []
    for linha, ch_ in sorted(pl.compr_hist.items()):
        compr, hs = ch_["texto"], ch_["hist"]
        lp = next((x for x in pl.lotes if (x.origem or {}).get("linha") == linha
                   and (x.origem or {}).get("aba") == "ESTOQUE 2026"), None)
        it = pl.itens[lp.item] if lp else None
        par = itu.get(chave_mat(it.descricao).texto) if it else None
        base = [lp.conteiner if lp else None, it.descricao if it else None, compr, ch_["motivo"],
                lp.peso_inicial if lp else None, lp.conferencia_kg if lp else None]
        tot = round(sum(h["entrada"] or 0 for h in hs), 3)
        for n, h in enumerate(hs):
            lin.append(base + [h["descricao"], h["entrada"], h["linha"], tot if n == 0 else None,
                               (par or {}).get("situacao") if n == 0 else None,
                               "; ".join(f"{x['codigo']} {x['descricao']} ({x['kg'] or 0:g} kg Mega na planilha)"
                                         for x in (par or {}).get("itu", [])) if n == 0 else None, linha])
    _aba(wb, "Comprimento do HISTORICO", ["Contêiner", "Material RJ (item)", "Comprimento no HISTORICO",
                                          "Uso na paridade (P31)",
                                          "Peso inicial (ESTOQUE 2026)", "Total em estoque (ESTOQUE 2026)",
                                          "Entrada no HISTORICO", "kg da entrada", "Linha HISTORICO",
                                          "Soma do HISTORICO", "Situação", "Linha de Itu", "Linha ESTOQUE 2026"],
         lin, [10, 40, 18, 40, 14, 14, 40, 12, 10, 12, 14, 60, 10])
    _aba(wb, "Correções aplicadas", ["Onde (linha do Estoque Geral, da ESTOQUE 2026…)", "kg", "Na planilha",
                                     "Corrigido para", "Fonte", "Tipo"],
         [[c["linha"], c["kg"], c["antes"], c["depois"], c["fonte"], c.get("tipo")] for c in pl.correcoes_aplicadas],
         [40, 10, 40, 40, 60, 16])
    # v3.11 §10.9 (P33): o que a carga corrigiu em relação à planilha, para o Fabiano conferir caso a caso
    _aba(wb, "Contêiner do Corte (B05)", ["OP", "MP no Controle de Corte", "Contêiner no Corte", "Contêiner usado",
                                          "Fonte", "Contêineres com a OP", "Linha do Corte"],
         [[c["op"], c["mp"], c["conteiner_corte"], c["conteiner"], c["fonte"], ", ".join(c["opcoes"]), c["linha"]]
          for c in pl.conteiner_corrigido], [10, 24, 14, 14, 16, 30, 10])
    _aba(wb, "Corte dividido (B07)", ["OP", "MP no Controle de Corte", "Contêiner no Corte", "Peso no Corte",
                                      "Contêiner (ESTOQUE 2026)", "kg", "Material (ESTOQUE 2026)", "Linha do Corte"],
         [[d["op"], d["mp"], d["conteiner_corte"], d["peso_corte"], ct, kg, mat, d["linha"]]
          for d in pl.cortes_divididos for ct, kg, mat in d["partes"]], [10, 24, 14, 12, 16, 10, 36, 10])
    _aba(wb, "Peso inicial (B08)", ["Contêiner", "Material (ESTOQUE 2026)", "Entrada do packing list (peso inicial)",
                                    "PESO INICIAL 2026 (abertura)", "Saídas anteriores a 2026", "Data de entrada",
                                    "Linhas do HISTORICO", "Linha ESTOQUE 2026"],
         [[x["conteiner"], x["material"], x["packing"], x["abertura"], round(x["packing"] - x["abertura"], 3),
           x["data_entrada"], ", ".join(map(str, x["linhas_hist"])), x["linha"]] for x in pl.peso_inicial_packing],
         [12, 40, 18, 18, 16, 12, 30, 10])
    _aba(wb, "Em aberto (avisos)", ["Aba", "Linha", "Descrição na planilha", "Aviso", "Fonte"],
         [[a["aba"], a["linha"], a["descricao"], a["texto"], a["fonte"]] for a in pl.avisos], [16, 8, 30, 100, 40])
    lot = []
    for n, l in enumerate(pl.lotes, start=1):
        it = pl.itens[l.item]
        d0 = next((m.data for m in l.movimentos if m.tipo == "SALDO_INICIAL"), None)
        lot.append([f"L-{n:06d}", l.estoque, l.conteiner, it.liga, it.descricao, it.codigo_mega, l.tipo,
                    l.peso_inicial, l.abertura_kg, d0, l.saldo, l.conferencia_kg,
                    "Não" if not l.origem_identificada else "Sim",
                    len(l.movimentos), "; ".join(f"{t}: {d}" for t, d in l.destinacoes) or None,
                    (l.origem or {}).get("arquivo"), (l.origem or {}).get("linha"), " | ".join(l.notas) or None])
    _aba(wb, "Lotes", ["Lote (previsto)", "Estoque", "Contêiner", "Liga", "Item", "Código Mega", "Tipo",
                       "Peso inicial", "Abertura 2026 (PESO INICIAL)", "Data de entrada", "Saldo",
                       "Conferência planilha", "Origem identificada", "Movimentos", "Restrições", "Arquivo", "Linha",
                       "Notas do lote"], lot,
         [12, 22, 10, 9, 40, 11, 9, 11, 12, 12, 11, 11, 10, 9, 40, 30, 8, 80])
    _aba(wb, "Restrições no item (B09)", ["Item", "Liga", "Código Mega", "Restrição", "Lotes do item"],
         [[it.descricao, it.liga, it.codigo_mega, it.restricao_uso, sum(1 for l in pl.lotes if l.item == ch)]
          for ch, it in pl.itens.items() if it.restricao_uso], [40, 10, 12, 50, 12])
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
