"""Spec v3.5 (R045) e revisão da 0007 (R044).

- solicitacao_corte.consumo_misto e corte_itu.consumo_misto: "OP com consumo misto" Itu + RJ (P26, opção A,
  decisão do Eduardo de 2026-11-11). As duas partes ficam ligadas pela OP.
- Parâmetros novos da T23: TOLERANCIA_EXCESSO_RJ_INTEIRO_PCT = 8 (P22(a): peça inteira vinda do RJ e lote RJ em
  Itu na T13) e SA_JANELA_ANTES_DIAS = 7 (P24: janela da confirmação do SA no Mega).
- pendencia_mega (R044): índice único parcial em `codigo` para ENTRADA ABERTA (duas sincronizações ao mesmo
  tempo não duplicam a pendência) e CHECK em `situacao` e `motivo`. Se já houver duplicada, a mais antiga fica
  ABERTA e as outras passam a ENCERRADA antes de criar o índice.

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-11
"""
import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

PARAM = sa.table("parametro", sa.column("chave", sa.String), sa.column("valor", sa.String),
                 sa.column("tipo", sa.String), sa.column("descricao", sa.String))
NOVOS = [
    {"chave": "TOLERANCIA_EXCESSO_RJ_INTEIRO_PCT", "valor": "8", "tipo": "NUMERO",
     "descricao": "Tolerância de pesagem do material inteiro do RJ (peça inteira e lote RJ em Itu, T13) (%)"},
    {"chave": "SA_JANELA_ANTES_DIAS", "valor": "7", "tipo": "NUMERO",
     "descricao": "Janela do SA no Mega: entradas a partir de N dias antes da data do SA"},
]
SITUACOES = "situacao IN ('ABERTA','RESOLVIDA','DESCARTADA','ENCERRADA')"
MOTIVOS = ("motivo IS NULL OR motivo IN ('ESTORNO_BAIXA_MEGA','ACERTO_INVENTARIO_MEGA','TRANSFERENCIA_CODIGOS',"
           "'OUTRO')")
ONDE = "tipo = 'ENTRADA' AND situacao = 'ABERTA'"


def upgrade() -> None:
    with op.batch_alter_table("solicitacao_corte") as b:
        b.add_column(sa.Column("consumo_misto", sa.Boolean, nullable=False, server_default=sa.false()))
    with op.batch_alter_table("corte_itu") as b:
        b.add_column(sa.Column("consumo_misto", sa.Boolean, nullable=False, server_default=sa.false()))
    op.execute(PARAM.delete().where(PARAM.c.chave.in_([p["chave"] for p in NOVOS])))
    op.bulk_insert(PARAM, NOVOS)
    op.execute("UPDATE pendencia_mega SET situacao = 'ENCERRADA' WHERE tipo = 'ENTRADA' AND situacao = 'ABERTA' "
               "AND id NOT IN (SELECT MIN(id) FROM pendencia_mega WHERE tipo = 'ENTRADA' AND situacao = 'ABERTA' "
               "GROUP BY codigo)")
    with op.batch_alter_table("pendencia_mega") as b:
        b.create_check_constraint("ck_pend_situacao", SITUACOES)
        b.create_check_constraint("ck_pend_motivo", MOTIVOS)
    op.create_index("uq_pend_entrada_aberta", "pendencia_mega", ["codigo"], unique=True,
                    postgresql_where=sa.text(ONDE), sqlite_where=sa.text(ONDE))


def downgrade() -> None:
    op.drop_index("uq_pend_entrada_aberta", table_name="pendencia_mega")
    with op.batch_alter_table("pendencia_mega") as b:
        b.drop_constraint("ck_pend_motivo", type_="check")
        b.drop_constraint("ck_pend_situacao", type_="check")
    op.execute(PARAM.delete().where(PARAM.c.chave.in_([p["chave"] for p in NOVOS])))
    with op.batch_alter_table("corte_itu") as b:
        b.drop_column("consumo_misto")
    with op.batch_alter_table("solicitacao_corte") as b:
        b.drop_column("consumo_misto")
