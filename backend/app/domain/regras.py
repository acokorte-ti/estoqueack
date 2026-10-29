"""Regras de validação antecipada das movimentações de matéria-prima.

Cada função recebe valores simples e devolve um `Resultado`. Nenhuma grava nada.
Tolerância de excesso: padrão 5 % sobre o peso previsto (que JÁ inclui o sobremetal).
Revisão do Eduardo em 28/10/2026 (antes: 20 %). Valor configurável em TOLERANCIA_EXCESSO_PCT.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .formato import kg_br, pct_br
from .validacao import Nivel, Resultado

EPS = 1e-9


def validar_quantidade_kg(kg: float, campo: str = "peso") -> Resultado:
    r = Resultado()
    if kg is None or kg <= 0:
        r.adicionar("PESO_INVALIDO", Nivel.ERRO, f"O {campo} deve ser maior que zero.", campo=campo, valor=kg)
    return r


def validar_saldo(saldo_kg: float, reservado_outros_kg: float, solicitado_kg: float) -> Resultado:
    """Saldo físico do lote menos reservas de outros destinos deve cobrir o solicitado."""
    r = validar_quantidade_kg(solicitado_kg)
    if r.erros:
        return r
    disponivel = round(saldo_kg - max(reservado_outros_kg, 0), 3)
    if solicitado_kg > saldo_kg + EPS:
        r.adicionar("SALDO_INSUFICIENTE", Nivel.ERRO,
                    f"Saldo do lote ({kg_br(saldo_kg)}) é menor que o solicitado ({kg_br(solicitado_kg)}).",
                    saldo_kg=saldo_kg, solicitado_kg=solicitado_kg)
    elif solicitado_kg > disponivel + EPS:
        r.adicionar("USA_SALDO_RESERVADO", Nivel.CIENCIA,
                    f"O solicitado ({kg_br(solicitado_kg)}) invade {kg_br(solicitado_kg - disponivel)} reservados "
                    f"para outro destino. Disponível livre: {kg_br(disponivel)}.",
                    disponivel_kg=disponivel, solicitado_kg=solicitado_kg)
    return r


def validar_peso_real(previsto_kg: float, real_kg: float,
                      tolerancia_excesso_pct: float = 5.0,
                      tolerancia_falta_pct: float = 20.0) -> Resultado:
    """Compara peso real (balança) com o previsto.

    O previsto já é calculado com sobremetal, então o excedente aceito é pequeno.
    > previsto + 5 %   → CIÊNCIA obrigatória: o operador justifica o uso a mais de MP.
    < previsto − 20 %  → ALERTA (provável erro de digitação/pesagem).
    """
    r = validar_quantidade_kg(real_kg, "peso real")
    if r.erros or not previsto_kg or previsto_kg <= 0:
        return r
    desvio_pct = (real_kg - previsto_kg) / previsto_kg * 100
    if desvio_pct > tolerancia_excesso_pct + EPS:
        excedente = round(real_kg - previsto_kg, 3)
        r.adicionar("EXCESSO_TOLERANCIA", Nivel.CIENCIA,
                    f"Peso real {kg_br(real_kg)} está {pct_br(desvio_pct, 1)} acima do previsto "
                    f"({kg_br(previsto_kg)}). "
                    f"Limite: {pct_br(tolerancia_excesso_pct)}. Justifique o uso de {kg_br(excedente)} a mais de "
                    "matéria-prima.",
                    excedente_kg=excedente, previsto_kg=previsto_kg, real_kg=real_kg,
                    desvio_pct=round(desvio_pct, 2))
    elif -desvio_pct > tolerancia_falta_pct + EPS:
        r.adicionar("ABAIXO_PREVISTO", Nivel.ALERTA,
                    f"Peso real {kg_br(real_kg)} está {pct_br(-desvio_pct, 1)} abaixo do previsto "
                    f"({kg_br(previsto_kg)}). "
                    "Verifique a pesagem.",
                    previsto_kg=previsto_kg, real_kg=real_kg, desvio_pct=round(desvio_pct, 2))
    return r


def validar_sobremetal(peso_bruto_kg: float, peso_peca_kg: float,
                       tolerancia_pct: float = 20.0) -> Resultado:
    """Na solicitação: material bruto (bitola × comprimento) versus peso da peça acabada.

    Acima de `tolerancia_pct` (padrão 20 %, TOLERANCIA_SOBREMETAL_PCT) → CIÊNCIA: o operador
    só solicita se justificar (ex.: "OP urgente, só havia bitola 50×610"). Decisão de 29/10/2026.
    Depois, na pesagem, vale a regra de 5 % sobre o previsto (`validar_peso_real`).
    """
    r = Resultado()
    if not peso_peca_kg or peso_peca_kg <= 0 or not peso_bruto_kg or peso_bruto_kg <= 0:
        return r
    excesso_pct = (peso_bruto_kg - peso_peca_kg) / peso_peca_kg * 100
    if excesso_pct > tolerancia_pct + EPS:
        r.adicionar("SOBREMETAL_ACIMA_TOLERANCIA", Nivel.CIENCIA,
                    f"O material bruto ({kg_br(peso_bruto_kg)}) gera sobremetal de {pct_br(excesso_pct, 1)} "
                    f"sobre a peça "
                    f"({kg_br(peso_peca_kg)}). Limite: {pct_br(tolerancia_pct)}. Verifique se há bitola mais "
                    "próxima da medida acabada ou justifique o uso desta.",
                    peso_bruto_kg=peso_bruto_kg, peso_peca_kg=peso_peca_kg, excesso_pct=round(excesso_pct, 2))
    return r


def validar_bitola(bitola_esp: float | None, bitola_larg: float | None, bitola_diam: float | None,
                   peca_esp: float | None, peca_larg: float | None, peca_diam: float | None) -> Resultado:
    """A bitola precisa comportar a medida acabada (comparação dimensão a dimensão, ordenada)."""
    r = Resultado()
    bit = sorted([v for v in (bitola_esp, bitola_larg) if v]) if not bitola_diam else [bitola_diam, bitola_diam]
    pec = sorted([v for v in (peca_esp, peca_larg) if v]) if not peca_diam else [peca_diam, peca_diam]
    if len(bit) < 2 or len(pec) < 2:
        return r
    if any(p > b + EPS for p, b in zip(pec, bit, strict=False)):
        r.adicionar("BITOLA_MENOR_QUE_PECA", Nivel.ERRO,
                    "A bitola do lote é menor que a medida acabada da peça.",
                    bitola=bit, peca=pec)
    return r


def validar_perda_corte(peso_antes_kg: float, consumo_kg: float, sobra_kg: float,
                        perda_esperada_kg: float, margem_pct: float = 20.0) -> Resultado:
    """Peso antes = consumo + sobra + perda. Alerta se a perda real foge muito da esperada."""
    r = Resultado()
    if consumo_kg < 0 or sobra_kg < 0:
        return r.adicionar("PESO_INVALIDO", Nivel.ERRO, "Consumo e sobra não podem ser negativos.")
    perda_real = round(peso_antes_kg - consumo_kg - sobra_kg, 3)
    if perda_real < -EPS:
        r.adicionar("SOMA_MAIOR_QUE_LOTE", Nivel.ERRO,
                    f"Consumo + sobra ({kg_br(consumo_kg + sobra_kg)}) é maior que o peso do lote "
                    f"({kg_br(peso_antes_kg)}).",
                    perda_real_kg=perda_real)
        return r
    limite = perda_esperada_kg + peso_antes_kg * margem_pct / 100
    if perda_real > limite + EPS:
        r.adicionar("PERDA_CORTE_ALTA", Nivel.CIENCIA,
                    f"Diferença de {kg_br(perda_real)} entre o peso do lote e consumo + sobra. "
                    f"Perda de corte esperada ≈ {kg_br(perda_esperada_kg, 2)}. Confirme a pesagem.",
                    perda_real_kg=perda_real, perda_esperada_kg=perda_esperada_kg)
    return r


@dataclass(frozen=True)
class Destinacao:
    tipo: str            # "RESERVA" ou "RESTRICAO"
    descricao: str       # ex.: "Reservado CPR", "Não usar para guilhotinas"
    validade: date | None = None


def validar_destinacoes(destinacoes: list[Destinacao], hoje: date | None = None) -> Resultado:
    """Toda destinação/restrição vigente exige ciência de quem está baixando (decisão 10)."""
    r = Resultado()
    hoje = hoje or date.today()
    for i, d in enumerate(destinacoes):
        if d.validade and d.validade < hoje:
            continue
        r.adicionar(f"DESTINACAO_{i}", Nivel.CIENCIA,
                    f"{'Reserva' if d.tipo == 'RESERVA' else 'Restrição'} no lote: {d.descricao}. "
                    "Confirme que está ciente e que o uso está correto.",
                    tipo=d.tipo, descricao=d.descricao)
    return r


def validar_op(op_existe: bool, op_aberta: bool, ja_tem_solicitacao: bool) -> Resultado:
    r = Resultado()
    if not op_existe:
        return r.adicionar("OP_INEXISTENTE", Nivel.ERRO, "OP não encontrada no Mega.")
    if not op_aberta:
        r.adicionar("OP_ENCERRADA", Nivel.ERRO, "OP está encerrada/cancelada no Mega.")
    if ja_tem_solicitacao:
        r.adicionar("OP_DUPLICADA", Nivel.CIENCIA,
                    "Já existe solicitação/baixa para esta OP. Confirme que é uma nova necessidade.")
    return r
