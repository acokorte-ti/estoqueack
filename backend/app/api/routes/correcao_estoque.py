"""T27 Corrigir estoque, só Admin (spec v3.22, contrato §16.7)."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api import deps
from app.core.db import get_db
from app.models import Usuario
from app.services import correcao_estoque as svc
from app.services import movimentos

router = APIRouter(prefix="/admin", tags=["T27 corrigir estoque"])
ADMIN = deps.exigir_perfil()          # só ADMIN


@router.get("/estoque")
def listar(estoque: Literal["RJ_NO_RIO", "RJ_EM_ITU"] | None = None, conteiner: str | None = None,
           liga: str | None = None, busca: str | None = Query(None, max_length=60), com_saldo: bool = True,
           db: Session = Depends(get_db), _: Usuario = Depends(ADMIN)) -> dict:
    itens = svc.listar(db, {"estoque": estoque, "conteiner": conteiner, "liga": liga, "busca": busca,
                            "com_saldo": com_saldo})
    return {"itens": itens, "total": len(itens)}


class Correcao(BaseModel):
    conteiner: str | None = Field(None, max_length=30)
    liga: str | None = Field(None, max_length=30)
    formato: Literal["RETANGULAR", "REDONDO", "RETO"] | None = None
    espessura: float | None = Field(None, gt=0, lt=10000)
    largura: float | None = Field(None, gt=0, lt=10000)
    diametro: float | None = Field(None, gt=0, lt=10000)
    comprimento_fixado: str | None = Field(None, max_length=120)
    descricao: str | None = Field(None, max_length=200)
    local_fisico: Literal["RJ", "ITU"] | None = None
    saldo_kg: float | None = Field(None, ge=0, lt=10_000_000)
    custo_kg: float | None = Field(None, ge=0, lt=100_000)
    observacao: str | None = Field(None, max_length=400)
    confirmacoes: dict[str, str] = Field(default_factory=dict)

    def campos(self) -> dict:
        d = self.model_dump(exclude_unset=True, exclude={"observacao", "confirmacoes"})
        # campo obrigatório mandado como null = "não muda" (só contêiner, comprimento e R$/kg podem ser limpos)
        return {k: v for k, v in d.items() if v is not None or k in ("conteiner", "comprimento_fixado", "custo_kg")}


@router.post("/lotes/{lote_id}/correcao/validar")
def validar(lote_id: int, c: Correcao, db: Session = Depends(get_db), _: Usuario = Depends(ADMIN)) -> dict:
    return svc.validar(db, movimentos.lote_ou_404(db, lote_id), c.campos()).como_dict()


@router.post("/lotes/{lote_id}/correcao")
def corrigir(lote_id: int, c: Correcao, request: Request, db: Session = Depends(get_db),
             u: Usuario = Depends(ADMIN)) -> dict:
    lote, mov_id = svc.gravar(db, lote_id, c.campos(), observacao=c.observacao, confirmacoes=c.confirmacoes,
                              usuario=u, ip=deps.ip_cliente(request))
    return {"lote": svc.linha(db, lote), "movimento_id": mov_id}
