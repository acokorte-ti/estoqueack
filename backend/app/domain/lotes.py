"""Lotes, saldo por movimentos e rastreabilidade de origem (árvore pai → filhos).

Conceito: um lote ORIGINAL nasce de um contêiner + bitola. Sobras fora da bitola viram
lotes RETO filhos, que sempre apontam para o pai. Assim é possível responder:
"quantos kg de H13 RETO vieram da bitola 35×610 do contêiner CH11EA?".
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass


@dataclass(frozen=True)
class LoteInfo:
    id: int
    conteiner: str
    liga: str
    bitola: str
    tipo: str                  # ORIGINAL | SOBRA | RETO
    pai_id: int | None
    saldo_kg: float


def saldo(movimentos_kg: list[float]) -> float:
    """Saldo = soma algébrica dos movimentos (entradas +, saídas −)."""
    return round(sum(movimentos_kg), 3)


def raiz(lote_id: int, lotes: dict[int, LoteInfo]) -> LoteInfo:
    """Sobe a árvore até o lote ORIGINAL. Protege contra ciclos."""
    visitados: set[int] = set()
    atual = lotes[lote_id]
    while atual.pai_id is not None:
        if atual.id in visitados:
            raise ValueError(f"ciclo na árvore de lotes a partir de {lote_id}")
        visitados.add(atual.id)
        atual = lotes[atual.pai_id]
    return atual


def cadeia_origem(lote_id: int, lotes: dict[int, LoteInfo]) -> list[LoteInfo]:
    """Lista do lote até a raiz (inclusive)."""
    cadeia, visitados = [], set()
    atual: LoteInfo | None = lotes[lote_id]
    while atual is not None:
        if atual.id in visitados:
            raise ValueError("ciclo na árvore de lotes")
        visitados.add(atual.id)
        cadeia.append(atual)
        atual = lotes[atual.pai_id] if atual.pai_id is not None else None
    return cadeia


def reto_por_origem(lotes: dict[int, LoteInfo], liga: str | None = None) -> dict[tuple[str, str, str], float]:
    """Saldo de RETO agrupado por (liga, bitola original, contêiner original)."""
    total: dict[tuple[str, str, str], float] = defaultdict(float)
    for l in lotes.values():
        if l.tipo != "RETO" or l.saldo_kg <= 0:
            continue
        if liga and l.liga != liga:
            continue
        r = raiz(l.id, lotes)
        total[(l.liga, r.bitola, r.conteiner)] += l.saldo_kg
    return {k: round(v, 3) for k, v in total.items()}
