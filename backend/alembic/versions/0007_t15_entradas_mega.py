"""T15 mínima (entradas Mega a classificar), spec v3.4.

- pendencia_mega: motivo e justificativa ("Não é entrada" e reabertura), saldo Mega e soma dos lotes da última
  sincronização, atualizado_em. Estados: ABERTA | RESOLVIDA | DESCARTADA | ENCERRADA (cabem em String(12)).
- item_mp.criado_pela_t15: marca "criado pela T15, revisar" para o T22.

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-06
"""
import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("pendencia_mega") as b:
        b.add_column(sa.Column("motivo", sa.String(30)))
        b.add_column(sa.Column("justificativa", sa.String(500)))
        b.add_column(sa.Column("saldo_mega_kg", sa.Numeric(14, 3)))
        b.add_column(sa.Column("soma_lotes_kg", sa.Numeric(14, 3)))
        b.add_column(sa.Column("atualizado_em", sa.DateTime(timezone=True)))
    with op.batch_alter_table("item_mp") as b:
        b.add_column(sa.Column("criado_pela_t15", sa.Boolean, nullable=False, server_default=sa.false()))


def downgrade() -> None:
    with op.batch_alter_table("item_mp") as b:
        b.drop_column("criado_pela_t15")
    with op.batch_alter_table("pendencia_mega") as b:
        for c in ("atualizado_em", "soma_lotes_kg", "saldo_mega_kg", "justificativa", "motivo"):
            b.drop_column(c)
