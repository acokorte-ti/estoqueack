"""3ª rodada: confirma tabela de OP, cálculo de saldo e bate com o relatório de 20/10/2026. Somente leitura."""
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
E = "ACOKORTE"


def bloco(titulo, sql, **p):
    print(f"\n## {titulo}\n")
    try:
        cur.execute(sql, p)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        print("| " + " | ".join(cols) + " |\n|" + "---|" * len(cols))
        for r in rows[:60]:
            print("| " + " | ".join("" if v is None else str(v).replace("|", "/").replace("\n", " ")[:45] for v in r) + " |")
        if not rows:
            print("_(vazio)_")
    except Exception as ex:  # noqa: BLE001
        print("ERRO:", str(ex).splitlines()[0])


def colunas(tab):
    bloco(f"Colunas de {tab}", "SELECT column_name, data_type FROM all_tab_columns WHERE owner=:e AND table_name=:t "
                               "ORDER BY column_id", e=E, t=tab)


bloco("Tabelas MAN_ (ordens)", """SELECT table_name, num_rows FROM all_tables WHERE owner=:e
      AND table_name LIKE 'MAN\\_%' ESCAPE '\\' ORDER BY num_rows DESC NULLS LAST FETCH FIRST 40 ROWS ONLY""", e=E)
colunas("EST_PRODUTOS")
colunas("EST_SALDOFIN")
# Código 1698 = IMP-H13 RETO. Relatório Mega 20/10 (aba 'estoque atual'/Estoque Geral) = 2240.042 kg na filial 3
bloco("Produto 1698 no cadastro", f'SELECT * FROM "{E}".EST_PRODUTOS WHERE PRO_IN_CODIGO = 1698')
bloco("Movimentos 1698, filial 3, por tipo (soma)",
      f"""SELECT MVT_ST_ENTRSAIDA, TPM_IN_CODIGO, TPM_ST_DESCRICAO, MVT_BO_ESTORNO, COUNT(*) N,
                 ROUND(SUM(MVT_RE_QUANTIDADE),3) KG
          FROM "{E}".EST_VW_MOVIMENTOESTOQUE WHERE PRO_IN_CODIGO = 1698 AND FIL_IN_CODIGO = 3
          GROUP BY MVT_ST_ENTRSAIDA, TPM_IN_CODIGO, TPM_ST_DESCRICAO, MVT_BO_ESTORNO ORDER BY 6 DESC""")
bloco("Últimos 12 movimentos 1698 filial 3",
      f"""SELECT MVT_DT_MOVIMENTO, MVT_ST_ENTRSAIDA, TPM_ST_DESCRICAO, MVT_ST_NUMDOC, MVT_RE_QUANTIDADE,
                 PRO_IN_CODIGODEST, MVT_BO_ESTORNO, MVT_IN_LANCAM
          FROM "{E}".EST_VW_MOVIMENTOESTOQUE WHERE PRO_IN_CODIGO = 1698 AND FIL_IN_CODIGO = 3
          ORDER BY MVT_DT_MOVIMENTO DESC, MVT_IN_LANCAM DESC FETCH FIRST 12 ROWS ONLY""")
bloco("Saldo 1698 em EST_SALDOFIN (últimas linhas)",
      f'SELECT * FROM "{E}".EST_SALDOFIN WHERE PRO_IN_CODIGO = 1698 AND ROWNUM <= 8')
bloco("Valores de MVT_ST_ENTRSAIDA (amostra recente filial 3)",
      f"""SELECT MVT_ST_ENTRSAIDA, COUNT(*) FROM "{E}".EST_VW_MOVIMENTOESTOQUE
          WHERE FIL_IN_CODIGO = 3 AND MVT_DT_MOVIMENTO >= DATE '2026-10-01' GROUP BY MVT_ST_ENTRSAIDA""")
bloco("Movimentos de manufatura ligados à OP 100508",
      f"""SELECT * FROM "{E}".DW_MAN_MOVTOMANUF WHERE ID_ORDEM LIKE '%-100508' AND ROWNUM <= 10""")
con.rollback()
con.close()
