"""4ª rodada: saldo calculado por movimentos x relatório Mega de 20/10/2026 e localização da tabela de OP."""
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
REF = {1698: 2240.042, 87780: 4900, 62622: 5253.79, 78290: 5198, 5838: 631.5, 60064: 2722}

print("## Saldo por movimentos (filial 3) x relatório 20/10\n")
print("| código | até 19/10 | até 20/10 | relatório | dif. 20/10 |\n|---|---|---|---|---|")
for cod, ref in REF.items():
    cur.execute(f"""SELECT
        SUM(CASE WHEN MVT_DT_MOVIMENTO < DATE '2026-10-20' THEN DECODE(MVT_ST_ENTRSAIDA,'ED',1,'SD',-1,0)*MVT_RE_QUANTIDADE END),
        SUM(CASE WHEN MVT_DT_MOVIMENTO < DATE '2026-10-21' THEN DECODE(MVT_ST_ENTRSAIDA,'ED',1,'SD',-1,0)*MVT_RE_QUANTIDADE END)
        FROM "{E}".EST_VW_MOVIMENTOESTOQUE WHERE PRO_IN_CODIGO=:c AND FIL_IN_CODIGO=3""", c=cod)
    a, b = cur.fetchone()
    print(f"| {cod} | {a or 0:.3f} | {b or 0:.3f} | {ref} | {(b or 0) - ref:.3f} |")

print("\n## Tabelas com coluna ORD_IN_CODIGO (candidatas a OP)\n")
cur.execute("""SELECT c.table_name, t.num_rows FROM all_tab_columns c JOIN all_tables t
               ON t.owner=c.owner AND t.table_name=c.table_name
               WHERE c.owner=:e AND c.column_name='ORD_IN_CODIGO' ORDER BY t.num_rows DESC NULLS LAST
               FETCH FIRST 15 ROWS ONLY""", e=E)
cands = cur.fetchall()
print("| tabela | linhas |\n|---|---|")
for t, n in cands:
    print(f"| {t} | {n} |")

for t, _ in cands[:6]:
    print(f"\n### {t}: OP 100508\n")
    try:
        cur.execute(f'SELECT * FROM "{E}"."{t}" WHERE ORD_IN_CODIGO = 100508 AND ROWNUM <= 2')
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        for r in rows:
            print("; ".join(f"{c}={v}" for c, v in zip(cols, r) if v not in (None, "", 0))[:1500], "\n")
        if not rows:
            print("_(não encontrada)_")
    except Exception as ex:  # noqa: BLE001
        print("ERRO:", str(ex).splitlines()[0])
con.rollback()
con.close()
