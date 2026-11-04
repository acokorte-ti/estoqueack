"""Roda o que estiver vencido: sincronização com o Mega (06:00 e 13:00, T23), verificação dos SAs (30 min) e os
avisos automáticos do sino (SA 48 h, atrasadas, reservas vencendo, resumo de exceções; `services/avisos.py`).

Cron do system-lab (a cada 5 min, ver deploy/cron/estoqueack-agendador.sh):
    docker compose exec -T api python -m app.jobs.agendador
Uso manual: `python -m app.jobs.agendador --forcar` sincroniza o estoque agora.
"""
from __future__ import annotations

import json
import logging
import sys

from app.core.db import SessionLocal
from app.services import avisos, sync_mega


def main(argv: list[str]) -> int:
    with SessionLocal() as db:
        if "--forcar" in argv:
            s = sync_mega.sincronizar_estoque(db, gatilho="MANUAL")
            feito = {"estoque": s.situacao, "detalhes": s.detalhes}
        else:
            feito = sync_mega.rodar_agendado(db)
        try:
            feito["avisos"] = avisos.rodar(db)
        except Exception as e:  # noqa: BLE001 — aviso nunca derruba a sincronização
            db.rollback()
            logging.getLogger("estoqueack.avisos").exception("falha nos avisos automáticos")
            feito["avisos"] = f"ERRO {type(e).__name__}"
    print(json.dumps(feito, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
