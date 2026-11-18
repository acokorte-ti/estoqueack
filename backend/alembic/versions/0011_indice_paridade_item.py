"""Revisão de código de 2026-11-18: índice na chave estrangeira item_mp.paridade_item_id (criada na 0009 sem índice).

Só índice: não muda dado nem regra. A paridade manual (§1.4 item 8) procura o item de Itu pelo item do RJ.

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-18
"""
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_item_mp_paridade_item_id", "item_mp", ["paridade_item_id"])


def downgrade() -> None:
    op.drop_index("ix_item_mp_paridade_item_id", table_name="item_mp")
