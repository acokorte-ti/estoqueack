"""Spec v3.15 (Eduardo, 2026-11-17; R074–R076): entrada enriquecida e documentos anexos.

- entrada_nf: origem (T06 | T15 | T05), série, data de emissão, CNPJ, chave da NF-e, packing list, DI/DUIMP e
  observação. numero, fornecedor e conteiner_id aceitam vazio (dados da entrada do lote da T15, que pode vir sem NF
  ou sem contêiner, e do lote da carga completado no T05). Sai a chave única (numero, fornecedor): a NF duplicada
  passa a considerar a série e é conferida pelo serviço (NF_DUPLICADA); fica um índice comum para a busca.
- entrada_nf_item: NCM, peso bruto e observação (o R$/kg do precificador é o custo_kg que já existia).
- anexo + anexo_arquivo: NF, packing list, precificador (contêiner) e outro (lote); apagar só esconde. O conteúdo fica
  no banco (bytea) para o backup diário/externo (pg_dump) e a restauração levarem os anexos junto.
- Parâmetro novo da T23: ANEXO_MAX_MB = 10 [proposta, P41(c)].

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-19
"""
import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)
KG = sa.Numeric(14, 3)
PARAM = sa.table("parametro", sa.column("chave", sa.String), sa.column("valor", sa.String),
                 sa.column("tipo", sa.String), sa.column("descricao", sa.String))


def upgrade() -> None:
    with op.batch_alter_table("entrada_nf") as b:
        b.drop_constraint("uq_entrada_nf", type_="unique")
        b.add_column(sa.Column("origem", sa.String(3), nullable=False, server_default="T06"))
        b.add_column(sa.Column("serie", sa.String(5)))
        b.add_column(sa.Column("cnpj", sa.String(14)))
        b.add_column(sa.Column("data_emissao", sa.Date))
        b.add_column(sa.Column("chave_nfe", sa.String(60)))
        b.add_column(sa.Column("packing_list", sa.String(60)))
        b.add_column(sa.Column("di_duimp", sa.String(30)))
        b.add_column(sa.Column("observacao", sa.String(500)))
        b.alter_column("numero", existing_type=sa.String(20), nullable=True)
        b.alter_column("fornecedor", existing_type=sa.String(120), nullable=True)
        b.alter_column("conteiner_id", existing_type=sa.Integer, nullable=True)
        b.create_check_constraint("ck_entrada_nf_origem", "origem IN ('T06','T15','T05')")
    op.create_index("ix_entrada_nf_numero_fornecedor", "entrada_nf", ["numero", "fornecedor"])
    with op.batch_alter_table("entrada_nf_item") as b:
        b.add_column(sa.Column("ncm", sa.String(10)))
        b.add_column(sa.Column("peso_bruto_kg", KG))
        b.add_column(sa.Column("observacao", sa.String(500)))

    op.create_table(
        "anexo",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tipo", sa.String(12), nullable=False),
        sa.Column("descricao", sa.String(120)),
        sa.Column("nome_arquivo", sa.String(200), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("tamanho_bytes", sa.Integer, nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("entrada_id", sa.Integer, sa.ForeignKey("entrada_nf.id"), index=True),
        sa.Column("conteiner_id", sa.Integer, sa.ForeignKey("conteiner.id"), index=True),
        sa.Column("lote_id", sa.Integer, sa.ForeignKey("lote.id"), index=True),
        sa.Column("usuario_id", sa.Integer, sa.ForeignKey("usuario.id")),
        sa.Column("criado_em", TS, nullable=False, server_default=sa.func.now()),
        sa.Column("apagado_em", TS),
        sa.Column("apagado_por_id", sa.Integer, sa.ForeignKey("usuario.id")),
        sa.Column("justificativa_apagar", sa.String(500)),
        sa.CheckConstraint("tipo IN ('NF','PACKING_LIST','PRECIFICADOR','OUTRO')", name="ck_anexo_tipo"),
        sa.CheckConstraint("(CASE WHEN entrada_id IS NULL THEN 0 ELSE 1 END) + (CASE WHEN conteiner_id IS NULL THEN 0 "
                           "ELSE 1 END) + (CASE WHEN lote_id IS NULL THEN 0 ELSE 1 END) = 1", name="ck_anexo_um_alvo"),
    )
    op.create_table(
        "anexo_arquivo",
        sa.Column("anexo_id", sa.Integer, sa.ForeignKey("anexo.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("conteudo", sa.LargeBinary, nullable=False),
    )
    op.bulk_insert(PARAM, [{"chave": "ANEXO_MAX_MB", "valor": "10", "tipo": "NUMERO",
                            "descricao": "Tamanho máximo de cada documento anexo (MB)"}])


def downgrade() -> None:
    op.execute(PARAM.delete().where(PARAM.c.chave == "ANEXO_MAX_MB"))
    op.drop_table("anexo_arquivo")
    op.drop_table("anexo")
    with op.batch_alter_table("entrada_nf_item") as b:
        b.drop_column("observacao")
        b.drop_column("peso_bruto_kg")
        b.drop_column("ncm")
    op.drop_index("ix_entrada_nf_numero_fornecedor", table_name="entrada_nf")
    # volta só se não houver entrada da T15/T05 (sem NF ou sem contêiner) nem NF repetida com outra série
    op.execute("DELETE FROM entrada_nf_item WHERE entrada_id IN (SELECT id FROM entrada_nf WHERE origem <> 'T06')")
    op.execute("DELETE FROM entrada_nf WHERE origem <> 'T06'")
    with op.batch_alter_table("entrada_nf") as b:
        b.drop_constraint("ck_entrada_nf_origem", type_="check")
        b.alter_column("conteiner_id", existing_type=sa.Integer, nullable=False)
        b.alter_column("fornecedor", existing_type=sa.String(120), nullable=False)
        b.alter_column("numero", existing_type=sa.String(20), nullable=False)
        for c in ("observacao", "di_duimp", "packing_list", "chave_nfe", "data_emissao", "cnpj", "serie", "origem"):
            b.drop_column(c)
        b.create_unique_constraint("uq_entrada_nf", ["numero", "fornecedor"])
