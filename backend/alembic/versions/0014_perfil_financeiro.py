"""Perfil Financeiro (Eduardo, 2026-11-23, pendências item 2: "a parte do financeiro, da Bruna"): grava o R$/kg do
precificador no Cadastro de SA e consulta o resto (spec v3.21 §1.2, §4.1).

Só alarga a regra do campo `usuario.perfil`; nenhum dado muda.

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-23
"""
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

COM = "perfil IN ('ADMIN','ESTOQUE','OPERACAO_RJ','ANALISE','FINANCEIRO')"
SEM = "perfil IN ('ADMIN','ESTOQUE','OPERACAO_RJ','ANALISE')"


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.drop_constraint("ck_usuario_perfil", "usuario", type_="check")
        op.create_check_constraint("ck_usuario_perfil", "usuario", COM)


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.drop_constraint("ck_usuario_perfil", "usuario", type_="check")
        op.create_check_constraint("ck_usuario_perfil", "usuario", SEM)
