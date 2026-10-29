"""Diagnóstico de conexão com o Mega: testa variações de SDU/descritor sem mostrar a senha.
Uso: $env:ORACLE_IC="<pasta>"; py diagnostico_conexao.py ..\\..\\.mega_ro"""
import os
import sys
import time

import oracledb

oracledb.init_oracle_client(lib_dir=os.environ["ORACLE_IC"])
dsn, usuario, senha = [l.strip() for l in open(sys.argv[1], encoding="utf-8-sig").read().splitlines()[:3]]
hp, servico = dsn.split("/", 1)
host, porta = (hp.split(":") + ["1521"])[:2]
print("cliente:", ".".join(map(str, oracledb.clientversion())), "| host:", host, "| servico:", servico)

variantes = {
    "easy connect": dsn,
    "descritor SDU 2048": f"(DESCRIPTION=(SDU=2048)(ADDRESS=(PROTOCOL=TCP)(HOST={host})(PORT={porta}))"
                          f"(CONNECT_DATA=(SERVICE_NAME={servico})))",
    "descritor como SID": f"(DESCRIPTION=(ADDRESS=(PROTOCOL=TCP)(HOST={host})(PORT={porta}))"
                          f"(CONNECT_DATA=(SID={servico})))",
}
for nome, d in variantes.items():
    t = time.time()
    try:
        c = oracledb.connect(user=usuario, password=senha, dsn=d, tcp_connect_timeout=15)
        cur = c.cursor()
        cur.execute("SELECT sys_context('USERENV','NETWORK_PROTOCOL'), user FROM dual")
        print(f"[OK]   {nome} ({time.time()-t:.1f}s):", cur.fetchone())
        c.close()
        break
    except Exception as e:  # noqa: BLE001
        print(f"[FALHA] {nome} ({time.time()-t:.1f}s):", str(e).splitlines()[0][:160])
