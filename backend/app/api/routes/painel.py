from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api import deps
from app.core.db import get_db
from app.models import Lote, Usuario

router = APIRouter(prefix="/painel", tags=["painel"])

BALDES = {
    ("ITU", "ITU"): "ESTOQUE_MEGA",
    ("RJ", "RJ"): "RJ_NO_RIO",
    ("RJ", "ITU"): "RJ_EM_ITU",
}


@router.get("/resumo")
def resumo(db: Session = Depends(get_db), _: Usuario = Depends(deps.usuario_liberado)) -> dict:
    linhas = db.execute(
        select(Lote.planta_fiscal, Lote.local_fisico, func.count(Lote.id), func.coalesce(func.sum(Lote.saldo_kg), 0))
        .where(Lote.saldo_kg > 0)
        .group_by(Lote.planta_fiscal, Lote.local_fisico)
    ).all()
    baldes = {nome: {"lotes": 0, "kg": 0.0} for nome in BALDES.values()}
    for planta, local, qtd, kg in linhas:
        nome = BALDES.get((planta, local))
        if nome:
            baldes[nome] = {"lotes": int(qtd), "kg": round(float(kg), 3)}
    return {"baldes": baldes, "total_kg": round(sum(b["kg"] for b in baldes.values()), 3)}
