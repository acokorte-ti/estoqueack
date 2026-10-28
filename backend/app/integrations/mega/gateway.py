"""Integração com o ERP Mega (Oracle 19c).

Fase atual: SOMENTE LEITURA. A escrita está prevista na interface, mas desabilitada
(`MEGA_ESCRITA_HABILITADA=false`). Gravar direto nas tabelas do ERP ignora regras fiscais
e gatilhos do Mega; quando for implementada, deve usar o mecanismo oficial de integração.

As consultas SQL ficam em `consultas.py` e precisam ser ajustadas ao dicionário de dados
real do Mega (nomes de tabelas/colunas) — ver docs/integracao_mega.md.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol

from app.core.config import Config

from . import consultas


@dataclass(frozen=True)
class SaldoMega:
    codigo: int
    descricao: str
    um: str
    saldo_fisico: float
    preco_medio: float | None


@dataclass(frozen=True)
class OrdemProducao:
    numero: int
    item_codigo: int | None
    item_descricao: str | None
    cliente: str | None
    situacao: str | None
    data_emissao: date | None


@dataclass(frozen=True)
class SemiAcabado:
    codigo: int
    descricao: str
    data_cadastro: date | None


class MegaGateway(Protocol):
    def saldos_mp(self) -> list[SaldoMega]: ...
    def ordem_producao(self, numero: int) -> OrdemProducao | None: ...
    def buscar_sa(self, texto: str) -> list[SemiAcabado]: ...


class EscritaDesabilitada(RuntimeError):
    pass


class OracleMegaGateway:
    """Acesso de leitura via python-oracledb (modo thin, sem Oracle Client)."""

    def __init__(self, cfg: Config):
        if not cfg.mega_habilitado:
            raise RuntimeError("Integração Mega desabilitada (MEGA_HABILITADO=false).")
        import oracledb  # import tardio: só carrega quando a integração está ligada

        self._cfg = cfg
        self._pool = oracledb.create_pool(user=cfg.mega_usuario, password=cfg.mega_senha, dsn=cfg.mega_dsn,
                                          min=1, max=4, increment=1)

    def _consultar(self, sql: str, **params) -> list[tuple]:
        with self._pool.acquire() as con:
            with con.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")   # defesa extra além do usuário read-only
                cur.execute(sql, params)
                linhas = cur.fetchall()
            con.rollback()
            return linhas

    def saldos_mp(self) -> list[SaldoMega]:
        return [SaldoMega(int(c), d, um, float(s or 0), float(p) if p is not None else None)
                for c, d, um, s, p in self._consultar(consultas.SALDOS_MP, filial=consultas.FILIAL_ITU)]

    def ordem_producao(self, numero: int) -> OrdemProducao | None:
        linhas = self._consultar(consultas.ORDEM_PRODUCAO, numero=numero)
        if not linhas:
            return None
        n, ic, idesc, cli, sit, dt = linhas[0]
        return OrdemProducao(int(n), int(ic) if ic else None, idesc, cli, sit, dt.date() if dt else None)

    def buscar_sa(self, texto: str) -> list[SemiAcabado]:
        return [SemiAcabado(int(c), d, dt.date() if dt else None)
                for c, d, dt in self._consultar(consultas.BUSCAR_SA, texto=f"%{texto.upper()}%")]

    # ---- Reservado para o futuro (atualizações no Mega pelo sistema) ----
    def solicitar_cadastro_sa(self, *_args, **_kwargs):
        if not self._cfg.mega_escrita_habilitada:
            raise EscritaDesabilitada("Escrita no Mega desabilitada nesta fase.")
        raise NotImplementedError("Definir mecanismo oficial de integração do Mega antes de habilitar.")


class MegaFalso:
    """Implementação em memória para testes e desenvolvimento sem acesso ao ERP."""

    def __init__(self, saldos=None, ops=None, sas=None):
        self._saldos = saldos or []
        self._ops = {o.numero: o for o in (ops or [])}
        self._sas = sas or []

    def saldos_mp(self):
        return list(self._saldos)

    def ordem_producao(self, numero):
        return self._ops.get(numero)

    def buscar_sa(self, texto):
        return [s for s in self._sas if texto.upper() in s.descricao.upper()]
