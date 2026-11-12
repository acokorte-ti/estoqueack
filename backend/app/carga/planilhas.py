"""Leitura das 4 planilhas da carga inicial (especificação §10), sem regra de negócio.

Cada leitor confere o cabeçalho esperado. Se a estrutura mudou (aba ou coluna faltando, cabeçalho em outro
lugar), levanta `EstruturaMudou`: a carga para em vez de se adaptar em silêncio (pedido da COORDENAÇÃO).
Toda linha lida guarda a origem {arquivo, aba, linha}.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

ARQ_ESTOQUE = "ESTOQUE 2026.xlsx"
ARQ_GERAL = "Materia Prima Geral 20out.xlsx"
ARQ_CORTE = "CONTROLE DE CORTE - RIO DE JANEIRO.xlsx"
ARQ_SA = "ATUAL_PLANILHA_CADASTRO PRODUTOS SEMI ACABADO .xlsx"
ARQUIVOS = (ARQ_ESTOQUE, ARQ_GERAL, ARQ_CORTE, ARQ_SA)
# O Estoque Geral muda de nome a cada versão ("Materia Prima Geral 20out", "Materia Prima Geral 05nov"…): a carga
# aceita qualquer "Materia Prima Geral*.xlsx" na pasta, desde que seja UM só (spec v3.5 §10.8, R045).
PADRAO_GERAL = "materia prima geral"


def arquivo_geral(pasta: Path) -> str:
    achados = sorted(p.name for p in pasta.glob("*.xlsx")
                     if p.name.lower().startswith(PADRAO_GERAL) and not p.name.startswith("~$"))
    if not achados:
        raise EstruturaMudou(f"Arquivo não encontrado: {ARQ_GERAL} (ou outro \"Materia Prima Geral*.xlsx\")")
    if len(achados) > 1:
        raise EstruturaMudou("Mais de um Estoque Geral na pasta (" + "; ".join(achados) + "): deixe só o que vale")
    return achados[0]


def arquivos(pasta: Path) -> tuple[str, ...]:
    """Nomes das 4 planilhas usadas (o do Estoque Geral é o que estiver na pasta)."""
    return (ARQ_ESTOQUE, arquivo_geral(pasta), ARQ_CORTE, ARQ_SA)


class EstruturaMudou(Exception):
    """A planilha não tem a estrutura conhecida em 2026-10-28/11-03."""


def _norm(s: Any) -> str:
    t = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", t).strip().upper()


def _num(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, int | float):
        return float(v)
    if isinstance(v, str):
        m = re.fullmatch(r"\s*(-?\d+(?:[.,]\d+)?)\s*", v)
        if m:
            return float(m.group(1).replace(",", "."))
    return None


def _int(v: Any) -> int | None:
    n = _num(v)
    return int(n) if n is not None and float(n).is_integer() else None


def _data(v: Any) -> date | None:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return None


def _texto(v: Any) -> str | None:
    if v is None:
        return None
    t = str(v).strip()
    return t or None


def _abrir(pasta: Path, nome: str):
    import openpyxl
    p = pasta / nome
    if not p.exists():
        raise EstruturaMudou(f"Arquivo não encontrado: {nome}")
    return openpyxl.load_workbook(p, data_only=True)


def _aba(wb, nome: str, arquivo: str):
    if nome not in wb.sheetnames:
        raise EstruturaMudou(f"{arquivo}: aba \"{nome}\" não existe (abas: {', '.join(wb.sheetnames)})")
    return wb[nome]


def _cabecalho(ws, esperados: dict[str, str], arquivo: str, linhas=range(1, 6)) -> tuple[int, dict[str, int]]:
    """Acha a linha do cabeçalho e devolve {chave: coluna}. `esperados` = {chave: texto do cabeçalho}."""
    alvo = {k: _norm(v) for k, v in esperados.items()}
    for r in linhas:
        col = {}
        textos = {_norm(c.value): c.column for c in ws[r] if c.value is not None}
        for k, t in alvo.items():
            if t in textos:
                col[k] = textos[t]
        if len(col) == len(alvo):
            return r, col
    faltam = sorted(alvo.values())
    raise EstruturaMudou(f"{arquivo} / {ws.title}: cabeçalho esperado não encontrado nas linhas 1–5 "
                         f"(colunas {', '.join(faltam)})")


def ref(arquivo: str, aba: str, linha: int, coluna: str | None = None) -> dict[str, Any]:
    d = {"arquivo": arquivo, "aba": aba, "linha": linha}
    if coluna:
        d["celula"] = f"{coluna}{linha}"
    return d


# ---------------- ESTOQUE 2026 ----------------

@dataclass
class Consumo:
    kg: float
    coluna: str
    comentario: str | None
    ops: list[int]
    ops_texto: list[str]          # números como estão escritos (para achar OP mal digitada)
    sem_op: bool
    dia_mes: tuple[int, int] | None
    origem: dict[str, Any]


@dataclass
class LinhaEstoque2026:
    linha: int
    conteiner: str
    material: str
    valor_unitario: float | None
    pecas: int | None
    peso_inicial: float
    total_estoque: float          # coluna AN (conferência)
    consumos: list[Consumo]
    comentario_pecas: str | None
    origem: dict[str, Any]


def _autor_fora(texto: str) -> str:
    """Comentários do Excel começam com 'Autor:\\n'. Tira esse prefixo."""
    return re.sub(r"^[^\n:]{1,40}:\s*\n", "", texto or "").strip()


def _ops_do_comentario(t: str) -> tuple[list[int], list[str], bool, tuple[int, int] | None]:
    up = t.upper()
    sem_op = "SEM OP" in up
    # números de 4 a 9 dígitos antes da data (a data é dd/mm, curta). 'OP 97683/95377' = duas OPs separadas por /
    # (só número longo dos dois lados da barra: '14/05/2026' continua sendo data)
    textos = [x for g in re.findall(r"(?<![\d/])(\d{4,9}(?:\s*/\s*\d{4,9})*)(?![\d/])", t)
              for x in re.split(r"\s*/\s*", g)]
    ops = [int(x) for x in textos]
    dm = None
    m = re.search(r"(?<!\d)(\d{1,2})/(\d{1,2})(?:/\d{2,4})?(?!\d)", t)
    if m:
        d, mes = int(m.group(1)), int(m.group(2))
        if 1 <= d <= 31 and 1 <= mes <= 12:
            dm = (d, mes)
    return ops, textos, sem_op, dm


def ler_estoque_2026(pasta: Path) -> tuple[list[LinhaEstoque2026], list[dict]]:
    """Aba 'ESTOQUE 2026' (lotes RJ no Rio) + aba 'HISTORICO' (entradas)."""
    from openpyxl.utils import get_column_letter
    wb = _abrir(pasta, ARQ_ESTOQUE)
    ws = _aba(wb, "ESTOQUE 2026", ARQ_ESTOQUE)
    r0, col = _cabecalho(ws, {"ct": "CONTÊINER", "mp": "MATÉRIA PRIMA", "valor": "VALOR UNITÁRIO",
                              "pecas": "QUANTIDADE CHAPA/BARRA", "inicial": "PESO INICIAL",
                              "ops": "ORDENS DE PRODUÇÃO"}, ARQ_ESTOQUE)
    # TOTAL EM ESTOQUE aparece duas vezes (F e AN): a conferência usa a última
    tot = [c.column for c in ws[r0] if _norm(c.value) == _norm("TOTAL EM ESTOQUE (KG)")]
    if len(tot) < 2:
        raise EstruturaMudou(f"{ARQ_ESTOQUE}: esperava duas colunas 'TOTAL EM ESTOQUE (KG)'")
    c_ini, c_fim = col["ops"], tot[-1] - 1
    linhas = []
    for r in range(r0 + 1, ws.max_row + 1):
        ct, mp = _texto(ws.cell(r, col["ct"]).value), _texto(ws.cell(r, col["mp"]).value)
        if ct is None and mp is None:
            continue
        consumos = []
        for c in range(c_ini, c_fim + 1):
            cel = ws.cell(r, c)
            kg = _num(cel.value)
            if not kg:
                continue
            txt = _autor_fora(cel.comment.text) if cel.comment else None
            ops, textos, sem_op, dm = _ops_do_comentario(txt or "")
            letra = get_column_letter(c)
            consumos.append(Consumo(kg, letra, txt, ops, textos, sem_op, dm, ref(ARQ_ESTOQUE, ws.title, r, letra)))
        cpec = ws.cell(r, col["pecas"]).comment
        linhas.append(LinhaEstoque2026(
            r, str(ct).strip().upper(), mp or "", _num(ws.cell(r, col["valor"]).value),
            _int(ws.cell(r, col["pecas"]).value), _num(ws.cell(r, col["inicial"]).value) or 0.0,
            _num(ws.cell(r, tot[-1]).value) or 0.0, consumos, _autor_fora(cpec.text) if cpec else None,
            ref(ARQ_ESTOQUE, ws.title, r)))
    hist = _ler_historico(wb)
    return linhas, hist


def _ler_historico(wb) -> list[dict]:
    ws = _aba(wb, "HISTORICO", ARQ_ESTOQUE)
    r0, col = _cabecalho(ws, {"data": "DATA DE ENTRADA", "ct": "CT", "desc": "DESCRIÇÃO",
                              "pecas": "QUANTIDADE CHAPA/BARRA", "entrada": "ENTRADA",
                              "sucata": "TOTAL EM SUCATA", "estoque": "TOTAL EM ESTOQUE",
                              "obs": "Observações", "hist": "HISTÓRICO"}, ARQ_ESTOQUE)
    out = []
    for r in range(r0 + 1, ws.max_row + 1):
        ct, desc = _texto(ws.cell(r, col["ct"]).value), _texto(ws.cell(r, col["desc"]).value)
        if not ct or not desc:
            continue
        out.append({"linha": r, "data": _data(ws.cell(r, col["data"]).value),
                    "conteiner": re.sub(r"\s+", "", ct).upper(), "descricao": desc,
                    "pecas": _int(ws.cell(r, col["pecas"]).value), "entrada": _num(ws.cell(r, col["entrada"]).value),
                    "sucata": _num(ws.cell(r, col["sucata"]).value),
                    "estoque": _num(ws.cell(r, col["estoque"]).value),
                    "obs": _texto(ws.cell(r, col["obs"]).value), "historico": _texto(ws.cell(r, col["hist"]).value),
                    "origem": ref(ARQ_ESTOQUE, ws.title, r)})
    return out


# ---------------- Materia Prima Geral (Estoque Geral) ----------------

@dataclass
class LinhaGeral:
    linha: int
    codigo: int | None
    descricao: str
    comprimento_fixado: str | None
    estoque_mega: float | None
    rj_no_rio: float
    rj_em_itu: float
    obs_rj: str | None
    obs_itu: str | None
    clientes_uso: str | None
    obs: str | None
    comentarios: list[str]
    origem: dict[str, Any]
    # Comentário da célula "ESTOQUE RJ (em Itu)": o Itu anota ali cada parcela de sobra com a medida de origem
    # ("381kg de sobra (MEDIDA ORIGINAL IMP-D2 25X610MM)"). Lista de (kg, medida de origem).
    parcelas_itu: list[tuple[float, str]] = field(default_factory=list)
    comentario_itu: str | None = None


_RE_PARCELA_SOBRA = re.compile(r"(\d+(?:[.,]\d+)?)\s*kg\s+de\s+sobra\s*\(\s*MEDIDA\s+ORIGINAL\s+(.+?)\s*\)", re.I)


def parcelas_de_sobra(texto: str | None) -> list[tuple[float, str]]:
    """Extrai (kg, medida de origem) do comentário do RETO em Itu. Ignora o que não tiver o formato."""
    return [(float(m.group(1).replace(",", ".")), m.group(2).strip()) for m in _RE_PARCELA_SOBRA.finditer(texto or "")]


def ler_geral(pasta: Path) -> list[LinhaGeral]:
    arq = arquivo_geral(pasta)
    wb = _abrir(pasta, arq)
    ws = _aba(wb, "Estoque Geral", arq)
    r0, _ = _cabecalho(ws, {"item": "ITEM", "desc": "DESCRIÇÃO", "compr": "COMPR. FIXADOS (MM)",
                            "mega": "ESTOQUE MEGA", "rio": "ESTOQUE RJ (no Rio)", "itu": "ESTOQUE RJ (em Itu)",
                            "uso": "CLIENTES / USO", "obs": "OBS:"}, arq)
    cab = {c.column: _norm(c.value) for c in ws[r0] if c.value is not None}
    pos = {v: k for k, v in cab.items() if list(cab.values()).count(v) == 1}
    obs_cols = [k for k, v in cab.items() if v == "OBSERVACOES"]
    if len(obs_cols) != 2:
        raise EstruturaMudou(f"{arq}: esperava duas colunas OBSERVAÇÕES (RJ no Rio e RJ em Itu)")
    c = lambda nome: pos[_norm(nome)]  # noqa: E731
    out = []
    for r in range(r0 + 1, ws.max_row + 1):
        desc = _texto(ws.cell(r, c("DESCRIÇÃO")).value)
        if not desc:
            continue
        coms = [_autor_fora(x.comment.text) for x in ws[r] if x.comment]
        cel_itu = ws.cell(r, c("ESTOQUE RJ (em Itu)"))
        com_itu = _autor_fora(cel_itu.comment.text) if cel_itu.comment else None
        out.append(LinhaGeral(
            r, _int(ws.cell(r, c("ITEM")).value), desc, _texto(ws.cell(r, c("COMPR. FIXADOS (MM)")).value),
            _num(ws.cell(r, c("ESTOQUE MEGA")).value), _num(ws.cell(r, c("ESTOQUE RJ (no Rio)")).value) or 0.0,
            _num(ws.cell(r, c("ESTOQUE RJ (em Itu)")).value) or 0.0, _texto(ws.cell(r, obs_cols[0]).value),
            _texto(ws.cell(r, obs_cols[1]).value), _texto(ws.cell(r, c("CLIENTES / USO")).value),
            _texto(ws.cell(r, c("OBS:")).value), coms, ref(arq, ws.title, r),
            parcelas_de_sobra(com_itu), com_itu))
    return out


# ---------------- CONTROLE DE CORTE ----------------

@dataclass
class LinhaCorte:
    linha: int
    data: date | None
    op: int | None
    op_texto: str | None
    item: int | None
    medida: str | None
    qtd: int | None
    mp: str | None
    conteiner: str | None
    peso: float | None
    peso_texto: str | None
    cliente: str | None
    instrucao: str | None
    instrucao_processo: str | None
    prazo: date | None
    pecas_cortadas: int | None
    data_liberacao: date | None
    observacao: str | None
    peso2: float | None
    liberacao_feita: bool
    recebido: bool
    status: str | None
    origem: dict[str, Any] = field(default_factory=dict)


def ler_corte(pasta: Path) -> list[LinhaCorte]:
    wb = _abrir(pasta, ARQ_CORTE)
    ws = _aba(wb, "CONTROLE - CORTE RJ", ARQ_CORTE)
    nomes = {"data": "DATA SOLICITADA", "op": "OP", "item": "Item", "medida": "MEDIDA ACABADA", "qtd": "QTD",
             "mp": "MP", "ct": "CT", "peso": "PESO", "cliente": "CLIENTE", "info": "INFORMAÇÕES DO CORTE",
             "prazo": "PRAZO", "cortadas": "QTDE PEÇAS CORTADAS", "lib": "DATA DE LIBERAÇÃO", "obs": "OBSERVAÇÃO",
             "peso2": "PESO2", "feita": "LIBERAÇÃO FEITA", "receb": "RECEBIDO ACK?", "status": "STATUS"}
    r0, col = _cabecalho(ws, nomes, ARQ_CORTE, range(1, 8))
    out = []
    for r in range(r0 + 1, ws.max_row + 1):
        v = {k: ws.cell(r, c).value for k, c in col.items()}
        if v["op"] is None and v["mp"] is None:
            continue
        info_cel = ws.cell(r, col["info"])
        proc = _autor_fora(info_cel.comment.text) if info_cel.comment else None
        out.append(LinhaCorte(
            r, _data(v["data"]), _int(v["op"]), _texto(v["op"]), _int(v["item"]), _texto(v["medida"]),
            _int(v["qtd"]), _texto(v["mp"]), _texto(v["ct"]).upper() if _texto(v["ct"]) else None, _num(v["peso"]),
            _texto(v["peso"]), _texto(v["cliente"]), _texto(v["info"]), proc, _data(v["prazo"]), _int(v["cortadas"]),
            _data(v["lib"]), _texto(v["obs"]), _num(v["peso2"]), v["feita"] is True, v["receb"] is True,
            _texto(v["status"]), ref(ARQ_CORTE, ws.title, r)))
    return out


# ---------------- PLANILHA DE SA ----------------

@dataclass
class LinhaSa:
    data: date | None
    op: int | None
    cliente: str | None
    item: int | None
    material: str | None
    dimensao: str | None
    origem_ct: str | None
    qtde: int | None
    peso: float | None
    valor_precificador: float | None
    sa_codigo: int | None
    sa_codigo_texto: str | None
    descricao: str | None
    ncm: str | None
    icms: str | None
    ipi: str | None
    pedido: str | None
    extras: dict[str, Any]
    origem: dict[str, Any]


ABAS_SA = tuple(str(a) for a in range(2016, 2026))
COLS_SA = {"data": "DATA", "op": "OP", "cliente": "CLIENTE", "item": "COD. ITEM", "material": "MATERIAL",
           "dimensao": "DIMENSÃO", "origem": "ORIGEM", "qtde": "QTDE", "peso": "PESO",
           "valor": "VALOR PRECIFICADOR     POR KG/PÇ", "sa": "COD.MEGA SEMI ACAB.", "desc": "DESCRIÇÃO",
           "ncm": "NCM", "icms": "ICMS", "ipi": "IPI", "pedido": "PEDIDO"}


def ler_sa(pasta: Path) -> list[LinhaSa]:
    wb = _abrir(pasta, ARQ_SA)
    faltam = [a for a in ABAS_SA if a not in wb.sheetnames]
    if faltam:
        raise EstruturaMudou(f"{ARQ_SA}: abas faltando: {', '.join(faltam)}")
    out = []
    for aba in ABAS_SA:
        ws = wb[aba]
        r0, col = _cabecalho(ws, COLS_SA, ARQ_SA)
        usadas = set(col.values())
        extras_cols = {c.column: _texto(c.value) for c in ws[r0] if c.value is not None and c.column not in usadas}
        for r in range(r0 + 1, ws.max_row + 1):
            v = {k: ws.cell(r, c).value for k, c in col.items()}
            if v["op"] is None and v["sa"] is None and v["item"] is None:
                continue
            ex = {nome: ws.cell(r, c).value for c, nome in extras_cols.items() if ws.cell(r, c).value is not None}
            ex = {k: (x.isoformat() if isinstance(x, date | datetime) else x) for k, x in ex.items()}
            sat = _texto(v["sa"])
            out.append(LinhaSa(
                _data(v["data"]), _int(v["op"]), _texto(v["cliente"]), _int(v["item"]), _texto(v["material"]),
                _texto(v["dimensao"]), _texto(v["origem"]).upper() if _texto(v["origem"]) else None, _int(v["qtde"]),
                _num(v["peso"]), _num(v["valor"]), _int(v["sa"]) if _int(v["sa"]) else
                (int(m.group(1)) if sat and (m := re.match(r"\s*(\d{3,7})", sat)) else None), sat,
                _texto(v["desc"]), _texto(_int(v["ncm"]) or v["ncm"]), _texto(v["icms"]), _texto(v["ipi"]),
                _texto(_int(v["pedido"]) or v["pedido"]), ex, ref(ARQ_SA, aba, r)))
    return out
