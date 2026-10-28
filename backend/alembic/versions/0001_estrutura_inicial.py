"""Estrutura inicial: usuários, sessões, auditoria, catálogo, lotes e movimentos.

Revision ID: 0001
Revises:
Create Date: 2026-10-28
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

JSON = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
TS = sa.DateTime(timezone=True)
KG = sa.Numeric(14, 3)
MM = sa.Numeric(10, 2)

# Densidades de referência (g/cm³) — editáveis na Administração. Confirmar com fornecedores.
LIGAS = [
    ("H13", "AISI H13 / DIN 1.2344", 7.80, ["1.2344", "DIN 1.2344"]),
    ("H11", "AISI H11", 7.80, []),
    ("D2", "AISI D2", 7.70, ["AISI-D2"]),
    ("CR12MOV", "Cr12MoV (equiv. D2)", 7.70, ["CR12 MOV", "Cr12MoV"]),
    ("D6", "AISI D6", 7.70, ["AISI-D6"]),
    ("A8", "AISI A8", 7.85, []),
    ("A8MOD", "AISI A8 modificado", 7.85, ["A8 MOD"]),
    ("CR8", "Cr8 / Cr8Mod", 7.75, ["CR8MOD"]),
    ("DC53", "DC53", 7.87, ["DC53-C", "DC53C"]),
    ("O1", "AISI O1", 7.85, ["AISI-O1"]),
    ("S5", "AISI S5", 7.76, []),
    ("4140", "SAE 4140", 7.85, []),
    ("1.2746", "DIN 1.2746 (45NiCrMoV16-6)", 7.85, ["12746", "DIN 1.2746"]),
    ("1.2767", "DIN 1.2767 (45NiCrMo16)", 7.85, ["12767", "DIN 1.2767"]),
    ("1.2360", "DIN 1.2360", 7.75, ["12360"]),
]


def upgrade() -> None:
    op.create_table(
        "usuario",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("login", sa.String(60), nullable=False, unique=True, index=True),
        sa.Column("nome", sa.String(120), nullable=False),
        sa.Column("email", sa.String(160)),
        sa.Column("perfil", sa.String(20), nullable=False),
        sa.Column("planta", sa.String(3), nullable=False, server_default="ITU"),
        sa.Column("senha_hash", sa.String(255), nullable=False),
        sa.Column("trocar_senha", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("ativo", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("tentativas_falhas", sa.Integer, nullable=False, server_default="0"),
        sa.Column("bloqueado_ate", TS),
        sa.Column("ultimo_login", TS),
        sa.Column("criado_em", TS, nullable=False, server_default=sa.func.now()),
        sa.Column("atualizado_em", TS, nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("perfil IN ('ADMIN','ESTOQUE','OPERACAO_RJ','ANALISE')", name="ck_usuario_perfil"),
        sa.CheckConstraint("planta IN ('ITU','RJ')", name="ck_usuario_planta"),
    )
    op.create_table(
        "sessao",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("csrf", sa.String(64), nullable=False),
        sa.Column("usuario_id", sa.Integer, sa.ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("criada_em", TS, nullable=False, server_default=sa.func.now()),
        sa.Column("expira_em", TS, nullable=False),
        sa.Column("revogada", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("ip", sa.String(64)),
        sa.Column("user_agent", sa.String(300)),
    )
    op.create_table(
        "auditoria",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("quando", TS, nullable=False, server_default=sa.func.now(), index=True),
        sa.Column("usuario_id", sa.Integer, sa.ForeignKey("usuario.id"), index=True),
        sa.Column("acao", sa.String(60), nullable=False, index=True),
        sa.Column("entidade", sa.String(40)),
        sa.Column("entidade_id", sa.String(40)),
        sa.Column("antes", JSON),
        sa.Column("depois", JSON),
        sa.Column("ip", sa.String(64)),
    )
    liga = op.create_table(
        "liga",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("codigo", sa.String(30), nullable=False, unique=True, index=True),
        sa.Column("nome", sa.String(120), nullable=False),
        sa.Column("apelidos", JSON, nullable=False),
        sa.Column("densidade", sa.Numeric(5, 3), nullable=False, server_default="7.85"),
        sa.Column("ativo", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.CheckConstraint("densidade > 6 AND densidade < 10", name="ck_liga_densidade"),
    )
    op.create_table(
        "item_mp",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("codigo_mega", sa.Integer, unique=True, index=True),
        sa.Column("descricao", sa.String(200), nullable=False),
        sa.Column("liga_id", sa.Integer, sa.ForeignKey("liga.id"), nullable=False, index=True),
        sa.Column("formato", sa.String(15), nullable=False),
        sa.Column("espessura", MM),
        sa.Column("largura", MM),
        sa.Column("diametro", MM),
        sa.Column("comprimento_fixado", sa.String(120)),
        sa.Column("um", sa.String(5), nullable=False, server_default="KG"),
        sa.Column("observacao_uso", sa.String(500)),
        sa.Column("ativo", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.CheckConstraint("formato IN ('RETANGULAR','REDONDO','RETO')", name="ck_item_formato"),
    )
    op.create_table(
        "conteiner",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("codigo", sa.String(30), nullable=False, unique=True, index=True),
        sa.Column("data_entrada", sa.Date),
        sa.Column("observacao", sa.String(500)),
        sa.Column("criado_em", TS, nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "lote",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("codigo", sa.String(20), nullable=False, unique=True, index=True),
        sa.Column("conteiner_id", sa.Integer, sa.ForeignKey("conteiner.id"), index=True),
        sa.Column("item_mp_id", sa.Integer, sa.ForeignKey("item_mp.id"), nullable=False, index=True),
        sa.Column("planta_fiscal", sa.String(3), nullable=False),
        sa.Column("local_fisico", sa.String(3), nullable=False),
        sa.Column("tipo", sa.String(10), nullable=False, server_default="ORIGINAL"),
        sa.Column("lote_pai_id", sa.Integer, sa.ForeignKey("lote.id"), index=True),
        sa.Column("origem_identificada", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("peso_inicial_kg", KG, nullable=False),
        sa.Column("pecas_iniciais", sa.Integer),
        sa.Column("saldo_kg", KG, nullable=False),
        sa.Column("custo_kg", KG),
        sa.Column("documento_entrada", sa.String(60)),
        sa.Column("status", sa.String(12), nullable=False, server_default="ATIVO"),
        sa.Column("criado_em", TS, nullable=False, server_default=sa.func.now()),
        sa.Column("criado_por_id", sa.Integer, sa.ForeignKey("usuario.id")),
        sa.CheckConstraint("saldo_kg >= 0", name="ck_lote_saldo_nao_negativo"),
        sa.CheckConstraint("planta_fiscal IN ('ITU','RJ')", name="ck_lote_planta"),
        sa.CheckConstraint("local_fisico IN ('ITU','RJ')", name="ck_lote_local"),
        sa.CheckConstraint("tipo IN ('ORIGINAL','SOBRA','RETO')", name="ck_lote_tipo"),
        sa.CheckConstraint("lote_pai_id IS NULL OR lote_pai_id <> id", name="ck_lote_pai_diferente"),
    )
    op.create_index("ix_lote_balde", "lote", ["planta_fiscal", "local_fisico"])
    op.create_table(
        "movimento",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("lote_id", sa.Integer, sa.ForeignKey("lote.id"), nullable=False, index=True),
        sa.Column("tipo", sa.String(20), nullable=False, index=True),
        sa.Column("kg", KG, nullable=False),
        sa.Column("pecas", sa.Integer),
        sa.Column("op", sa.Integer, index=True),
        sa.Column("sa_codigo", sa.Integer, index=True),
        sa.Column("cop_numero", sa.Integer, index=True),
        sa.Column("documento", sa.String(60)),
        sa.Column("data_referencia", sa.Date),
        sa.Column("justificativa", sa.String(500)),
        sa.Column("confirmacoes", JSON),
        sa.Column("estorno_de_id", sa.Integer, sa.ForeignKey("movimento.id")),
        sa.Column("usuario_id", sa.Integer, sa.ForeignKey("usuario.id")),
        sa.Column("criado_em", TS, nullable=False, server_default=sa.func.now(), index=True),
        sa.CheckConstraint("kg <> 0", name="ck_mov_kg_nao_zero"),
    )
    op.create_table(
        "destinacao",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("lote_id", sa.Integer, sa.ForeignKey("lote.id"), nullable=False, index=True),
        sa.Column("tipo", sa.String(10), nullable=False),
        sa.Column("descricao", sa.String(300), nullable=False),
        sa.Column("kg", KG),
        sa.Column("validade", sa.Date),
        sa.Column("ativa", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("criado_por_id", sa.Integer, sa.ForeignKey("usuario.id")),
        sa.Column("criado_em", TS, nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("tipo IN ('RESERVA','RESTRICAO')", name="ck_destinacao_tipo"),
    )
    op.create_table(
        "nota",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("entidade", sa.String(20), nullable=False),
        sa.Column("entidade_id", sa.Integer, nullable=False, index=True),
        sa.Column("texto", sa.String(2000), nullable=False),
        sa.Column("usuario_id", sa.Integer, sa.ForeignKey("usuario.id")),
        sa.Column("criado_em", TS, nullable=False, server_default=sa.func.now()),
    )

    op.bulk_insert(liga, [{"codigo": c, "nome": n, "densidade": d, "apelidos": a, "ativo": True}
                          for c, n, d, a in LIGAS])

    if op.get_bind().dialect.name == "postgresql":
        # Movimentos e auditoria são imutáveis: correção somente por estorno / novo registro.
        op.execute("""
            CREATE OR REPLACE FUNCTION bloquear_alteracao() RETURNS trigger AS $$
            BEGIN
              RAISE EXCEPTION 'Tabela % é somente-inclusão (use estorno).', TG_TABLE_NAME;
            END; $$ LANGUAGE plpgsql;
        """)
        for tabela in ("movimento", "auditoria"):
            op.execute(f"""
                CREATE TRIGGER trg_{tabela}_imutavel BEFORE UPDATE OR DELETE ON {tabela}
                FOR EACH ROW EXECUTE FUNCTION bloquear_alteracao();
            """)


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        for tabela in ("movimento", "auditoria"):
            op.execute(f"DROP TRIGGER IF EXISTS trg_{tabela}_imutavel ON {tabela}")
        op.execute("DROP FUNCTION IF EXISTS bloquear_alteracao()")
    for t in ("nota", "destinacao", "movimento", "lote", "conteiner", "item_mp", "liga", "auditoria", "sessao",
              "usuario"):
        op.drop_table(t)
