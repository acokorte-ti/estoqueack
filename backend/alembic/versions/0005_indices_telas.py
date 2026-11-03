"""Parte B (chat BANCO E TESTES, 2026-11-03): índices das consultas das telas e precisão do preço médio.

- movimento (lote_id, criado_em): T05 movimentos do lote com saldo acumulado, conciliação por lote.
- lote (status): T04 consulta de estoque e lotes compatíveis (só ATIVO).
- solicitacao_corte (situacao, prazo): T09 fila RJ e T08 por situação, ordenadas por prazo.
- solicitacao_corte (lote_id, situacao): reserva por lote (Enviadas/Parciais) em toda prévia de corte e na T04.
- cadastro_sa (item_codigo, situacao, data): sugestão do código de SA pelo histórico do item (T14).
- notificacao (usuario_id, lida_em): contador do sino a cada 60 s.
- mega_saldo.preco_medio: Numeric(14,3) → Numeric(14,6) (R$/kg; 3 casas arredondavam 7,939533 para 7,940).

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-03
"""
import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

INDICES = [
    ("ix_movimento_lote_criado", "movimento", ["lote_id", "criado_em"]),
    ("ix_lote_status", "lote", ["status"]),
    ("ix_sol_situacao_prazo", "solicitacao_corte", ["situacao", "prazo"]),
    ("ix_sol_lote_situacao", "solicitacao_corte", ["lote_id", "situacao"]),
    ("ix_sa_item_situacao_data", "cadastro_sa", ["item_codigo", "situacao", "data"]),
    ("ix_notificacao_usuario_lida", "notificacao", ["usuario_id", "lida_em"]),
]


def upgrade() -> None:
    for nome, tabela, colunas in INDICES:
        op.create_index(nome, tabela, colunas)
    with op.batch_alter_table("mega_saldo") as b:
        b.alter_column("preco_medio", type_=sa.Numeric(14, 6), existing_type=sa.Numeric(14, 3))


def downgrade() -> None:
    with op.batch_alter_table("mega_saldo") as b:
        b.alter_column("preco_medio", type_=sa.Numeric(14, 3), existing_type=sa.Numeric(14, 6))
    for nome, tabela, _ in reversed(INDICES):
        op.drop_index(nome, tabela)
