"""Resultado padronizado das validações antecipadas.

Níveis:
  ERRO      → bloqueia a operação.
  CIENCIA   → só grava se o usuário confirmar "estou ciente" + justificativa.
  ALERTA    → informativo; aparece na tela, não bloqueia.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Nivel(str, Enum):
    ERRO = "ERRO"
    CIENCIA = "CIENCIA"
    ALERTA = "ALERTA"


@dataclass(frozen=True)
class Ocorrencia:
    codigo: str
    nivel: Nivel
    mensagem: str
    dados: dict[str, Any] = field(default_factory=dict)


@dataclass
class Resultado:
    ocorrencias: list[Ocorrencia] = field(default_factory=list)

    def adicionar(self, codigo: str, nivel: Nivel, mensagem: str, **dados: Any) -> "Resultado":
        self.ocorrencias.append(Ocorrencia(codigo, nivel, mensagem, dados))
        return self

    def juntar(self, outro: "Resultado") -> "Resultado":
        self.ocorrencias.extend(outro.ocorrencias)
        return self

    @property
    def erros(self) -> list[Ocorrencia]:
        return [o for o in self.ocorrencias if o.nivel is Nivel.ERRO]

    @property
    def ciencias(self) -> list[Ocorrencia]:
        return [o for o in self.ocorrencias if o.nivel is Nivel.CIENCIA]

    @property
    def alertas(self) -> list[Ocorrencia]:
        return [o for o in self.ocorrencias if o.nivel is Nivel.ALERTA]

    def pendencias(self, confirmacoes: dict[str, str] | None = None) -> list[Ocorrencia]:
        """Ocorrências que ainda impedem a gravação.

        `confirmacoes` = {codigo_da_ocorrencia: justificativa}. Justificativa vazia não vale.
        """
        conf = {k: (v or "").strip() for k, v in (confirmacoes or {}).items()}
        pend = list(self.erros)
        pend += [c for c in self.ciencias if len(conf.get(c.codigo, "")) < 5]
        return pend

    def pode_gravar(self, confirmacoes: dict[str, str] | None = None) -> bool:
        return not self.pendencias(confirmacoes)

    def como_dict(self) -> dict[str, Any]:
        return {
            "ok": not self.erros and not self.ciencias,
            "ocorrencias": [
                {"codigo": o.codigo, "nivel": o.nivel.value, "mensagem": o.mensagem, "dados": o.dados}
                for o in self.ocorrencias
            ],
        }
