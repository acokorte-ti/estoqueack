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
    # medida de origem anotada na carga (origem_ref["bitola_origem"]) para RETO sem lote pai
    bitola_origem: str | None = None


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


COMPLETA, SO_BITOLA, SEM_ORIGEM = "COMPLETA", "SO_BITOLA", "SEM_ORIGEM"


def origem_do_reto(lote_id: int, lotes: dict[int, LoteInfo]) -> tuple[str, str | None, str]:
    """(bitola de origem, contêiner de origem, classe) de um lote RETO/SOBRA.

    COMPLETA: a raiz da árvore tem bitola e contêiner. SO_BITOLA: só a bitola é conhecida (medida anotada na carga
    ou raiz sem contêiner). SEM_ORIGEM: nada se sabe (RETO sem pai e sem medida anotada)."""
    r = raiz(lote_id, lotes)
    if r.tipo == "RETO" or r.bitola == "RETO":
        return (r.bitola_origem, None, SO_BITOLA) if r.bitola_origem else ("", None, SEM_ORIGEM)
    if r.conteiner:
        return r.bitola, r.conteiner, COMPLETA
    return r.bitola, None, SO_BITOLA


def reto_por_origem(lotes: dict[int, LoteInfo], liga: str | None = None) -> dict[tuple[str, str, str], float]:
    """Saldo de RETO agrupado por (liga, bitola original, contêiner original)."""
    total: dict[tuple[str, str, str], float] = defaultdict(float)
    for l in lotes.values():
        if l.tipo != "RETO" or l.saldo_kg <= 0:
            continue
        if liga and l.liga != liga:
            continue
        r = raiz(l.id, lotes)
        if r.id == l.id and l.bitola_origem:     # RETO sem pai, mas com a medida de origem anotada
            total[(l.liga, l.bitola_origem, "sem lote de origem")] += l.saldo_kg
            continue
        total[(l.liga, r.bitola, r.conteiner)] += l.saldo_kg
    return {k: round(v, 3) for k, v in total.items()}
