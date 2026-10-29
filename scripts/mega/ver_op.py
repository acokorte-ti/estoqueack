"""Mostra os campos preenchidos da OP em PRO_ORDENS e as requisições de MP dela. Uso: python ver_op.py .mega_ro 100508"""
import os
import sys

import oracledb

if os.environ.get("ORACLE_IC"):
    oracledb.init_oracle_client(lib_dir=os.environ["ORACLE_IC"])
dsn, usuario, senha = [l.strip() for l in open(sys.argv[1], encoding="utf-8-sig").read().splitlines()[:3]]
op = int(sys.argv[2])
con = oracledb.connect(user=usuario, password=senha, dsn=dsn)
con.call_timeout = 60_000
cur = con.cursor()
cur.execute("SET TRANSACTION READ ONLY")
E = "ACOKORTE"
cur.execute(f'SELECT * FROM "{E}".PRO_ORDENS WHERE ORD_IN_CODIGO = :o AND FIL_IN_CODIGO = 3', o=op)
cols = [d[0] for d in cur.description]
for r in cur.fetchall():
    print(f"## PRO_ORDENS OP {op}\n")
    for c, v in zip(cols, r):
        if v not in (None, "", 0, "N"):
            print(f"- {c} = {str(v)[:80]}")
cur.execute(f"""SELECT m.MVT_DT_MOVIMENTO, m.TPM_ST_DESCRICAO, m.PRO_IN_CODIGO, m.PRO_ST_DESCRICAO, m.MVT_RE_QUANTIDADE
                FROM "{E}".EST_VW_MOVIMENTOESTOQUE m WHERE m.FIL_IN_CODIGO = 3 AND m.MVT_ST_NUMDOC = :d
                AND m.MVT_DT_MOVIMENTO >= DATE '2026-01-01'""", d=str(op))
print(f"\n## Movimentos de estoque com documento {op}\n")
for r in cur.fetchall():
    print("-", " | ".join(str(x) for x in r))
con.rollback()
con.close()
