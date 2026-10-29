"""2ª rodada do mapeamento (leve): lista tabelas dos módulos EST_/MAN_/ADM_ e descreve objetos-chave.
Somente leitura; amostra de 2 linhas por objeto. Uso dentro do container estoqueack-mapeamento:
    python descrever_mega.py /work/.mega_ro > relatorio.md
"""
import os
import sys

import oracledb

if os.environ.get("ORACLE_IC"):
    oracledb.init_oracle_client(lib_dir=os.environ["ORACLE_IC"])
dsn, usuario, senha = [l.strip() for l in open(sys.argv[1], encoding="utf-8-sig").read().splitlines()[:3]]
con = oracledb.connect(user=usuario, password=senha, dsn=dsn)
con.call_timeout = 120_000
cur = con.cursor()
cur.execute("SET TRANSACTION READ ONLY")
ESQ = "ACOKORTE"

OBJETOS = ["EST_VW_MOVIMENTOESTOQUE", "EST_VW_MOVESTOQUE", "EST_VW_SALDOQTDE", "EST_VW_FICHAINVENTARIO",
           "DW_ADM_PRODUTOS", "DW_MAN_MOVTOMANUF", "DW_MAN_ORDEMSUBPROD", "MAN_VW_OP_LINHAPROG",
           "DWMV_ADM_SALDOESTOQUEVALOR", "ADM_VW_PRODALMOXLOCAL"]


def md(cols, linhas):
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for l in linhas:
        out.append("| " + " | ".join("" if v is None else str(v).replace("|", "/").replace("\n", " ")[:40]
                                     for v in l) + " |")
    return "\n".join(out)


print("# Mapeamento do Mega — 2ª rodada\n")
print("## Tabelas dos módulos de estoque/manufatura/produto (por nº de linhas)\n")
cur.execute(f"""SELECT table_name, num_rows FROM all_tables WHERE owner=:e AND (
                  table_name LIKE 'EST\\_%' ESCAPE '\\' OR table_name LIKE 'MAN\\_%' ESCAPE '\\'
                  OR (table_name LIKE 'ADM\\_%' ESCAPE '\\' AND (table_name LIKE '%PROD%' OR table_name LIKE '%ITEM%')))
                ORDER BY num_rows DESC NULLS LAST FETCH FIRST 120 ROWS ONLY""", e=ESQ)
print(md(["TABELA", "LINHAS"], cur.fetchall()), "\n")

for obj in OBJETOS:
    print(f"## {obj}\n")
    try:
        cur.execute("""SELECT column_name, data_type, data_length FROM all_tab_columns
                       WHERE owner=:e AND table_name=:t ORDER BY column_id""", e=ESQ, t=obj)
        cols = cur.fetchall()
        print("Colunas:", ", ".join(f"{c}({t[:3]})" for c, t, _ in cols), "\n")
        cur.execute(f'SELECT * FROM "{ESQ}"."{obj}" WHERE ROWNUM <= 2')
        print(md([d[0] for d in cur.description][:30], [r[:30] for r in cur.fetchall()]), "\n")
    except Exception as ex:  # noqa: BLE001
        print("ERRO:", str(ex).splitlines()[0], "\n")
con.rollback()
con.close()
