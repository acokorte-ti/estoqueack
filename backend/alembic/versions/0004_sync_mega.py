"""Sincronização com o Mega (chat BANCO E TESTES, 2026-11-03): campos que faltavam para saldo/preço médio e para a
cópia dos movimentos por janela (data de inclusão, alteração e usuário), e índice por código + data.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-03
"""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

KG = sa.Numeric(14, 3)


def upgrade() -> None:
    with op.batch_alter_table("mega_saldo") as b:
        b.add_column(sa.Column("preco_medio_data", sa.Date))
        b.add_column(sa.Column("um", sa.String(8)))
        b.add_column(sa.Column("peso_especifico", KG))
    with op.batch_alter_table("mega_movimento") as b:
        b.add_column(sa.Column("incluido_em", sa.Date))
        b.add_column(sa.Column("alterado_em", sa.DateTime(timezone=True)))
        b.add_column(sa.Column("usuario_mega", sa.Integer))
    op.create_index("ix_mega_movimento_codigo_data", "mega_movimento", ["codigo", "data"])
    op.create_index("ix_sync_mega_tipo_situacao", "sync_mega", ["tipo", "situacao", "iniciado_em"])


def downgrade() -> None:
    op.drop_index("ix_sync_mega_tipo_situacao", "sync_mega")
    op.drop_index("ix_mega_movimento_codigo_data", "mega_movimento")
    with op.batch_alter_table("mega_movimento") as b:
        for c in ("usuario_mega", "alterado_em", "incluido_em"):
            b.drop_column(c)
    with op.batch_alter_table("mega_saldo") as b:
        for c in ("peso_especifico", "um", "preco_medio_data"):
            b.drop_column(c)
