"""Roda o que estiver vencido: sincronização com o Mega (06:00 e 13:00, T23) e verificação dos SAs (30 min).

Cron do system-lab (a cada 5 min, ver deploy/cron/estoqueack-agendador.sh):
    docker compose exec -T api python -m app.jobs.agendador
Uso manual: `python -m app.jobs.agendador --forcar` sincroniza o estoque agora.
"""
from __future__ import annotations

import json
import sys

from app.core.db import SessionLocal
from app.services import sync_mega


def main(argv: list[str]) -> int:
    with SessionLocal() as db:
        if "--forcar" in argv:
            s = sync_mega.sincronizar_estoque(db, gatilho="MANUAL")
            feito = {"estoque": s.situacao, "detalhes": s.detalhes}
        else:
            feito = sync_mega.rodar_agendado(db)
    print(json.dumps(feito, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
