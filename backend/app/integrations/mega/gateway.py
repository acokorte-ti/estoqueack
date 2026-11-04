"""Integração com o ERP Mega (Oracle 19c).

Fase atual: SOMENTE LEITURA. A escrita está prevista na interface, mas desabilitada
(`MEGA_ESCRITA_HABILITADA=false`). Gravar direto nas tabelas do ERP ignora regras fiscais
e gatilhos do Mega; quando for implementada, deve usar o mecanismo oficial de integração.

As consultas SQL ficam em `consultas.py` (mapeadas e validadas em 2026-10-29, ver
docs/integracao_mega.md). O banco EXIGE Native Network Encryption → modo thick (Instant Client).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
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
    situacao: str | None            # ORD_ST_SITUACAO (ver consultas.SITUACOES_OP)
    data_emissao: date | None
    quantidade: float | None = None
    data_recebimento: date | None = None
    pedido: str | None = None       # nº do pedido de venda (série '1'), sem a série
    cliente_codigo: int | None = None
    tipo: str | None = None         # TPO_ST_CODIGO_TIPO (OP001 normal, OP016 estoque, OS001 serviço…)


@dataclass(frozen=True)
class SituacaoSa:
    codigo: int
    existe: bool
    descricao: str | None = None
    ativo: bool | None = None
    data_cadastro: date | None = None
    qtd_entrada: float = 0.0         # PEÇAS (UM do SA = PC) que entraram desde a data pedida = carga do SA
    nf_entrada: str | None = None    # nº da NF da entrada por compra (TPM 1) = NF Fio Certo / Médio Vale
    ncm: str | None = None
    ipi_pct: float | None = None     # alíquota de IPI do NCM no Mega (TRF_NCM), em %


@dataclass(frozen=True)
class ComponenteOp:
    """Linha da estrutura da OP (PRO_DEMANDA_DEP): o SA (material RJ) ou a MP em kg (material Itu)."""
    codigo: int
    descricao: str | None
    definicao: str | None           # PRO_ST_DEFITEM ('MP', 'CO', 'PA'…)
    um: str | None
    qtd_necessaria: float
    qtd_unitaria: float | None = None
    qtd_requisitada: float | None = None

    @property
    def tipo(self) -> str:
        if (self.descricao or "").upper().startswith("SA "):
            return "SA"
        return "MP" if self.definicao == "MP" else "OUTRO"


@dataclass(frozen=True)
class MovimentoMega:
    lancamento: int
    data: date
    entrada_saida: str              # ED | SD
    tpm: int
    tpm_descricao: str | None
    documento: str | None
    codigo: int
    kg: float                       # sempre positivo; o sinal vem de entrada_saida
    codigo_destino: int | None = None
    estorno: bool = False
    incluido_em: date | None = None
    alterado_em: datetime | None = None
    usuario: int | None = None


@dataclass(frozen=True)
class SemiAcabado:
    codigo: int
    descricao: str
    data_cadastro: date | None


class MegaGateway(Protocol):
    def saldos_mp(self, data_corte: date | None = None) -> list[SaldoMega]: ...
    def precos_medios_mp(self, data_corte: date | None = None) -> dict[int, tuple[float, date]]: ...
    def movimentos_janela(self, desde: date, alterado_desde: date, ultimo_lancamento: int) -> list[MovimentoMega]: ...
    def ordem_producao(self, numero: int) -> OrdemProducao | None: ...
    def estrutura_op(self, numero: int) -> list[ComponenteOp]: ...
    def buscar_sa(self, texto: str) -> list[SemiAcabado]: ...
    def situacao_sa(self, codigo: int, desde: date) -> SituacaoSa | None: ...


class EscritaDesabilitada(RuntimeError):
    pass


class OracleMegaGateway:
    """Acesso de leitura via python-oracledb em modo thick (Instant Client 19; o banco exige NNE)."""

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

    def precos_medios_mp(self, data_corte: date | None = None) -> dict[int, tuple[float, date]]:
        """Custo médio (R$/kg) mais recente por código de MP na filial 3: {codigo: (valor, data)}."""
        import datetime as _dt
        corte = data_corte or (_dt.date.today() + _dt.timedelta(days=1))
        return {int(c): (float(v), d.date()) for c, v, d in
                self._consultar(consultas.PRECOS_MEDIOS_MP, filial=consultas.FILIAL_ITU, data_corte=corte)
                if v is not None}

    def movimentos_janela(self, desde: date, alterado_desde: date, ultimo_lancamento: int) -> list[MovimentoMega]:
        def _d(v):
            return v.date() if isinstance(v, datetime) else v
        return [MovimentoMega(int(lc), _d(dt), es, int(tpm), tdesc, doc, int(cod), float(q or 0),
                              int(dest) if dest else None, est == "S", _d(inc), alt, int(usu) if usu else None)
                for lc, dt, es, tpm, tdesc, doc, cod, q, dest, est, inc, alt, usu in
                self._consultar(consultas.MOVIMENTOS_JANELA, filial=consultas.FILIAL_ITU, desde=desde,
                                alterado_desde=alterado_desde, ultimo_lancamento=ultimo_lancamento)]

    def codigos_com_movimento(self, codigos: list[int], desde: date) -> set[int]:
        """Kardex: quais códigos tiveram movimento na filial 3 desde a data (em lotes de 500 binds)."""
        out: set[int] = set()
        for i in range(0, len(codigos), 500):
            parte = codigos[i:i + 500]
            params = {f"c{j}": c for j, c in enumerate(parte)}
            out |= {int(r[0]) for r in self._consultar(consultas.codigos_com_movimento(len(parte)),
                                                         filial=consultas.FILIAL_ITU, desde=desde, **params)}
        return out

    def ordem_producao(self, numero: int) -> OrdemProducao | None:
        linhas = self._consultar(consultas.ORDEM_PRODUCAO, numero=numero, filial=consultas.FILIAL_ITU)
        if not linhas:
            return None
        n, ic, idesc, cli, sit, dt, qtd, receb, ped, cli_cod, tipo = linhas[0]
        return OrdemProducao(int(n), int(ic) if ic else None, idesc, cli, sit, dt.date() if dt else None,
                             float(qtd) if qtd is not None else None, receb.date() if receb else None,
                             pedido=str(int(ped)) if ped is not None else None,
                             cliente_codigo=int(cli_cod) if cli_cod is not None else None, tipo=tipo)

    def estrutura_op(self, numero: int) -> list[ComponenteOp]:
        f = lambda v: float(v) if v is not None else None  # noqa: E731
        return [ComponenteOp(int(c), d, dfi, um, float(nec or 0), f(uni), f(req))
                for c, d, dfi, um, nec, uni, req in self._consultar(consultas.ESTRUTURA_OP, numero=numero,
                                                                     filial=consultas.FILIAL_ITU)]

    def buscar_sa(self, texto: str) -> list[SemiAcabado]:
        return [SemiAcabado(int(c), d, dt.date() if dt else None)
                for c, d, dt in self._consultar(consultas.BUSCAR_SA, texto=f"%{texto.upper()}%")]

    def situacao_sa(self, codigo: int, desde: date) -> SituacaoSa:
        linhas = self._consultar(consultas.SITUACAO_SA, codigo=codigo, desde=desde)
        if not linhas:
            return SituacaoSa(codigo, False)
        _c, desc, dt, ativo, ncm, ipi, qtd_itu, qtd_rj, nf = linhas[0]
        return SituacaoSa(codigo, True, desc, ativo == "S", dt.date() if dt else None,
                          float(max(qtd_itu or 0, qtd_rj or 0)), nf, str(ncm) if ncm is not None else None,
                          float(ipi) if ipi is not None else None)

    # ---- Reservado para o futuro (atualizações no Mega pelo sistema) ----
    def solicitar_cadastro_sa(self, *_args, **_kwargs):
        if not self._cfg.mega_escrita_habilitada:
            raise EscritaDesabilitada("Escrita no Mega desabilitada nesta fase.")
        raise NotImplementedError("Definir mecanismo oficial de integração do Mega antes de habilitar.")


class MegaFalso:
    """Implementação em memória para testes e desenvolvimento sem acesso ao ERP."""

    def __init__(self, saldos=None, ops=None, sas=None, situacoes_sa=None, estruturas=None, precos=None,
                 movimentos=None):
        self.saldos = list(saldos or [])
        self._ops = {o.numero: o for o in (ops or [])}
        self._sas = sas or []
        self.situacoes_sa: dict[int, SituacaoSa] = dict(situacoes_sa or {})
        self.estruturas: dict[int, list[ComponenteOp]] = dict(estruturas or {})
        self.precos: dict[int, tuple[float, date]] = dict(precos or {})
        self.movimentos: list[MovimentoMega] = list(movimentos or [])
        self.falhar = False                     # simula Mega fora do ar na sincronização

    def codigos_com_movimento(self, codigos, desde):
        return {m.codigo for m in self.movimentos if m.codigo in set(codigos) and m.data >= desde}

    def saldos_mp(self, data_corte=None):
        if self.falhar:
            raise RuntimeError("Mega fora do ar (simulado)")
        return list(self.saldos)

    def precos_medios_mp(self, data_corte=None):
        return dict(self.precos)

    def movimentos_janela(self, desde, alterado_desde, ultimo_lancamento):
        return [m for m in self.movimentos if m.data >= desde or m.lancamento > ultimo_lancamento
                or (m.alterado_em is not None and m.alterado_em.date() >= alterado_desde)]

    def ordem_producao(self, numero):
        return self._ops.get(numero)

    def estrutura_op(self, numero):
        return list(self.estruturas.get(numero, []))

    def buscar_sa(self, texto):
        return [s for s in self._sas if texto.upper() in s.descricao.upper()]

    def situacao_sa(self, codigo, desde):
        return self.situacoes_sa.get(codigo, SituacaoSa(codigo, False))
