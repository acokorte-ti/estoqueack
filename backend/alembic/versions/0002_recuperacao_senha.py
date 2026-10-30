"""Recuperação de senha por e-mail (token de uso único).

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-30
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "token_senha",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("usuario_id", sa.Integer, sa.ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False,
                  index=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("criado_em", TS, nullable=False, server_default=sa.func.now()),
        sa.Column("expira_em", TS, nullable=False),
        sa.Column("usado_em", TS),
        sa.Column("ip", sa.String(64)),
    )


def downgrade() -> None:
    op.drop_table("token_senha")
