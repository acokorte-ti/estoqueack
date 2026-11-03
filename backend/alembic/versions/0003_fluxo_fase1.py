"""Fase 1 (especificação v3): solicitação, corte RJ, COP, NF de transferência, SA, recebimento, corte em Itu,
entrada por NF, parâmetros, notificações, cache/sincronização do Mega, equivalência de ligas, paridade RJ ↔ CM e
material a chegar.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-03
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

JSON = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
TS = sa.DateTime(timezone=True)
KG = sa.Numeric(14, 3)
MM = sa.Numeric(10, 2)


def _in(col, valores):
    return f"{col} IN (" + ",".join(f"'{v}'" for v in valores) + ")"


SIT_SOL = ("RASCUNHO", "ENVIADA", "MATERIAL_INSUFICIENTE", "CORTADA_PARCIAL", "CORTADA", "EM_COP", "SA_PRONTO",
           "EM_TRANSITO", "AGUARDANDO_CORTE_ITU", "CONCLUIDA", "CANCELADA")

# T23 — valores da especificação v3 (R008 com os valores propostos pelo FUNCIONAL; ajustáveis na tela)
PARAMETROS = [
    ("TOLERANCIA_EXCESSO_PCT", "5", "NUMERO", "Tolerância de pesagem acima do previsto (%)"),
    ("TOLERANCIA_SOBREMETAL_PCT", "20", "NUMERO", "Tolerância de sobremetal na solicitação (%)"),
    ("TOLERANCIA_FALTA_PCT", "20", "NUMERO", "Tolerância abaixo do previsto (%)"),
    ("DIVERGENCIA_TRANSPORTE_PCT", "2", "NUMERO", "Divergência de peso no recebimento do COP (%)"),
    ("ESPESSURA_SERRA_MM", "3", "NUMERO", "Espessura da serra (mm)"),
    ("SOBREMETAL_COMPRIMENTO_MM", "5", "NUMERO", "Sobremetal sugerido no comprimento (mm)"),
    ("SOBREMETAL_LARGURA_MM", "5", "NUMERO", "Sobremetal sugerido na largura, peça de chapa larga (mm)"),
    ("PRAZO_CONFIRMACAO_SA_H", "48", "NUMERO", "Prazo de confirmação do SA no Mega (horas)"),
    ("ATRASO_ATENCAO_DIAS", "7", "NUMERO", "Atraso: até este nº de dias é Normal"),
    ("ATRASO_ATRASADO_DIAS", "15", "NUMERO", "Atraso: acima deste nº de dias é Atrasado"),
    ("SYNC_MEGA_HORARIOS", "06:00,13:00", "HORARIOS", "Horários da sincronização com o Mega"),
    ("DIVERGENCIA_MEGA_KG", "5", "NUMERO", "Limite de divergência Mega × lotes por código (kg)"),
    ("GIRO_DIAS", "180", "NUMERO", "Lote sem movimento para o relatório de giro (dias)"),
    ("PERDA_CORTE_MARGEM_PCT", "50", "NUMERO", "Margem sobre a perda esperada de serra (%)"),
    ("VERIFICACAO_SA_MIN", "30", "NUMERO", "Intervalo de verificação de SA aguardando Mega (min)"),
    ("AVISO_RESERVA_DIAS", "7", "NUMERO", "Aviso de reserva vencendo (dias antes)"),
    ("CORTE_DIAS_RETROATIVOS", "7", "NUMERO", "Data do corte: até quantos dias para trás"),
]

# [P18] ligas que faltavam para as equivalências da especificação
LIGAS_NOVAS = [("1.2344", "DIN 1.2344 (equivalente ao H13)", 7.80), ("1.2379", "DIN 1.2379 (equivalente ao D2)", 7.70)]
EQUIVALENCIAS = [("1.2344", "H13"), ("1.2379", "D2")]


def upgrade() -> None:
    # ---- catálogo ----
    with op.batch_alter_table("item_mp") as b:
        b.add_column(sa.Column("substituido_por_id", sa.Integer, sa.ForeignKey("item_mp.id",
                                                                                name="fk_item_substituido")))
    with op.batch_alter_table("lote") as b:
        b.add_column(sa.Column("origem_ref", JSON))

    op.create_table(
        "ordem_producao",
        sa.Column("numero", sa.Integer, primary_key=True, autoincrement=False),
        sa.Column("item_codigo", sa.Integer, index=True),
        sa.Column("item_descricao", sa.String(200)),
        sa.Column("cliente_codigo", sa.Integer),
        sa.Column("cliente", sa.String(160)),
        sa.Column("pedido", sa.String(40)),
        sa.Column("situacao", sa.String(10)),
        sa.Column("quantidade", KG),
        sa.Column("data_entrega", sa.Date),
        sa.Column("fonte", sa.String(10), nullable=False, server_default="MEGA"),
        sa.Column("atualizado_em", TS, nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "solicitacao_corte",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("op", sa.Integer, nullable=False, index=True),
        sa.Column("item_codigo", sa.Integer, index=True),
        sa.Column("item_descricao", sa.String(200)),
        sa.Column("cliente", sa.String(160)),
        sa.Column("pedido", sa.String(40)),
        sa.Column("op_confirmada_mega", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("lote_id", sa.Integer, sa.ForeignKey("lote.id"), nullable=False, index=True),
        sa.Column("modo", sa.String(15), nullable=False),
        sa.Column("quantidade", sa.Integer, nullable=False),
        sa.Column("formato", sa.String(15), nullable=False),
        sa.Column("acabada_espessura", MM), sa.Column("acabada_largura", MM),
        sa.Column("acabada_diametro", MM), sa.Column("acabada_comprimento", MM),
        sa.Column("sobremetal_comprimento_mm", MM, nullable=False, server_default="5"),
        sa.Column("sobremetal_largura_mm", MM, nullable=False, server_default="0"),
        sa.Column("bruto_espessura", MM), sa.Column("bruto_largura", MM),
        sa.Column("bruto_diametro", MM), sa.Column("bruto_comprimento", MM),
        sa.Column("peso_peca_kg", KG),
        sa.Column("peso_previsto_kg", KG, nullable=False),
        sa.Column("sobremetal_pct", KG),
        sa.Column("comprimento_barra_mm", MM),
        sa.Column("instrucao", sa.String(300)),
        sa.Column("instrucao_processo", sa.String(300)),
        sa.Column("observacao", sa.String(1000)),
        sa.Column("prazo", sa.Date),
        sa.Column("situacao", sa.String(25), nullable=False, server_default="RASCUNHO", index=True),
        sa.Column("encerrada_saldo_pendente", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("motivo", sa.String(500)),
        sa.Column("confirmacoes", JSON),
        sa.Column("enviada_em", TS),
        sa.Column("criado_em", TS, nullable=False, server_default=sa.func.now()),
        sa.Column("criado_por_id", sa.Integer, sa.ForeignKey("usuario.id")),
        sa.Column("atualizado_em", TS, nullable=False, server_default=sa.func.now()),
        sa.Column("origem_ref", JSON),
        sa.CheckConstraint(_in("situacao", SIT_SOL), name="ck_sol_situacao"),
        sa.CheckConstraint(_in("modo", ("CORTAR_RJ", "TRAZER_INTEIRA")), name="ck_sol_modo"),
        sa.CheckConstraint("quantidade > 0", name="ck_sol_qtd"),
    )
    op.create_table(
        "liberacao_corte",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("solicitacao_id", sa.Integer, sa.ForeignKey("solicitacao_corte.id"), nullable=False, index=True),
        sa.Column("lote_id", sa.Integer, sa.ForeignKey("lote.id"), nullable=False, index=True),
        sa.Column("pecas", sa.Integer, nullable=False),
        sa.Column("peso_real_kg", KG, nullable=False),
        sa.Column("comprimento_barra_mm", MM),
        sa.Column("data_corte", sa.Date, nullable=False),
        sa.Column("observacao", sa.String(1000)),
        sa.Column("estornada", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("confirmacoes", JSON),
        sa.Column("usuario_id", sa.Integer, sa.ForeignKey("usuario.id")),
        sa.Column("criado_em", TS, nullable=False, server_default=sa.func.now()),
        sa.Column("origem_ref", JSON),
        sa.CheckConstraint("peso_real_kg > 0", name="ck_lib_peso"),
    )
    op.create_table(
        "nf_transferencia",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("numero", sa.String(20), nullable=False, index=True),
        sa.Column("emitente", sa.String(40), nullable=False),
        sa.Column("data", sa.Date),
        sa.Column("criado_em", TS, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("numero", "emitente", name="uq_nf_numero_emitente"),
    )
    op.create_table(
        "cop",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("numero", sa.Integer, nullable=False, unique=True, index=True),
        sa.Column("situacao", sa.String(20), nullable=False, server_default="ABERTO", index=True),
        sa.Column("observacao", sa.String(1000)),
        sa.Column("criado_em", TS, nullable=False, server_default=sa.func.now()),
        sa.Column("criado_por_id", sa.Integer, sa.ForeignKey("usuario.id")),
        sa.Column("fechado_em", TS), sa.Column("enviado_em", TS), sa.Column("recebido_em", TS),
        sa.Column("origem_ref", JSON),
        sa.CheckConstraint(_in("situacao", ("ABERTO", "FECHADO", "ENVIADO", "RECEBIDO_PARCIAL", "RECEBIDO")),
                           name="ck_cop_situacao"),
    )
    op.create_table(
        "cop_item",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("cop_id", sa.Integer, sa.ForeignKey("cop.id"), nullable=False, index=True),
        sa.Column("liberacao_id", sa.Integer, sa.ForeignKey("liberacao_corte.id"), nullable=False, unique=True),
        sa.Column("nf_id", sa.Integer, sa.ForeignKey("nf_transferencia.id"), index=True),
        sa.Column("situacao", sa.String(15), nullable=False, server_default="EM_COP"),
        sa.Column("peso_conferido_kg", KG),
        sa.Column("recebido_em", TS),
        sa.Column("recebido_por_id", sa.Integer, sa.ForeignKey("usuario.id")),
        sa.Column("lote_itu_id", sa.Integer, sa.ForeignKey("lote.id")),
        sa.Column("confirmacoes", JSON),
        sa.CheckConstraint(_in("situacao", ("EM_COP", "EM_TRANSITO", "RECEBIDO")), name="ck_copitem_situacao"),
    )
    op.create_table(
        "divergencia_recebimento",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("cop_item_id", sa.Integer, sa.ForeignKey("cop_item.id"), nullable=False, index=True),
        sa.Column("tipo", sa.String(20), nullable=False),
        sa.Column("pecas", sa.Integer),
        sa.Column("kg", KG),
        sa.Column("observacao", sa.String(1000), nullable=False),
        sa.Column("usuario_id", sa.Integer, sa.ForeignKey("usuario.id")),
        sa.Column("criado_em", TS, nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(_in("tipo", ("FALTANDO", "DANIFICADO", "PESO_DIFERENTE")), name="ck_div_tipo"),
    )
    op.create_table(
        "corte_itu",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("op", sa.Integer, nullable=False, index=True),
        sa.Column("item_codigo", sa.Integer),
        sa.Column("cliente", sa.String(160)),
        sa.Column("lote_id", sa.Integer, sa.ForeignKey("lote.id"), nullable=False, index=True),
        sa.Column("solicitacao_id", sa.Integer, sa.ForeignKey("solicitacao_corte.id"), index=True),
        sa.Column("pecas", sa.Integer),
        sa.Column("peso_usado_kg", KG, nullable=False),
        sa.Column("consumo_kg", KG, nullable=False),
        sa.Column("sobra_kg", KG, nullable=False, server_default="0"),
        sa.Column("sobra_na_bitola", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("perda_kg", KG, nullable=False, server_default="0"),
        sa.Column("previsto_kg", KG),
        sa.Column("lote_reto_id", sa.Integer, sa.ForeignKey("lote.id")),
        sa.Column("instrucao_mega", sa.String(500)),
        sa.Column("observacao", sa.String(1000)),
        sa.Column("confirmacoes", JSON),
        sa.Column("data_corte", sa.Date, nullable=False),
        sa.Column("usuario_id", sa.Integer, sa.ForeignKey("usuario.id")),
        sa.Column("criado_em", TS, nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "cadastro_sa",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("origem", sa.String(10), nullable=False),
        sa.Column("cop_item_id", sa.Integer, sa.ForeignKey("cop_item.id"), unique=True),
        sa.Column("corte_itu_id", sa.Integer, sa.ForeignKey("corte_itu.id"), index=True),
        sa.Column("solicitacao_id", sa.Integer, sa.ForeignKey("solicitacao_corte.id"), index=True),
        sa.Column("lote_id", sa.Integer, sa.ForeignKey("lote.id"), index=True),
        sa.Column("data", sa.Date, nullable=False),
        sa.Column("op", sa.Integer, index=True),
        sa.Column("item_codigo", sa.Integer, index=True),
        sa.Column("item_descricao", sa.String(200)),
        sa.Column("cliente", sa.String(160)),
        sa.Column("pedido", sa.String(40)),
        sa.Column("material", sa.String(60)),
        sa.Column("dimensao", sa.String(60)),
        sa.Column("conteiner", sa.String(30)),
        sa.Column("quantidade", sa.Integer),
        sa.Column("peso_kg", KG),
        sa.Column("rs_kg", KG),
        sa.Column("sa_codigo", sa.Integer, index=True),
        sa.Column("sa_codigo_sugerido", sa.Integer),
        sa.Column("sa_novo", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("sa_descricao", sa.String(200)),
        sa.Column("ncm", sa.String(15)), sa.Column("icms", sa.String(10)), sa.Column("ipi", sa.String(10)),
        sa.Column("nf_id", sa.Integer, sa.ForeignKey("nf_transferencia.id"), index=True),
        sa.Column("situacao", sa.String(20), nullable=False, server_default="PENDENTE", index=True),
        sa.Column("preparado_em", TS), sa.Column("informado_em", TS), sa.Column("confirmado_em", TS),
        sa.Column("verificado_mega_em", TS), sa.Column("exportado_renato_em", TS),
        sa.Column("alterado_apos_exportar", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("confirmacoes", JSON),
        sa.Column("dados_extra", JSON),
        sa.Column("criado_em", TS, nullable=False, server_default=sa.func.now()),
        sa.Column("origem_ref", JSON),
        sa.CheckConstraint(_in("situacao", ("PENDENTE", "PREPARADO", "AGUARDANDO_MEGA", "CONFIRMADO")),
                           name="ck_sa_situacao"),
        sa.CheckConstraint(_in("origem", ("COP", "CORTE_ITU", "CARGA")), name="ck_sa_origem"),
    )
    op.create_table(
        "entrada_nf",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("numero", sa.String(20), nullable=False),
        sa.Column("fornecedor", sa.String(120), nullable=False),
        sa.Column("data", sa.Date, nullable=False),
        sa.Column("conteiner_id", sa.Integer, sa.ForeignKey("conteiner.id"), nullable=False, index=True),
        sa.Column("usuario_id", sa.Integer, sa.ForeignKey("usuario.id")),
        sa.Column("criado_em", TS, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("numero", "fornecedor", name="uq_entrada_nf"),
    )
    op.create_table(
        "entrada_nf_item",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("entrada_id", sa.Integer, sa.ForeignKey("entrada_nf.id"), nullable=False, index=True),
        sa.Column("lote_id", sa.Integer, sa.ForeignKey("lote.id"), nullable=False, unique=True),
        sa.Column("descricao_nf", sa.String(200)),
        sa.Column("pecas", sa.Integer),
        sa.Column("peso_kg", KG, nullable=False),
        sa.Column("comprimento", sa.String(40)),
        sa.Column("custo_kg", KG),
    )

    # movimento: ligações com o fluxo (a tabela é somente-inclusão; ADD COLUMN não dispara o trigger)
    with op.batch_alter_table("movimento") as b:
        b.add_column(sa.Column("solicitacao_id", sa.Integer, sa.ForeignKey("solicitacao_corte.id",
                                                                            name="fk_mov_solicitacao")))
        b.add_column(sa.Column("liberacao_id", sa.Integer, sa.ForeignKey("liberacao_corte.id",
                                                                          name="fk_mov_liberacao")))
        b.add_column(sa.Column("corte_itu_id", sa.Integer, sa.ForeignKey("corte_itu.id", name="fk_mov_corte_itu")))
        b.add_column(sa.Column("origem_ref", JSON))
    op.create_index("ix_movimento_solicitacao_id", "movimento", ["solicitacao_id"])
    op.create_index("ix_movimento_liberacao_id", "movimento", ["liberacao_id"])
    op.create_index("ix_movimento_corte_itu_id", "movimento", ["corte_itu_id"])

    # ---- apoio ----
    parametro = op.create_table(
        "parametro",
        sa.Column("chave", sa.String(40), primary_key=True),
        sa.Column("valor", sa.String(200), nullable=False),
        sa.Column("tipo", sa.String(10), nullable=False, server_default="NUMERO"),
        sa.Column("descricao", sa.String(200), nullable=False),
        sa.Column("atualizado_em", TS, nullable=False, server_default=sa.func.now()),
        sa.Column("atualizado_por_id", sa.Integer, sa.ForeignKey("usuario.id")),
    )
    op.create_table(
        "notificacao",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("usuario_id", sa.Integer, sa.ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False,
                  index=True),
        sa.Column("tipo", sa.String(40), nullable=False, index=True),
        sa.Column("texto", sa.String(500), nullable=False),
        sa.Column("link", sa.String(200)),
        sa.Column("criado_em", TS, nullable=False, server_default=sa.func.now(), index=True),
        sa.Column("lida_em", TS),
    )
    op.create_table(
        "sync_mega",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tipo", sa.String(15), nullable=False),
        sa.Column("gatilho", sa.String(15), nullable=False),
        sa.Column("iniciado_em", TS, nullable=False, server_default=sa.func.now(), index=True),
        sa.Column("terminado_em", TS),
        sa.Column("situacao", sa.String(10), nullable=False, server_default="RODANDO"),
        sa.Column("ultimo_lancamento", sa.BigInteger),
        sa.Column("detalhes", JSON),
        sa.Column("usuario_id", sa.Integer, sa.ForeignKey("usuario.id")),
    )
    op.create_table(
        "mega_saldo",
        sa.Column("codigo", sa.Integer, primary_key=True, autoincrement=False),
        sa.Column("descricao", sa.String(200)),
        sa.Column("saldo_kg", KG, nullable=False),
        sa.Column("preco_medio", KG),
        sa.Column("atualizado_em", TS, nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "mega_movimento",
        sa.Column("lancamento", sa.BigInteger, primary_key=True, autoincrement=False),
        sa.Column("codigo", sa.Integer, nullable=False, index=True),
        sa.Column("data", sa.Date, nullable=False, index=True),
        sa.Column("entrada_saida", sa.String(2), nullable=False),
        sa.Column("tpm", sa.Integer, nullable=False),
        sa.Column("tpm_descricao", sa.String(80)),
        sa.Column("documento", sa.String(40), index=True),
        sa.Column("kg", KG, nullable=False),
        sa.Column("codigo_destino", sa.Integer),
        sa.Column("estorno", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "pendencia_mega",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tipo", sa.String(12), nullable=False),
        sa.Column("codigo", sa.Integer, nullable=False, index=True),
        sa.Column("kg", KG, nullable=False),
        sa.Column("situacao", sa.String(12), nullable=False, server_default="ABERTA", index=True),
        sa.Column("nota", sa.String(1000)),
        sa.Column("lote_id", sa.Integer, sa.ForeignKey("lote.id")),
        sa.Column("criado_em", TS, nullable=False, server_default=sa.func.now()),
        sa.Column("resolvido_em", TS),
        sa.Column("resolvido_por_id", sa.Integer, sa.ForeignKey("usuario.id")),
        sa.CheckConstraint("tipo IN ('ENTRADA','DIVERGENCIA')", name="ck_pend_tipo"),
    )
    op.create_table(
        "liga_equivalente",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("liga_a_id", sa.Integer, sa.ForeignKey("liga.id"), nullable=False),
        sa.Column("liga_b_id", sa.Integer, sa.ForeignKey("liga.id"), nullable=False),
        sa.Column("observacao", sa.String(200)),
        sa.UniqueConstraint("liga_a_id", "liga_b_id", name="uq_liga_equiv"),
        sa.CheckConstraint("liga_a_id <> liga_b_id", name="ck_liga_equiv_diferente"),
    )
    op.create_table(
        "paridade_rj",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("descricao_rj", sa.String(200), nullable=False, unique=True),
        sa.Column("item_mp_id", sa.Integer, sa.ForeignKey("item_mp.id"), index=True),
        sa.Column("confirmada", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("confirmada_por_id", sa.Integer, sa.ForeignKey("usuario.id")),
        sa.Column("confirmada_em", TS),
    )
    op.create_table(
        "pedido_a_chegar",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("item_mp_id", sa.Integer, sa.ForeignKey("item_mp.id"), index=True),
        sa.Column("descricao", sa.String(200)),
        sa.Column("fornecedor", sa.String(120)),
        sa.Column("kg", KG),
        sa.Column("previsao", sa.Date),
        sa.Column("situacao", sa.String(10), nullable=False, server_default="PEDIDO"),
        sa.Column("observacao", sa.String(1000)),
        sa.Column("criado_por_id", sa.Integer, sa.ForeignKey("usuario.id")),
        sa.Column("criado_em", TS, nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("situacao IN ('PEDIDO','EMBARCADO','CHEGOU','CANCELADO')", name="ck_pedido_situacao"),
    )

    # ---- dados iniciais ----
    op.bulk_insert(parametro, [{"chave": c, "valor": v, "tipo": t, "descricao": d} for c, v, t, d in PARAMETROS])
    con = op.get_bind()
    liga = sa.table("liga", sa.column("id", sa.Integer), sa.column("codigo", sa.String),
                    sa.column("nome", sa.String), sa.column("densidade", sa.Numeric),
                    sa.column("apelidos", JSON), sa.column("ativo", sa.Boolean))
    existentes = {c for (c,) in con.execute(sa.select(liga.c.codigo))}
    novas = [{"codigo": c, "nome": n, "densidade": d, "apelidos": [], "ativo": True}
             for c, n, d in LIGAS_NOVAS if c not in existentes]
    if novas:
        op.bulk_insert(liga, novas)
    ids = {c: i for i, c in con.execute(sa.select(liga.c.id, liga.c.codigo))}
    equiv = sa.table("liga_equivalente", sa.column("liga_a_id", sa.Integer), sa.column("liga_b_id", sa.Integer),
                     sa.column("observacao", sa.String))
    op.bulk_insert(equiv, [{"liga_a_id": ids[a], "liga_b_id": ids[b], "observacao": "Especificação v3 [P18]"}
                           for a, b in EQUIVALENCIAS if a in ids and b in ids])


def downgrade() -> None:
    for t in ("pedido_a_chegar", "paridade_rj", "liga_equivalente", "pendencia_mega", "mega_movimento", "mega_saldo",
              "sync_mega", "notificacao", "parametro"):
        op.drop_table(t)
    op.drop_index("ix_movimento_corte_itu_id", "movimento")
    op.drop_index("ix_movimento_liberacao_id", "movimento")
    op.drop_index("ix_movimento_solicitacao_id", "movimento")
    with op.batch_alter_table("movimento") as b:
        for c in ("origem_ref", "corte_itu_id", "liberacao_id", "solicitacao_id"):
            b.drop_column(c)
    for t in ("entrada_nf_item", "entrada_nf", "cadastro_sa", "corte_itu", "divergencia_recebimento", "cop_item",
              "cop", "nf_transferencia", "liberacao_corte", "solicitacao_corte", "ordem_producao"):
        op.drop_table(t)
    with op.batch_alter_table("lote") as b:
        b.drop_column("origem_ref")
    with op.batch_alter_table("item_mp") as b:
        b.drop_column("substituido_por_id")
    op.execute("DELETE FROM liga WHERE codigo IN ('1.2344','1.2379') AND id NOT IN (SELECT item_mp.liga_id FROM item_mp)")
