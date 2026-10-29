"""Teste rápido da conexão somente leitura com o Mega.
Uso: $env:ORACLE_IC="<pasta instant client>"; py testar_conexao.py ..\\..\\.mega_ro"""
import sys

import oracledb


def _modo_thick() -> None:
    """O banco do Mega exige Native Network Encryption → precisa do modo thick (Oracle Instant Client).
    Defina ORACLE_IC com a pasta do Instant Client (ex.: C:\\Users\\<user>\\oracle\\instantclient_23_0)."""
    import os

    import oracledb
    pasta = os.environ.get("ORACLE_IC")
    if pasta:
        oracledb.init_oracle_client(lib_dir=pasta)

_modo_thick()

dsn, usuario, senha = [l.strip() for l in open(sys.argv[1], encoding="utf-8-sig").read().splitlines()[:3]]
con = oracledb.connect(user=usuario, password=senha, dsn=dsn)
cur = con.cursor()
print("Modo:", "thick" if not oracledb.is_thin_mode() else "thin")
cur.execute("SELECT banner FROM v$version")
print("Versão:", cur.fetchone()[0])
cur.execute("SELECT sys_context('USERENV','CON_NAME'), user FROM dual")
print("Container/usuário:", cur.fetchone())
cur.execute("SELECT privilege FROM session_privs ORDER BY 1")
print("Privilégios:", [r[0] for r in cur])
con.close()
