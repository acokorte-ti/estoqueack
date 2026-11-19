"""Prazo da pendência do peso real da peça inteira do RJ: 7 → 14 dias (Eduardo, 2026-11-19, pendências item 1:
"toda solicitação demora no mínimo uma semana para vir do RJ; depois, até uma semana para cortar").

Só muda o valor se ainda estiver no padrão antigo (7): se alguém já mudou na T23, fica como está.

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-19
"""
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE parametro SET valor = '14' WHERE chave = 'PENDENCIA_PESO_REAL_DIAS' AND valor = '7'")


def downgrade() -> None:
    op.execute("UPDATE parametro SET valor = '7' WHERE chave = 'PENDENCIA_PESO_REAL_DIAS' AND valor = '14'")
