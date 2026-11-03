"""Cálculo da solicitação de corte (T07 passo 3), sem acesso ao banco.

Regra do Matheus / especificação v3: o **peso previsto** vem das **dimensões brutas de corte** = bitola escolhida
+ sobremetal preenchido, e não da medida acabada:
  - espessura (ou Ø) = a da bitola;
  - largura = a da bitola quando a peça usa a largura inteira; senão, largura acabada + sobremetal de largura;
  - comprimento = comprimento acabado + sobremetal de comprimento.
Cada dimensão bruta pode ser editada pelo usuário. Ex.: OP 91050, peça 23×65×165,2 de bitola 28×610 → 28×70×170,2.
"""
from __future__ import annotations

from dataclasses import dataclass

from .formato import numero_br
from .peso import peso_redondo, peso_reto


@dataclass(frozen=True)
class Dimensoes:
    formato: str                    # RETANGULAR | REDONDO
    espessura: float | None = None
    largura: float | None = None
    diametro: float | None = None
    comprimento: float | None = None

    def completo(self) -> bool:
        if self.formato == "REDONDO":
            return bool(self.diametro and self.comprimento)
        return bool(self.espessura and self.largura and self.comprimento)

    def texto(self) -> str:
        n = lambda v: numero_br(v, 1).replace(",0", "")  # noqa: E731
        if self.formato == "REDONDO":
            return f"Ø{n(self.diametro or 0)}×{n(self.comprimento or 0)}"
        return f"{n(self.espessura or 0)}×{n(self.largura or 0)}×{n(self.comprimento or 0)}"


@dataclass(frozen=True)
class CalculoCorte:
    bruto: Dimensoes
    sobremetal_largura_mm: float
    usa_largura_inteira: bool
    peso_peca_kg: float | None      # medida acabada × densidade × qtd (só referência)
    peso_previsto_kg: float | None  # bruto × densidade × qtd
    sobremetal_pct: float | None


def _peso(d: Dimensoes, densidade: float, qtd: int) -> float | None:
    if not d.completo():
        return None
    if d.formato == "REDONDO":
        return peso_redondo(d.diametro, d.comprimento, densidade, qtd)
    return peso_reto(d.espessura, d.largura, d.comprimento, densidade, qtd)


def calcular(*, bitola: Dimensoes | None, acabada: Dimensoes, quantidade: int, densidade: float,
             sobremetal_comprimento_mm: float, sobremetal_largura_mm: float | None,
             sobremetal_largura_padrao_mm: float = 5.0, bruto_informado: Dimensoes | None = None) -> CalculoCorte:
    """`bitola` é None para lote RETO (sem bitola definida): aí o bruto precisa vir informado."""
    usa_inteira = False
    sl = sobremetal_largura_mm
    if acabada.formato == "REDONDO":
        bruto = Dimensoes("REDONDO", diametro=(bitola.diametro if bitola else acabada.diametro),
                          comprimento=(acabada.comprimento or 0) + sobremetal_comprimento_mm
                          if acabada.comprimento else None)
        sl = 0.0
    else:
        larg_bruta = None
        if bitola and bitola.largura and acabada.largura:
            padrao = sobremetal_largura_padrao_mm if sl is None else sl
            usa_inteira = acabada.largura + padrao >= bitola.largura - 1e-9
            if usa_inteira:
                larg_bruta, sl = bitola.largura, 0.0
            else:
                sl = padrao
                larg_bruta = acabada.largura + sl
        elif acabada.largura:
            sl = sobremetal_largura_padrao_mm if sl is None else sl
            larg_bruta = acabada.largura + sl
        bruto = Dimensoes("RETANGULAR",
                          espessura=(bitola.espessura if bitola and bitola.espessura else acabada.espessura),
                          largura=larg_bruta,
                          comprimento=(acabada.comprimento + sobremetal_comprimento_mm)
                          if acabada.comprimento else None)
    if bruto_informado is not None:
        bruto = Dimensoes(bruto.formato,
                          espessura=bruto_informado.espessura or bruto.espessura,
                          largura=bruto_informado.largura or bruto.largura,
                          diametro=bruto_informado.diametro or bruto.diametro,
                          comprimento=bruto_informado.comprimento or bruto.comprimento)
    peca = _peso(acabada, densidade, quantidade)
    previsto = _peso(bruto, densidade, quantidade)
    pct = round((previsto - peca) / peca * 100, 2) if previsto and peca else None
    return CalculoCorte(bruto, float(sl or 0), usa_inteira, peca, previsto, pct)


def instrucao_padrao(modo: str, quantidade: int, comprimento_corte: float | None, liga: str, bitola: str,
                     comprimento_barra: float | None = None) -> str:
    """Mesmo texto usado hoje na planilha de corte."""
    if modo == "TRAZER_INTEIRA":
        barra = f"X{comprimento_barra:g}" if comprimento_barra else ""
        return f"TRAZER {quantidade:02d} PEÇA{'S' if quantidade > 1 else ''} {liga} {bitola}{barra}"
    comp = numero_br(comprimento_corte or 0, 1).replace(",0", "")
    return f"{quantidade:02d} PEÇA{'S' if quantidade > 1 else ''} COM {comp}MM COMPRIMENTO"
