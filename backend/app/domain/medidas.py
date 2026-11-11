"""Interpretação de descrições de material (liga + bitola) vindas das planilhas e do Mega.

Exemplos reais tratados:
  'IMP-H13 50X610MM', 'H13 Ø66', 'CR8  13X510', 'IMP-Cr12MoV RED 54MM', 'REDØ101',
  'A8 MOD 21x204x1110 Múltiplo', 'D2 FLAT BAR 4,8X600 (MÚLTIPLO DE 2020MM)', 'IMP-H13 RETO'
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# Apelidos → código canônico da liga
_APELIDOS = {
    "CR12 MOV": "CR12MOV", "CR12-MOV": "CR12MOV", "CR12MOV": "CR12MOV",
    "DC53-C": "DC53", "DC53C": "DC53", "DC 53": "DC53", "DC53": "DC53",
    "DIN 1.2746": "1.2746", "1.2746": "1.2746", "12746": "1.2746",
    "DIN 1.2767": "1.2767", "1.2767": "1.2767", "12767": "1.2767",
    "DIN 1.2344": "1.2344", "1.2344": "1.2344", "12344": "1.2344",
    "DIN 1.2360": "1.2360", "1.2360": "1.2360", "12360": "1.2360",
    "AISI-D2": "D2", "AISI D2": "D2", "AISI-D6": "D6", "AISI-O1": "O1",
    # CR8MOD é liga distinta de CR8 (P24, confirmada pelo Eduardo em 2026-11-10), como o A8 MOD do A8
    "A8 MOD": "A8MOD", "A8MOD": "A8MOD", "CR8MOD": "CR8MOD", "CR8 MOD": "CR8MOD",
    "HGNI06": "HGNI06", "TENAX300IM": "TENAX300", "CPM-10V": "CPM10V", "CPM 10V": "CPM10V",
    "45CRNI4MO": "45CRNI4MO",
}
_IGNORAR_PRIMEIRA = {"AÇO", "ACO", "CHAPA", "BARRA", "AISI", "DIN"}
_LIGAS_SIMPLES = ["H13", "H11", "D2", "D6", "A8", "CR8", "O1", "S5", "4140"]


def _sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def _num(s: str) -> float:
    return float(s.replace(",", "."))


@dataclass(frozen=True)
class Medida:
    liga: str | None
    formato: str            # RETANGULAR | REDONDO | RETO | DESCONHECIDO
    espessura: float | None = None
    largura: float | None = None
    diametro: float | None = None
    comprimento: float | None = None

    @property
    def bitola(self) -> str:
        """Bitola normalizada: '50X610', 'Ø126', 'RETO'."""
        if self.formato == "REDONDO" and self.diametro:
            return f"Ø{self.diametro:g}"
        if self.formato == "RETANGULAR" and self.espessura and self.largura:
            return f"{self.espessura:g}X{self.largura:g}"
        return self.formato


def normalizar_liga(texto: str | None) -> str | None:
    if not texto:
        return None
    t = _sem_acento(texto).upper().replace("IMP-", " ").replace("IMP -", " ")
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"(?<![\d.])1,(\d{4})(?!\d)", r"1.\1", t)  # 1,2767 → 1.2767
    for apelido in sorted(_APELIDOS, key=len, reverse=True):
        if re.search(rf"(?<![\w.]){re.escape(apelido)}(?![\w])", t):
            return _APELIDOS[apelido]
    for liga in _LIGAS_SIMPLES:
        if re.search(rf"(?<![\w.]){re.escape(liga)}(?![\w])", t):
            return liga
    # Fallback: primeira palavra que não é medida (ex.: 'OH255', 'K-100', '1.2721', 'W360')
    for palavra in t.split(" "):
        p = palavra.strip("-_")
        if not p or p in _IGNORAR_PRIMEIRA or re.match(r"^(RED|Ø)", p):
            continue
        if re.match(r"^\d+(?:[.,]\d+)?X", p) or re.match(r"^\d+(?:[,]\d+)?$", p):
            break
        return p
    return None


_RE_RED = re.compile(r"(?:RED\.?\s*Ø?|Ø\s*)(\d+(?:[.,]\d+)?)")
_RE_RET = re.compile(r"(\d+(?:[.,]\d+)?)\s*X\s*(\d+(?:[.,]\d+)?)(?:\s*X\s*(\d+(?:[.,]\d+)?))?")


_RE_MARCA_REDONDO = re.compile(r"Ø|(?<![A-Z])RED(?![A-Z])|(?<![A-Z])ROUND(?![A-Z])")
_RE_DIAM_COMP = re.compile(r"(\d+(?:[.,]\d+)?)\s*X\s*(\d+(?:[.,]\d+)?)(?!\s*X)")


def interpretar(descricao: str) -> Medida:
    """Extrai liga e bitola de uma descrição livre."""
    liga = normalizar_liga(descricao)
    t = (descricao or "").upper()
    # Faixa de largura 'X(400-600)' → usa o maior valor (capacidade máxima da bitola)
    t = re.sub(r"\((\d+(?:[.,]\d+)?)\s*-\s*(\d+(?:[.,]\d+)?)\)", lambda m: m.group(2), t)
    if re.search(r"\bRETO\b", t):
        return Medida(liga, "RETO")
    # Remove a liga do texto para não confundir números (ex.: 1.2746 76x183)
    t_sem_liga = re.sub(r"\b(DIN\s*)?1[.,]?\d{4}\b", " ", t)
    if liga and not liga[0].isdigit():
        t_sem_liga = t_sem_liga.replace(liga, " ", 1)
    # Redondo com comprimento: 'Ø90X2425', 'RED 90X2425MM', 'STEEL ROUND BARS 91X2430'
    # = redondo de diâmetro N e comprimento M (não é chapa N×M).
    if _RE_MARCA_REDONDO.search(t_sem_liga):
        mr = _RE_DIAM_COMP.search(t_sem_liga)
        if mr:
            return Medida(liga, "REDONDO", diametro=_num(mr.group(1)), comprimento=_num(mr.group(2)))
    m = _RE_RET.search(t_sem_liga)
    if m:
        a, b = _num(m.group(1)), _num(m.group(2))
        c = _num(m.group(3)) if m.group(3) else None
        return Medida(liga, "RETANGULAR", espessura=min(a, b), largura=max(a, b), comprimento=c)
    m = _RE_RED.search(t_sem_liga)
    if m:
        return Medida(liga, "REDONDO", diametro=_num(m.group(1)))
    return Medida(liga, "DESCONHECIDO")


_RE_MULT = re.compile(r"\bMULT|M[ÚU]LTIPLO")
_RE_MULT_COMPR = re.compile(r"(?:M[ÚU]LTIPLO\s*(?:DE)?|MULT\.?)\s*(\d+(?:[.,]\d+)?)")


def chave_multiplo(descricao: str | None, comprimento_fixado: str | None = None) -> str | None:
    """Múltiplo do item (§10.7, T07 v3.5: lote de múltiplo só se junta ao MESMO múltiplo). None = material comum.

    Ex.: 'A8 MOD 21x204x1110 Múltiplo' → '1110'; 'D2 FLAT BAR 4,8X600 (MÚLTIPLO DE 2020MM)' → '2020';
    comprimento fixado 'MULT. 1820' → '1820'; múltiplo sem comprimento legível → 'MULT'."""
    textos = [(t or "").upper() for t in (descricao, comprimento_fixado)]
    if not any(_RE_MULT.search(t) for t in textos):
        return None
    for t in textos:
        m = _RE_MULT_COMPR.search(t)
        if m:
            return f"{_num(m.group(1)):g}"
    c = interpretar(descricao or "").comprimento
    return f"{c:g}" if c else "MULT"


def bitola_de_origem(texto: str | None, liga_do_lote: str | None = None) -> str:
    """Bitola de origem anotada (comentário do Estoque Geral) no mesmo formato da bitola do cadastro, para agrupar
    na aba "RETO por origem" (R044): 'IMP-D2 25X610MM' e 'D2 25x610' → '25X610'; 'IMP-D2 30,5x610MM' → '30,5X610';
    'Ø90' → 'Ø90'. Se a liga anotada for outra que a do lote, ela fica na frente ('D2 36X510'). Faixa ('45x510~610')
    ou texto que não se lê: maiúsculo e sem espaço."""
    t = (texto or "").strip()
    if not t:
        return ""
    m = interpretar(t)
    if "~" in t or m.formato not in ("RETANGULAR", "REDONDO") or m.bitola in ("RETANGULAR", "REDONDO"):
        return re.sub(r"\s+", "", t.upper())
    b = m.bitola.replace(".", ",")
    return f"{m.liga} {b}" if m.liga and liga_do_lote and m.liga != normalizar_liga(liga_do_lote) else b


# P28 (Eduardo, 2026-11-11): 1.2344 = H13 e 1.2379 = D2 contam como a MESMA liga na mesma linha Itu × RJ;
# ligas MOD (A8MOD, CR8MOD) são diferentes de A8 e CR8.
LIGA_MESMA_LINHA = {"1.2344": "H13", "1.2379": "D2"}


@dataclass(frozen=True)
class ChaveMaterial:
    """Identidade do material para pôr Itu e RJ na mesma linha (spec v3.7 §1.4 + P28 do Eduardo, 2026-11-11):
    liga (com 1.2344 = H13 e 1.2379 = D2), formato, seção, comprimento informado e múltiplo. A escrita não conta
    (espaço, 'mm', ',0', 'IMP-', x/X/×), a medida conta (45X610 ≠ 45X600; Ø90 ≠ Ø90X2425)."""
    liga: str | None
    formato: str
    espessura: float | None
    largura: float | None
    diametro: float | None
    comprimento: float | None
    multiplo: bool

    @property
    def secao(self) -> tuple:
        return (self.formato, self.espessura, self.largura, self.diametro)

    @property
    def texto(self) -> str:
        if self.formato == "REDONDO":
            b = f"Ø{self.diametro:g}"
        elif self.formato == "RETANGULAR":
            b = f"{self.espessura:g}X{self.largura:g}"
        else:
            b = self.formato
        b = b.replace(".", ",")
        if self.comprimento:
            b += f"X{self.comprimento:g}".replace(".", ",")
        return f"{self.liga or '?'} {b}" + (" MULT" if self.multiplo else "")


def chave_material(m: Medida, descricao: str | None = None, comprimento_fixado: str | None = None) -> ChaveMaterial:
    mult = chave_multiplo(descricao, comprimento_fixado)
    compr = m.comprimento
    if compr is None and mult and mult != "MULT":
        compr = float(mult)
    liga = LIGA_MESMA_LINHA.get(m.liga, m.liga) if m.liga else None
    if m.formato == "REDONDO":
        return ChaveMaterial(liga, "REDONDO", None, None, m.diametro, compr, bool(mult))
    if m.formato == "RETANGULAR":
        return ChaveMaterial(liga, "RETANGULAR", m.espessura, m.largura, None, compr, bool(mult))
    return ChaveMaterial(liga, m.formato, None, None, None, None, False)
