"""Cálculo de peso teórico e perda de corte.

Unidades: medidas em milímetros (mm), densidade em g/cm³, resultado em kg.
    mm³ × g/cm³ × 1e-6 = kg

O peso teórico serve apenas para PREVISÃO (ex.: NF de peça inteira vinda do RJ).
Todo material é pesado; o peso real sempre prevalece.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

DENSIDADE_PADRAO = 7.85

# Valores de referência (literatura técnica). Editáveis na Administração;
# confirmar com fornecedores. Chave = código normalizado da liga.
DENSIDADES_REFERENCIA: dict[str, float] = {
    "H13": 7.80,
    "1.2344": 7.80,
    "H11": 7.80,
    "D2": 7.70,
    "CR12MOV": 7.70,
    "D6": 7.70,
    "A8": 7.85,
    "A8MOD": 7.85,
    "CR8": 7.75,
    "DC53": 7.87,
    "O1": 7.85,
    "S5": 7.76,
    "4140": 7.85,
    "1.2746": 7.85,
    "1.2767": 7.85,
    "1.2360": 7.75,
}


def _positivo(nome: str, valor: float) -> float:
    if valor is None or valor <= 0:
        raise ValueError(f"{nome} deve ser maior que zero (recebido: {valor!r})")
    return float(valor)


def densidade_da_liga(liga: str | None, tabela: dict[str, float] | None = None,
                      padrao: float = DENSIDADE_PADRAO) -> float:
    """Densidade da liga (g/cm³). Usa a tabela informada, depois a de referência, depois o padrão."""
    if not liga:
        return padrao
    chave = liga.strip().upper()
    for t in (tabela or {}, DENSIDADES_REFERENCIA):
        if chave in t:
            return t[chave]
    return padrao


def peso_reto(espessura: float, largura: float, comprimento: float,
              densidade: float = DENSIDADE_PADRAO, quantidade: int = 1) -> float:
    """Peso de chapa/barra retangular (kg)."""
    e = _positivo("espessura", espessura)
    l = _positivo("largura", largura)
    c = _positivo("comprimento", comprimento)
    d = _positivo("densidade", densidade)
    return round(e * l * c * d * 1e-6 * quantidade, 3)


def peso_redondo(diametro: float, comprimento: float,
                 densidade: float = DENSIDADE_PADRAO, quantidade: int = 1) -> float:
    """Peso de barra redonda (kg)."""
    di = _positivo("diâmetro", diametro)
    c = _positivo("comprimento", comprimento)
    d = _positivo("densidade", densidade)
    return round(math.pi / 4 * di * di * c * d * 1e-6 * quantidade, 3)


def peso_anel(diametro_externo: float, diametro_interno: float, comprimento: float,
              densidade: float = DENSIDADE_PADRAO, quantidade: int = 1) -> float:
    """Peso de anel/tubo (kg)."""
    de = _positivo("diâmetro externo", diametro_externo)
    c = _positivo("comprimento", comprimento)
    d = _positivo("densidade", densidade)
    di = float(diametro_interno or 0)
    if di < 0 or di >= de:
        raise ValueError("diâmetro interno deve ser >= 0 e menor que o externo")
    return round(math.pi / 4 * (de * de - di * di) * c * d * 1e-6 * quantidade, 3)


@dataclass(frozen=True)
class Secao:
    """Seção transversal de uma bitola."""
    espessura: float | None = None
    largura: float | None = None
    diametro: float | None = None

    @property
    def area_mm2(self) -> float:
        if self.diametro:
            return math.pi / 4 * self.diametro ** 2
        if self.espessura and self.largura:
            return self.espessura * self.largura
        raise ValueError("seção sem medidas suficientes")


def perda_corte_esperada(secao: Secao, espessura_serra_mm: float = 3.0,
                         densidade: float = DENSIDADE_PADRAO, cortes: int = 1) -> float:
    """Perda de material (kg) causada pela espessura da serra.

    Ex.: corte transversal em 35×610 com serra de 3 mm ≈ 0,503 kg.
    """
    _positivo("espessura da serra", espessura_serra_mm)
    return round(secao.area_mm2 * espessura_serra_mm * densidade * 1e-6 * cortes, 3)
