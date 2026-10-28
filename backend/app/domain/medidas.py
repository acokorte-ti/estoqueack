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
    "A8 MOD": "A8MOD", "A8MOD": "A8MOD", "CR8MOD": "CR8",
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
    m = _RE_RET.search(t_sem_liga)
    if m:
        a, b = _num(m.group(1)), _num(m.group(2))
        c = _num(m.group(3)) if m.group(3) else None
        return Medida(liga, "RETANGULAR", espessura=min(a, b), largura=max(a, b), comprimento=c)
    m = _RE_RED.search(t_sem_liga)
    if m:
        return Medida(liga, "REDONDO", diametro=_num(m.group(1)))
    return Medida(liga, "DESCONHECIDO")
