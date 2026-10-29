"""Formatação de números no padrão brasileiro para mensagens ao usuário (pedido R011 do FRONTEND).

    kg_br(1234.56)  -> "1.234,6 kg"
    pct_br(8.123)   -> "8,1 %"
    pct_br(5)       -> "5 %"
"""
from __future__ import annotations


def numero_br(valor: float, casas: int = 1) -> str:
    texto = f"{valor:,.{casas}f}"                     # 1,234.6
    return texto.replace(",", "§").replace(".", ",").replace("§", ".")


def kg_br(valor: float, casas: int = 1) -> str:
    return f"{numero_br(valor, casas)} kg"


def pct_br(valor: float, casas: int | None = None) -> str:
    if casas is None:
        casas = 0 if float(valor).is_integer() else 1
    return f"{numero_br(valor, casas)} %"
