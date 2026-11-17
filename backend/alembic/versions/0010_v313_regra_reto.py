"""Spec v3.13 (observações do Eduardo de 2026-11-17; R063): regra do RETO na sobra da T13.

- corte_itu.sobra_espessura_mm / sobra_largura_mm: E × L da sobra que não mantém a bitola (placa/blooming), digitados
  pelo operador [proposta, P35(b)]; sobra_diametro_mm: Ø da sobra de redondo que não vai para RETO [P35(d)].
- corte_itu.sobra_destino: RETO | LOTE_NOVO (NULL = sem sobra ou sobra na bitola).
- corte_itu.regra_reto: o que o sistema mostrou e o operador conferiu ("Conferi a regra do RETO"): limites usados,
  texto da regra e do resultado.
- corte_itu.lote_sobra_id: lote novo com a medida da sobra, filho do lote de origem (tipo SOBRA, movimento
  GERA_SOBRA), quando a sobra não passa na regra do RETO [proposta, P35(c)].
- Parâmetros novos da T23: RETO_ESP_LIMITE = 50, RETO_LARG_MAX_ATE_LIMITE = 200, RETO_LARG_MAX_ACIMA = 250 (mm).

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-17
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

JSON = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
PARAM = sa.table("parametro", sa.column("chave", sa.String), sa.column("valor", sa.String),
                 sa.column("tipo", sa.String), sa.column("descricao", sa.String))
NOVOS = [
    {"chave": "RETO_ESP_LIMITE", "valor": "50", "tipo": "NUMERO",
     "descricao": "Regra do RETO (T13): espessura limite da sobra de placa/blooming, em mm"},
    {"chave": "RETO_LARG_MAX_ATE_LIMITE", "valor": "200", "tipo": "NUMERO",
     "descricao": "Regra do RETO (T13): largura da sobra abaixo deste valor (mm) vai para RETO, espessura até o limite"},
    {"chave": "RETO_LARG_MAX_ACIMA", "valor": "250", "tipo": "NUMERO",
     "descricao": "Regra do RETO (T13): largura da sobra abaixo deste valor (mm) vai para RETO, espessura acima do "
                  "limite"},
]


def upgrade() -> None:
    with op.batch_alter_table("corte_itu") as b:
        b.add_column(sa.Column("sobra_espessura_mm", sa.Numeric(10, 2), nullable=True))
        b.add_column(sa.Column("sobra_largura_mm", sa.Numeric(10, 2), nullable=True))
        b.add_column(sa.Column("sobra_diametro_mm", sa.Numeric(10, 2), nullable=True))
        b.add_column(sa.Column("sobra_destino", sa.String(10), nullable=True))
        b.add_column(sa.Column("regra_reto", JSON, nullable=True))
        b.add_column(sa.Column("lote_sobra_id", sa.Integer, nullable=True))
        b.create_foreign_key("fk_corte_itu_lote_sobra", "lote", ["lote_sobra_id"], ["id"])
        b.create_check_constraint("ck_corte_itu_sobra_destino",
                                  "sobra_destino IS NULL OR sobra_destino IN ('RETO','LOTE_NOVO')")
    op.execute(PARAM.delete().where(PARAM.c.chave.in_([p["chave"] for p in NOVOS])))
    op.bulk_insert(PARAM, NOVOS)


def downgrade() -> None:
    op.execute(PARAM.delete().where(PARAM.c.chave.in_([p["chave"] for p in NOVOS])))
    with op.batch_alter_table("corte_itu") as b:
        b.drop_constraint("ck_corte_itu_sobra_destino", type_="check")
        b.drop_constraint("fk_corte_itu_lote_sobra", type_="foreignkey")
        for c in ("lote_sobra_id", "regra_reto", "sobra_destino", "sobra_diametro_mm", "sobra_largura_mm",
                  "sobra_espessura_mm"):
            b.drop_column(c)
