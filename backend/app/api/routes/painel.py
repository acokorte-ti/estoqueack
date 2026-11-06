from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api import deps
from app.core.db import get_db
from app.models import Lote, Usuario
from app.services import painel as svc
from app.services.base import so_rj_no_rio

router = APIRouter(prefix="/painel", tags=["painel"])
router_conciliacao = APIRouter(prefix="/conciliacao", tags=["conciliação"])

BALDES = {
    ("ITU", "ITU"): "ESTOQUE_MEGA",
    ("RJ", "RJ"): "RJ_NO_RIO",
    ("RJ", "ITU"): "RJ_EM_ITU",
}


@router.get("/resumo")
def resumo(db: Session = Depends(get_db), u: Usuario = Depends(deps.usuario_liberado)) -> dict:
    q = (
        select(Lote.planta_fiscal, Lote.local_fisico, func.count(Lote.id), func.coalesce(func.sum(Lote.saldo_kg), 0))
        .where(Lote.saldo_kg > 0)
        .group_by(Lote.planta_fiscal, Lote.local_fisico))
    linhas = db.execute(q).all()
    baldes = {nome: {"lotes": 0, "kg": 0.0} for nome in BALDES.values()}
    if so_rj_no_rio(u):                      # P10: Operação RJ vê só o RJ no Rio (os outros baldes nem aparecem)
        baldes = {"RJ_NO_RIO": baldes["RJ_NO_RIO"]}
    for planta, local, qtd, kg in linhas:
        nome = BALDES.get((planta, local))
        if nome in baldes:
            baldes[nome] = {"lotes": int(qtd), "kg": round(float(kg), 3)}
    return {"baldes": baldes, "total_kg": round(sum(b["kg"] for b in baldes.values()), 3)}


@router.get("/pendencias")
def pendencias(db: Session = Depends(get_db), u: Usuario = Depends(deps.usuario_liberado)) -> dict:
    """T03: pendências do perfil (Admin vê os três grupos), atrasos, divergências com o Mega e última sincronização."""
    return svc.pendencias(db, u)


@router_conciliacao.get("")
def conciliacao(somente_divergentes: bool = False, db: Session = Depends(get_db),
                _: Usuario = Depends(deps.exigir_perfil("ESTOQUE", "ANALISE"))) -> dict:
    """T16 mínima (só leitura): código Mega × soma dos lotes do Estoque Mega."""
    return svc.conciliacao(db, somente_divergentes=somente_divergentes)
