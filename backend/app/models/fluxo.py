"""Fluxo da Fase 1 (especificação v3, §2, §3 e §11): solicitação → corte RJ → COP → SA → NF → envio → recebimento,
corte em Itu (consumo, sobra, RETO) e entrada por NF no RJ.

As situações das solicitações são **derivadas** dos fatos (cortes, COP, SA, recebimento) por
`app.services.fluxo.recalcular_solicitacao`; a coluna `situacao` guarda o último valor calculado para
filtrar e ordenar rápido.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

from ._tipos import DataHora, JsonDoc, Kg, Mm, agora
from .estoque import Lote

SITUACOES_SOLICITACAO = ("RASCUNHO", "ENVIADA", "MATERIAL_INSUFICIENTE", "CORTADA_PARCIAL", "CORTADA", "EM_COP",
                         "SA_PRONTO", "EM_TRANSITO", "AGUARDANDO_CORTE_ITU", "CONCLUIDA", "CANCELADA")
MODOS = ("CORTAR_RJ", "TRAZER_INTEIRA")
SITUACOES_COP = ("ABERTO", "FECHADO", "ENVIADO", "RECEBIDO_PARCIAL", "RECEBIDO")
SITUACOES_SA = ("PENDENTE", "PREPARADO", "AGUARDANDO_MEGA", "CONFIRMADO")
ORIGENS_SA = ("COP", "CORTE_ITU", "CARGA")


def _in(col: str, valores: tuple[str, ...]) -> str:
    return f"{col} IN (" + ",".join(f"'{v}'" for v in valores) + ")"


class OrdemProducao(Base):
    """Cache da OP lida do Mega (ou digitada com o Mega fora do ar: fonte = DIGITADO)."""
    __tablename__ = "ordem_producao"

    numero: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    item_codigo: Mapped[int | None] = mapped_column(Integer, index=True)
    item_descricao: Mapped[str | None] = mapped_column(String(200))
    cliente_codigo: Mapped[int | None] = mapped_column(Integer)
    cliente: Mapped[str | None] = mapped_column(String(160))
    pedido: Mapped[str | None] = mapped_column(String(40))
    situacao: Mapped[str | None] = mapped_column(String(10))
    quantidade: Mapped[float | None] = mapped_column(Kg)
    data_entrega: Mapped[date | None] = mapped_column(Date)
    fonte: Mapped[str] = mapped_column(String(10), default="MEGA")
    atualizado_em: Mapped[datetime] = mapped_column(DataHora, default=agora)


class SolicitacaoCorte(Base):
    """Uma solicitação = uma OP + um lote (T07). Duas bitolas para a mesma OP = duas solicitações."""
    __tablename__ = "solicitacao_corte"
    __table_args__ = (
        CheckConstraint(_in("situacao", SITUACOES_SOLICITACAO), name="ck_sol_situacao"),
        CheckConstraint(_in("modo", MODOS), name="ck_sol_modo"),
        CheckConstraint("quantidade > 0", name="ck_sol_qtd"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    op: Mapped[int] = mapped_column(Integer, index=True)
    item_codigo: Mapped[int | None] = mapped_column(Integer, index=True)
    item_descricao: Mapped[str | None] = mapped_column(String(200))
    cliente: Mapped[str | None] = mapped_column(String(160))
    pedido: Mapped[str | None] = mapped_column(String(40))
    op_confirmada_mega: Mapped[bool] = mapped_column(Boolean, default=True)
    lote_id: Mapped[int] = mapped_column(ForeignKey("lote.id"), index=True)
    modo: Mapped[str] = mapped_column(String(15))
    quantidade: Mapped[int] = mapped_column(Integer)
    # medida acabada
    formato: Mapped[str] = mapped_column(String(15))
    acabada_espessura: Mapped[float | None] = mapped_column(Mm)
    acabada_largura: Mapped[float | None] = mapped_column(Mm)
    acabada_diametro: Mapped[float | None] = mapped_column(Mm)
    acabada_comprimento: Mapped[float | None] = mapped_column(Mm)
    sobremetal_comprimento_mm: Mapped[float] = mapped_column(Mm, default=5)
    sobremetal_largura_mm: Mapped[float] = mapped_column(Mm, default=0)
    # dimensões brutas de corte (bitola + sobremetal), editáveis
    bruto_espessura: Mapped[float | None] = mapped_column(Mm)
    bruto_largura: Mapped[float | None] = mapped_column(Mm)
    bruto_diametro: Mapped[float | None] = mapped_column(Mm)
    bruto_comprimento: Mapped[float | None] = mapped_column(Mm)
    peso_peca_kg: Mapped[float | None] = mapped_column(Kg)       # acabada × densidade × qtd (referência)
    peso_previsto_kg: Mapped[float] = mapped_column(Kg)          # bruto × densidade × qtd
    sobremetal_pct: Mapped[float | None] = mapped_column(Kg)
    comprimento_barra_mm: Mapped[float | None] = mapped_column(Mm)   # peça inteira, opcional [P14]
    instrucao: Mapped[str | None] = mapped_column(String(300))
    instrucao_processo: Mapped[str | None] = mapped_column(String(300))
    observacao: Mapped[str | None] = mapped_column(String(1000))
    prazo: Mapped[date | None] = mapped_column(Date)
    situacao: Mapped[str] = mapped_column(String(25), default="RASCUNHO", index=True)
    encerrada_saldo_pendente: Mapped[bool] = mapped_column(Boolean, default=False)
    motivo: Mapped[str | None] = mapped_column(String(500))      # material insuficiente / cancelamento / encerramento
    confirmacoes: Mapped[dict[str, Any] | None] = mapped_column(JsonDoc)
    enviada_em: Mapped[datetime | None] = mapped_column(DataHora)
    criado_em: Mapped[datetime] = mapped_column(DataHora, default=agora)
    criado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    atualizado_em: Mapped[datetime] = mapped_column(DataHora, default=agora, onupdate=agora)
    origem_ref: Mapped[dict[str, Any] | None] = mapped_column(JsonDoc)   # carga: {arquivo, aba, linha}

    lote: Mapped[Lote] = relationship()
    liberacoes: Mapped[list[LiberacaoCorte]] = relationship(back_populates="solicitacao",
                                                            order_by="LiberacaoCorte.id")


class LiberacaoCorte(Base):
    """Corte registrado no RJ (T10). Várias por solicitação quando o RJ troca ou divide o lote."""
    __tablename__ = "liberacao_corte"
    __table_args__ = (CheckConstraint("peso_real_kg > 0", name="ck_lib_peso"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    solicitacao_id: Mapped[int] = mapped_column(ForeignKey("solicitacao_corte.id"), index=True)
    lote_id: Mapped[int] = mapped_column(ForeignKey("lote.id"), index=True)
    pecas: Mapped[int] = mapped_column(Integer)
    peso_real_kg: Mapped[float] = mapped_column(Kg)
    comprimento_barra_mm: Mapped[float | None] = mapped_column(Mm)
    data_corte: Mapped[date] = mapped_column(Date)
    observacao: Mapped[str | None] = mapped_column(String(1000))
    estornada: Mapped[bool] = mapped_column(Boolean, default=False)
    confirmacoes: Mapped[dict[str, Any] | None] = mapped_column(JsonDoc)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    criado_em: Mapped[datetime] = mapped_column(DataHora, default=agora)
    origem_ref: Mapped[dict[str, Any] | None] = mapped_column(JsonDoc)

    solicitacao: Mapped[SolicitacaoCorte] = relationship(back_populates="liberacoes")
    lote: Mapped[Lote] = relationship()
    cop_item: Mapped[CopItem | None] = relationship(back_populates="liberacao", uselist=False)


class NfTransferencia(Base):
    """NF de transferência RJ → Itu (Fio Certo / Médio Vale). Uma NF serve vários itens e até dois COPs."""
    __tablename__ = "nf_transferencia"
    __table_args__ = (UniqueConstraint("numero", "emitente", name="uq_nf_numero_emitente"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    numero: Mapped[str] = mapped_column(String(20), index=True)
    emitente: Mapped[str] = mapped_column(String(40))
    data: Mapped[date | None] = mapped_column(Date)
    criado_em: Mapped[datetime] = mapped_column(DataHora, default=agora)


class Cop(Base):
    """COP (T11): Aberto → Fechado (gera SAs) → [Aguardando NF] → Enviado → Recebido parcial → Recebido."""
    __tablename__ = "cop"
    __table_args__ = (CheckConstraint(_in("situacao", SITUACOES_COP), name="ck_cop_situacao"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    numero: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    situacao: Mapped[str] = mapped_column(String(20), default="ABERTO", index=True)
    observacao: Mapped[str | None] = mapped_column(String(1000))
    criado_em: Mapped[datetime] = mapped_column(DataHora, default=agora)
    criado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    fechado_em: Mapped[datetime | None] = mapped_column(DataHora)
    enviado_em: Mapped[datetime | None] = mapped_column(DataHora)
    recebido_em: Mapped[datetime | None] = mapped_column(DataHora)
    origem_ref: Mapped[dict[str, Any] | None] = mapped_column(JsonDoc)

    itens: Mapped[list[CopItem]] = relationship(back_populates="cop", order_by="CopItem.id")


class CopItem(Base):
    __tablename__ = "cop_item"
    __table_args__ = (CheckConstraint(_in("situacao", ("EM_COP", "EM_TRANSITO", "RECEBIDO")),
                                      name="ck_copitem_situacao"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    cop_id: Mapped[int] = mapped_column(ForeignKey("cop.id"), index=True)
    liberacao_id: Mapped[int] = mapped_column(ForeignKey("liberacao_corte.id"), unique=True)
    nf_id: Mapped[int | None] = mapped_column(ForeignKey("nf_transferencia.id"), index=True)
    situacao: Mapped[str] = mapped_column(String(15), default="EM_COP")
    peso_conferido_kg: Mapped[float | None] = mapped_column(Kg)
    recebido_em: Mapped[datetime | None] = mapped_column(DataHora)
    recebido_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    lote_itu_id: Mapped[int | None] = mapped_column(ForeignKey("lote.id"))     # peça inteira recebida
    confirmacoes: Mapped[dict[str, Any] | None] = mapped_column(JsonDoc)

    cop: Mapped[Cop] = relationship(back_populates="itens")
    liberacao: Mapped[LiberacaoCorte] = relationship(back_populates="cop_item")
    nf: Mapped[NfTransferencia | None] = relationship()


class DivergenciaRecebimento(Base):
    """T12 'Registrar divergência' [R006]: não bloqueia; entra no relatório de exceções."""
    __tablename__ = "divergencia_recebimento"
    __table_args__ = (CheckConstraint(_in("tipo", ("FALTANDO", "DANIFICADO", "PESO_DIFERENTE")),
                                      name="ck_div_tipo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    cop_item_id: Mapped[int] = mapped_column(ForeignKey("cop_item.id"), index=True)
    tipo: Mapped[str] = mapped_column(String(20))
    pecas: Mapped[int | None] = mapped_column(Integer)
    kg: Mapped[float | None] = mapped_column(Kg)
    observacao: Mapped[str] = mapped_column(String(1000))
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    criado_em: Mapped[datetime] = mapped_column(DataHora, default=agora)


class CorteItu(Base):
    """T13: consumo da OP, sobra (na bitola ou RETO) e perda de corte, em lote RJ em Itu ou Estoque Mega."""
    __tablename__ = "corte_itu"

    id: Mapped[int] = mapped_column(primary_key=True)
    op: Mapped[int] = mapped_column(Integer, index=True)
    item_codigo: Mapped[int | None] = mapped_column(Integer)
    cliente: Mapped[str | None] = mapped_column(String(160))
    lote_id: Mapped[int] = mapped_column(ForeignKey("lote.id"), index=True)
    solicitacao_id: Mapped[int | None] = mapped_column(ForeignKey("solicitacao_corte.id"), index=True)
    pecas: Mapped[int | None] = mapped_column(Integer)
    peso_usado_kg: Mapped[float] = mapped_column(Kg)      # peso do material antes do corte (padrão: saldo do lote)
    consumo_kg: Mapped[float] = mapped_column(Kg)
    sobra_kg: Mapped[float] = mapped_column(Kg, default=0)
    sobra_na_bitola: Mapped[bool] = mapped_column(Boolean, default=True)
    perda_kg: Mapped[float] = mapped_column(Kg, default=0)
    previsto_kg: Mapped[float | None] = mapped_column(Kg)
    lote_reto_id: Mapped[int | None] = mapped_column(ForeignKey("lote.id"))
    instrucao_mega: Mapped[str | None] = mapped_column(String(500))
    observacao: Mapped[str | None] = mapped_column(String(1000))
    confirmacoes: Mapped[dict[str, Any] | None] = mapped_column(JsonDoc)
    data_corte: Mapped[date] = mapped_column(Date)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    criado_em: Mapped[datetime] = mapped_column(DataHora, default=agora)

    lote: Mapped[Lote] = relationship(foreign_keys=[lote_id])


class CadastroSa(Base):
    """Linha de SA (T14). Nasce do COP fechado (caminhos A/B), do corte em Itu de lote fiscal RJ (B2) ou da carga."""
    __tablename__ = "cadastro_sa"
    __table_args__ = (
        CheckConstraint(_in("situacao", SITUACOES_SA), name="ck_sa_situacao"),
        CheckConstraint(_in("origem", ORIGENS_SA), name="ck_sa_origem"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    origem: Mapped[str] = mapped_column(String(10))
    cop_item_id: Mapped[int | None] = mapped_column(ForeignKey("cop_item.id"), unique=True)
    corte_itu_id: Mapped[int | None] = mapped_column(ForeignKey("corte_itu.id"), index=True)
    solicitacao_id: Mapped[int | None] = mapped_column(ForeignKey("solicitacao_corte.id"), index=True)
    lote_id: Mapped[int | None] = mapped_column(ForeignKey("lote.id"), index=True)
    data: Mapped[date] = mapped_column(Date, default=date.today)
    op: Mapped[int | None] = mapped_column(Integer, index=True)
    item_codigo: Mapped[int | None] = mapped_column(Integer, index=True)     # item da PEÇA ACABADA (OP)
    item_descricao: Mapped[str | None] = mapped_column(String(200))
    cliente: Mapped[str | None] = mapped_column(String(160))
    pedido: Mapped[str | None] = mapped_column(String(40))
    material: Mapped[str | None] = mapped_column(String(60))
    dimensao: Mapped[str | None] = mapped_column(String(60))
    conteiner: Mapped[str | None] = mapped_column(String(30))
    quantidade: Mapped[int | None] = mapped_column(Integer)
    peso_kg: Mapped[float | None] = mapped_column(Kg)
    rs_kg: Mapped[float | None] = mapped_column(Kg)                # manual e opcional [P16]
    sa_codigo: Mapped[int | None] = mapped_column(Integer, index=True)
    sa_codigo_sugerido: Mapped[int | None] = mapped_column(Integer)
    sa_novo: Mapped[bool] = mapped_column(Boolean, default=False)   # peça acabada nunca teve SA
    sa_descricao: Mapped[str | None] = mapped_column(String(200))
    ncm: Mapped[str | None] = mapped_column(String(15))
    icms: Mapped[str | None] = mapped_column(String(10))
    ipi: Mapped[str | None] = mapped_column(String(10))
    nf_id: Mapped[int | None] = mapped_column(ForeignKey("nf_transferencia.id"), index=True)
    situacao: Mapped[str] = mapped_column(String(20), default="PENDENTE", index=True)
    preparado_em: Mapped[datetime | None] = mapped_column(DataHora)
    informado_em: Mapped[datetime | None] = mapped_column(DataHora)
    confirmado_em: Mapped[datetime | None] = mapped_column(DataHora)
    verificado_mega_em: Mapped[datetime | None] = mapped_column(DataHora)
    exportado_renato_em: Mapped[datetime | None] = mapped_column(DataHora)
    alterado_apos_exportar: Mapped[bool] = mapped_column(Boolean, default=False)
    confirmacoes: Mapped[dict[str, Any] | None] = mapped_column(JsonDoc)
    dados_extra: Mapped[dict[str, Any] | None] = mapped_column(JsonDoc)   # carga: pedido, NF Renafer etc.
    criado_em: Mapped[datetime] = mapped_column(DataHora, default=agora)
    origem_ref: Mapped[dict[str, Any] | None] = mapped_column(JsonDoc)

    nf: Mapped[NfTransferencia | None] = relationship()
    cop_item: Mapped[CopItem | None] = relationship()


class EntradaNf(Base):
    """T06: NF de entrada no RJ. Cada item vira um lote RJ/RJ."""
    __tablename__ = "entrada_nf"
    __table_args__ = (UniqueConstraint("numero", "fornecedor", name="uq_entrada_nf"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    numero: Mapped[str] = mapped_column(String(20))
    fornecedor: Mapped[str] = mapped_column(String(120))
    data: Mapped[date] = mapped_column(Date)
    conteiner_id: Mapped[int] = mapped_column(ForeignKey("conteiner.id"), index=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    criado_em: Mapped[datetime] = mapped_column(DataHora, default=agora)

    itens: Mapped[list[EntradaNfItem]] = relationship(back_populates="entrada")


class EntradaNfItem(Base):
    __tablename__ = "entrada_nf_item"

    id: Mapped[int] = mapped_column(primary_key=True)
    entrada_id: Mapped[int] = mapped_column(ForeignKey("entrada_nf.id"), index=True)
    lote_id: Mapped[int] = mapped_column(ForeignKey("lote.id"), unique=True)
    descricao_nf: Mapped[str | None] = mapped_column(String(200))
    pecas: Mapped[int | None] = mapped_column(Integer)
    peso_kg: Mapped[float] = mapped_column(Kg)
    comprimento: Mapped[str | None] = mapped_column(String(40))
    custo_kg: Mapped[float | None] = mapped_column(Kg)

    entrada: Mapped[EntradaNf] = relationship(back_populates="itens")
