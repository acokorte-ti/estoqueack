"""Integração com o ERP Mega (Oracle 19c).

Fase atual: SOMENTE LEITURA. A escrita está prevista na interface, mas desabilitada
(`MEGA_ESCRITA_HABILITADA=false`). Gravar direto nas tabelas do ERP ignora regras fiscais
e gatilhos do Mega; quando for implementada, deve usar o mecanismo oficial de integração.

As consultas SQL ficam em `consultas.py` (mapeadas e validadas em 2026-10-29, ver
docs/integracao_mega.md). O banco EXIGE Native Network Encryption → modo thick (Instant Client).
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
    peso_especifico: float | None   # PRO_RE_PESOESPECIFICO (densidade cadastrada no Mega)


@dataclass(frozen=True)
class OrdemProducao:
    numero: int
    item_codigo: int | None
    item_descricao: str | None
    cliente: str | None
    situacao: str | None            # 'AB' = aberta (demais códigos a confirmar)
    data_emissao: date | None
    quantidade: float | None = None
    data_recebimento: date | None = None


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

        if cfg.mega_instant_client and oracledb.is_thin_mode():
            oracledb.init_oracle_client(lib_dir=cfg.mega_instant_client)
        self._cfg = cfg
        self._pool = oracledb.create_pool(user=cfg.mega_usuario, password=cfg.mega_senha, dsn=cfg.mega_dsn,
                                          min=1, max=2, increment=1)
        # 2 workers × 2 conexões = 4, igual ao SESSIONS_PER_USER do perfil estoqueack_ro_perfil no Oracle

    def _consultar(self, sql: str, **params) -> list[tuple]:
        with self._pool.acquire() as con:
            with con.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")   # defesa extra além do usuário read-only
                cur.execute(sql, params)
                linhas = cur.fetchall()
            con.rollback()
            return linhas

    def saldos_mp(self, data_corte: date | None = None) -> list[SaldoMega]:
        """Saldo por código de MP na filial de Itu. `data_corte` exclusiva (padrão: amanhã = saldo atual)."""
        import datetime as _dt
        corte = data_corte or (_dt.date.today() + _dt.timedelta(days=1))
        return [SaldoMega(int(c), d, um, float(s or 0), float(pe) if pe is not None else None)
                for c, d, um, s, pe in self._consultar(consultas.SALDOS_MP, filial=consultas.FILIAL_ITU,
                                                        data_corte=corte)]

    def ordem_producao(self, numero: int) -> OrdemProducao | None:
        linhas = self._consultar(consultas.ORDEM_PRODUCAO, numero=numero, filial=consultas.FILIAL_ITU)
        if not linhas:
            return None
        n, ic, idesc, cli, sit, dt, qtd, receb = linhas[0]
        return OrdemProducao(int(n), int(ic) if ic else None, idesc, cli, sit, dt.date() if dt else None,
                             float(qtd) if qtd is not None else None, receb.date() if receb else None)

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
