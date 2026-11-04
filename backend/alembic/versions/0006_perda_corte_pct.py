"""Perda de corte e densidade das ligas.

Perda de corte: PERDA_CORTE_MAX_PCT = 6 % do material usado (decisão do Eduardo, 2026-11-04, R024; spec v3.3 T13,
§9, T23), no lugar de PERDA_CORTE_MARGEM_PCT (margem de 50 % sobre a perda esperada de serra).

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-04
"""
import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

PARAM = sa.table("parametro", sa.column("chave", sa.String), sa.column("valor", sa.String),
                 sa.column("tipo", sa.String), sa.column("descricao", sa.String))


def upgrade() -> None:
    # densidade de 1 a 25 g/cm³: ligas que não são aço entram na carga (titânio 4,43; metal duro 14,5) — R038
    if op.get_bind().dialect.name == "postgresql":
        op.drop_constraint("ck_liga_densidade", "liga", type_="check")
        op.create_check_constraint("ck_liga_densidade", "liga", "densidade > 1 AND densidade < 25")
    op.execute(PARAM.delete().where(PARAM.c.chave == "PERDA_CORTE_MARGEM_PCT"))
    op.bulk_insert(PARAM, [{"chave": "PERDA_CORTE_MAX_PCT", "valor": "6", "tipo": "NUMERO",
                            "descricao": "Perda de corte máxima normal (% do peso do material usado)"}])


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.drop_constraint("ck_liga_densidade", "liga", type_="check")
        op.create_check_constraint("ck_liga_densidade", "liga", "densidade > 6 AND densidade < 10")
    op.execute(PARAM.delete().where(PARAM.c.chave == "PERDA_CORTE_MAX_PCT"))
    op.bulk_insert(PARAM, [{"chave": "PERDA_CORTE_MARGEM_PCT", "valor": "50", "tipo": "NUMERO",
                            "descricao": "Margem sobre a perda esperada de serra (%)"}])
