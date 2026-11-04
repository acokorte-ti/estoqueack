"""Peças comuns dos serviços da Fase 1: erros de negócio, parâmetros (T23), notificações (§6), visibilidade por
perfil (P10) e o padrão prévia/gravação (contrato §1.5)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Config
from app.domain.validacao import Resultado
from app.models import Lote, Notificacao, Parametro, Usuario


class ErroNegocio(Exception):
    """Ação impossível no estado atual (ex.: cancelar solicitação já cortada). Vira HTTP 400."""


class NaoEncontrado(Exception):
    """Vira HTTP 404."""


@dataclass
class Previa:
    """Resultado do /validar: ocorrências + frase de resultado + efeitos (contrato §1.5)."""
    resultado: Resultado = field(default_factory=Resultado)
    frase: str | None = None
    efeitos: list[dict[str, Any]] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    def como_dict(self) -> dict[str, Any]:
        d = self.resultado.como_dict()
        d["resultado"] = {"frase": self.frase, "efeitos": self.efeitos, **self.extra}
        return d


class PendenciasValidacao(Exception):
    """Gravação recusada porque ainda há ERRO ou CIENCIA sem justificativa. Vira HTTP 409 com a prévia."""

    def __init__(self, previa: Previa):
        super().__init__("pendências de validação")
        self.previa = previa


def exigir_sem_pendencias(previa: Previa, confirmacoes: dict[str, str] | None) -> dict[str, str]:
    """Levanta 409 se houver pendência; devolve só as justificativas que correspondem a ocorrências CIENCIA."""
    if not previa.resultado.pode_gravar(confirmacoes):
        raise PendenciasValidacao(previa)
    codigos = {o.codigo for o in previa.resultado.ciencias}
    return {k: v.strip() for k, v in (confirmacoes or {}).items() if k in codigos}


def agora() -> datetime:
    return datetime.now(timezone.utc)


def hoje() -> date:
    return date.today()


# ---------------- Parâmetros (T23) ----------------

PADROES: dict[str, float] = {
    "TOLERANCIA_EXCESSO_PCT": 5, "TOLERANCIA_SOBREMETAL_PCT": 20, "TOLERANCIA_FALTA_PCT": 20,
    "DIVERGENCIA_TRANSPORTE_PCT": 2, "ESPESSURA_SERRA_MM": 3, "SOBREMETAL_COMPRIMENTO_MM": 5,
    "SOBREMETAL_LARGURA_MM": 5, "PRAZO_CONFIRMACAO_SA_H": 48, "ATRASO_ATENCAO_DIAS": 7, "ATRASO_ATRASADO_DIAS": 15,
    "DIVERGENCIA_MEGA_KG": 5, "GIRO_DIAS": 180, "PERDA_CORTE_MAX_PCT": 6, "VERIFICACAO_SA_MIN": 30,
    "AVISO_RESERVA_DIAS": 7, "CORTE_DIAS_RETROATIVOS": 7,
}


def parametro(db: Session, chave: str, cfg: Config | None = None) -> float:
    """Valor numérico do parâmetro: tabela `parametro` → .env (tolerâncias antigas) → padrão da especificação."""
    p = db.get(Parametro, chave)
    if p is not None:
        try:
            return float(p.valor.replace(",", "."))
        except ValueError:
            pass
    if cfg is not None:
        do_env = {"TOLERANCIA_EXCESSO_PCT": cfg.tolerancia_excesso_pct,
                  "TOLERANCIA_FALTA_PCT": cfg.tolerancia_falta_pct,
                  "TOLERANCIA_SOBREMETAL_PCT": cfg.tolerancia_sobremetal_pct,
                  "ESPESSURA_SERRA_MM": cfg.espessura_serra_mm}
        if chave in do_env:
            return float(do_env[chave])
    return float(PADROES[chave])


def parametro_texto(db: Session, chave: str, padrao: str) -> str:
    p = db.get(Parametro, chave)
    return p.valor if p is not None else padrao


# ---------------- Notificações (§6, só no sino [P05]) ----------------

def notificar(db: Session, *, perfis: tuple[str, ...] = (), usuarios: tuple[int, ...] = (), tipo: str, texto: str,
              link: str | None = None, exceto_id: int | None = None) -> int:
    """Cria um aviso para cada usuário ativo dos perfis (e/ou ids) informados. Commit fica com quem chama."""
    alvo: set[int] = set(usuarios)
    if perfis:
        alvo |= set(db.scalars(select(Usuario.id).where(Usuario.ativo.is_(True), Usuario.perfil.in_(perfis))))
    if exceto_id is not None:
        alvo.discard(exceto_id)
    for uid in alvo:
        db.add(Notificacao(usuario_id=uid, tipo=tipo, texto=texto[:500], link=link))
    return len(alvo)


# ---------------- Visibilidade por perfil [P10] ----------------

ESTOQUE_ITU = ("ESTOQUE",)
OPERACAO_RJ = ("OPERACAO_RJ",)
ANALISE = ("ANALISE",)


def so_rj_no_rio(usuario: Usuario) -> bool:
    """Perfil Operação RJ (Marcelo) enxerga só lotes, solicitações e COPs do RJ no Rio."""
    return usuario.perfil == "OPERACAO_RJ"


def lote_visivel(usuario: Usuario, lote: Lote) -> bool:
    return not so_rj_no_rio(usuario) or (lote.planta_fiscal == "RJ" and lote.local_fisico == "RJ")
