"""Mapeamento do banco do ERP Mega (Oracle 19c) — SOMENTE LEITURA.

Objetivo (pedido R001): achar as tabelas/colunas reais de produto, saldo por filial,
ordem de produção, SA e MOVIMENTOS de estoque, usando valores conhecidos das planilhas.

Uso (na máquina do Eduardo, que tem rota até o Oracle):
    py -m pip install oracledb
    $env:ORACLE_IC="C:\\Users\\<user>\\oracle\\instantclient_23_0"   # Instant Client (exigido pela criptografia)
    py descobrir_mega.py --credenciais ..\\..\\.mega_ro        (arquivo com 3 linhas: dsn, usuario, senha)

Saída: relatorio_mega_AAAAMMDD_HHMM.md (na pasta atual). NÃO contém dados de clientes além dos
valores de teste abaixo, nem senhas. Toda sessão é READ ONLY e com timeout por consulta.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

# Valores conhecidos nas planilhas (Materia Prima Geral 20out / SA / Controle de Corte)
CODIGOS_MP = [1698, 87780, 62622, 78290]      # IMP-H13 RETO, IMP-A8 5,50X315X4600MM, 1.2746 RETO, H13 24X62MM
SALDOS_ESPERADOS = {1698: 4302.042, 62622: 6931.29, 87780: 4900}   # aba "Quant consider" (09/06) — só referência
OPS = [100508, 100092, 100553]
SA_CODIGOS = [78988, 68946, 91773]
ITENS = [68092, 68646, 2134]
TEXTOS_DESC = ["IMP-H13 RETO", "IMP-A8 5,50X315X4600MM"]

PALAVRAS_TABELA = ["PRODUTO", "PROD", "ITEM", "MATERIAL", "ESTOQUE", "SALDO", "ORDEM", "OP", "PRODUCAO",
                   "MOVIMENTO", "MOV", "KARDEX", "LOTE", "INVENT", "NOTA", "NF", "FILIAL", "EMPRESA"]


def conectar(arq: Path):
    import os

    import oracledb
    if os.environ.get("ORACLE_IC"):  # banco exige Native Network Encryption → modo thick
        oracledb.init_oracle_client(lib_dir=os.environ["ORACLE_IC"])
    dsn, usuario, senha = [l.strip() for l in arq.read_text(encoding="utf-8-sig").splitlines()[:3]]
    con = oracledb.connect(user=usuario, password=senha, dsn=dsn)
    con.call_timeout = 60_000  # ms
    cur = con.cursor()
    cur.execute("SET TRANSACTION READ ONLY")
    return con, cur


def q(cur, sql, **p):
    try:
        cur.execute(sql, p)
        cols = [d[0] for d in cur.description]
        return cols, cur.fetchall()
    except Exception as e:  # noqa: BLE001 — relatório deve continuar
        return ["ERRO"], [(str(e)[:300],)]


def tabela_md(cols, linhas, limite=40):
    if not linhas:
        return "_(nenhum resultado)_\n"
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for l in linhas[:limite]:
        out.append("| " + " | ".join("" if v is None else str(v).replace("|", "/")[:60] for v in l) + " |")
    if len(linhas) > limite:
        out.append(f"\n_… {len(linhas) - limite} linhas omitidas_")
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--credenciais", required=True, type=Path)
    ap.add_argument("--esquema", help="esquema do Mega, se já souber")
    ap.add_argument("--buscar-valores", action="store_true",
                    help="também procura valores conhecidos (faz varreduras; rodar fora do horário de pico)")
    a = ap.parse_args()
    con, cur = conectar(a.credenciais)
    r = [f"# Mapeamento do Mega — {dt.datetime.now():%Y-%m-%d %H:%M}\n"]

    cols, l = q(cur, "SELECT banner FROM v$version")
    r += ["## Versão\n", tabela_md(cols, l)]

    # 1. Esquemas com mais tabelas (o do Mega costuma ser o maior)
    cols, l = q(cur, """SELECT owner, COUNT(*) tabelas FROM all_tables
                        WHERE owner NOT IN ('SYS','SYSTEM','XDB','MDSYS','CTXSYS','ORDSYS','WMSYS','OLAPSYS',
                        'DVSYS','LBACSYS','GSMADMIN_INTERNAL','APPQOSSYS','AUDSYS','DBSNMP','OJVMSYS','ORDDATA')
                        GROUP BY owner ORDER BY 2 DESC FETCH FIRST 15 ROWS ONLY""")
    r += ["## 1. Esquemas\n", tabela_md(cols, l)]
    esquema = a.esquema or (l[0][0] if l and cols[0] != "ERRO" else None)
    r.append(f"\nEsquema analisado: **{esquema}**\n")

    # 2. Tabelas candidatas por nome
    filtro = " OR ".join(f"table_name LIKE '%{p}%'" for p in PALAVRAS_TABELA)
    cols, l = q(cur, f"""SELECT t.table_name, t.num_rows, c.comments FROM all_tables t
                         LEFT JOIN all_tab_comments c ON c.owner=t.owner AND c.table_name=t.table_name
                         WHERE t.owner=:e AND ({filtro}) ORDER BY t.num_rows DESC NULLS LAST""", e=esquema)
    r += ["## 2. Tabelas candidatas (por nome)\n", tabela_md(cols, l, 120)]

    # 3. Colunas numéricas candidatas a código de produto / OP, com busca dos valores conhecidos
    def procurar(valores, rotulo, padroes_coluna):
        filtro_c = " OR ".join(f"column_name LIKE '%{p}%'" for p in padroes_coluna)
        _, colunas = q(cur, f"""SELECT table_name, column_name FROM all_tab_columns
                                WHERE owner=:e AND data_type='NUMBER' AND ({filtro_c})""", e=esquema)
        achados = []
        for tab, col in colunas[:400]:
            _, n = q(cur, f'SELECT COUNT(*) FROM "{esquema}"."{tab}" WHERE "{col}" IN ({",".join(map(str, valores))})')
            if n and isinstance(n[0][0], (int, float)) and n[0][0] > 0:
                achados.append((tab, col, n[0][0]))
        r.extend([f"## {rotulo}\n", tabela_md(["TABELA", "COLUNA", "OCORRENCIAS"], achados, 80)])

    # 2b. Colunas das maiores tabelas candidatas (só dicionário, leve)
    for tab, _n, _c in [x for x in l if cols[0] != "ERRO"][:25]:
        c2, l2 = q(cur, """SELECT column_name, data_type, data_length, comments FROM all_col_comments
                           RIGHT JOIN all_tab_columns USING (owner, table_name, column_name)
                           WHERE owner=:e AND table_name=:t ORDER BY column_id""", e=esquema, t=tab)
        r += [f"### Colunas de {tab}\n", tabela_md(c2, l2, 80)]

    if not a.buscar_valores:
        cols, l = q(cur, f"""SELECT view_name FROM all_views WHERE owner=:e
                             AND ({filtro.replace('table_name', 'view_name')}) ORDER BY 1""", e=esquema)
        r += ["## 7. Visões candidatas\n", tabela_md(cols, l, 120)]
        return _salvar(con, r)

    procurar(CODIGOS_MP, "3. Onde aparecem os códigos de MP (1698, 87780, 62622, 78290)", ["PRO", "ITE", "MAT", "COD"])
    procurar(OPS, "4. Onde aparecem as OPs (100508, 100092, 100553)", ["ORD", "OP", "NUM", "DOC"])
    procurar(SA_CODIGOS, "5. Onde aparecem os SAs (78988, 68946, 91773)", ["PRO", "ITE", "COD"])

    # 6. Descrições conhecidas (tabela de produto)
    _, colunas = q(cur, """SELECT table_name, column_name FROM all_tab_columns
                           WHERE owner=:e AND data_type IN ('VARCHAR2','CHAR') AND column_name LIKE '%DESC%'""",
                   e=esquema)
    achados = []
    for tab, col in colunas[:300]:
        _, n = q(cur, f'SELECT COUNT(*) FROM "{esquema}"."{tab}" WHERE UPPER("{col}") IN (:a, :b)',
                 a=TEXTOS_DESC[0], b=TEXTOS_DESC[1])
        if n and isinstance(n[0][0], (int, float)) and n[0][0] > 0:
            achados.append((tab, col, n[0][0]))
    r += ["## 6. Tabelas com as descrições conhecidas\n", tabela_md(["TABELA", "COLUNA", "OCORRENCIAS"], achados)]

    # 7. Visões (o Mega pode expor saldo/kardex por views)
    cols, l = q(cur, f"""SELECT view_name FROM all_views WHERE owner=:e AND ({filtro.replace('table_name', 'view_name')})
                         ORDER BY 1""", e=esquema)
    r += ["## 7. Visões candidatas\n", tabela_md(cols, l, 120)]

    return _salvar(con, r)


def _salvar(con, r) -> int:
    con.rollback()
    con.close()
    saida = Path(f"relatorio_mega_{dt.datetime.now():%Y%m%d_%H%M}.md")
    saida.write_text("\n".join(r), encoding="utf-8")
    print(f"Relatório gerado: {saida.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
