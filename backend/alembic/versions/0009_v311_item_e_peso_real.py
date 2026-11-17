"""Spec v3.11 (decisões de 2026-11-17; R058): restrição no item, paridade manual e pendência do peso real.

- item_mp.restricao_uso: texto da restrição do material (B09 da P33, ex.: "não usar para guilhotinas"). A carga grava
  no item do RJ a observação das colunas RJ do Estoque Geral, também quando o item ainda não tem lote; todo lote novo
  do item (T06, T13, recebimento, T15) ganha essa restrição (destinação RESTRICAO, "estou ciente" na baixa).
- item_mp.paridade_item_id: "paridade manual" (§1.4 item 8, §10.9 B; P34(a)): o item do RJ (sem código, com a
  própria medida) fica na MESMA LINHA do item de Itu indicado (T04, T07), só porque o usuário confirmou que é o
  mesmo material. Não dá código do Mega ao lote RJ.
- solicitacao_corte.peso_real_encerrada_em / _por_id / peso_real_justificativa: "Encerrar pendência" do peso real
  da peça inteira do RJ (§2.2 passo 7, [proposta, P33(e)]).
- Parâmetro novo da T23: PENDENCIA_PESO_REAL_DIAS = 7 (bloqueio PESO_REAL_PENDENTE na T07, §9).

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-17
"""
import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

PARAM = sa.table("parametro", sa.column("chave", sa.String), sa.column("valor", sa.String),
                 sa.column("tipo", sa.String), sa.column("descricao", sa.String))
NOVOS = [
    {"chave": "PENDENCIA_PESO_REAL_DIAS", "valor": "7", "tipo": "NUMERO",
     "descricao": "Peça inteira do RJ sem peso real: dias desde o recebimento do COP até bloquear novas solicitações"},
]


def upgrade() -> None:
    with op.batch_alter_table("item_mp") as b:
        b.add_column(sa.Column("restricao_uso", sa.String(300), nullable=True))
        b.add_column(sa.Column("paridade_item_id", sa.Integer, nullable=True))
        b.create_foreign_key("fk_item_mp_paridade_item", "item_mp", ["paridade_item_id"], ["id"])
    with op.batch_alter_table("solicitacao_corte") as b:
        b.add_column(sa.Column("peso_real_encerrada_em", sa.DateTime(timezone=True), nullable=True))
        b.add_column(sa.Column("peso_real_encerrada_por_id", sa.Integer, nullable=True))
        b.add_column(sa.Column("peso_real_justificativa", sa.String(500), nullable=True))
        b.create_foreign_key("fk_sol_peso_real_encerrada_por", "usuario", ["peso_real_encerrada_por_id"], ["id"])
    op.execute(PARAM.delete().where(PARAM.c.chave.in_([p["chave"] for p in NOVOS])))
    op.bulk_insert(PARAM, NOVOS)


def downgrade() -> None:
    op.execute(PARAM.delete().where(PARAM.c.chave.in_([p["chave"] for p in NOVOS])))
    with op.batch_alter_table("solicitacao_corte") as b:
        b.drop_constraint("fk_sol_peso_real_encerrada_por", type_="foreignkey")
        b.drop_column("peso_real_justificativa")
        b.drop_column("peso_real_encerrada_por_id")
        b.drop_column("peso_real_encerrada_em")
    with op.batch_alter_table("item_mp") as b:
        b.drop_constraint("fk_item_mp_paridade_item", type_="foreignkey")
        b.drop_column("paridade_item_id")
        b.drop_column("restricao_uso")
