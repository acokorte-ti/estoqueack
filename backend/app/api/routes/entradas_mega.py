"""T15 Entradas Mega a classificar (mínima, F1). Contrato em docs/api/02_contrato_fase1.md §15."""
from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api import deps
from app.core.db import get_db
from app.models import Usuario
from app.services import entradas_mega as svc

router = APIRouter(prefix="/entradas-mega", tags=["T15 entradas Mega"])
VER = deps.exigir_perfil("ESTOQUE", "ANALISE")
ALTERAR = deps.exigir_perfil("ESTOQUE")
ADMIN = deps.exigir_perfil()


class CriarLote(BaseModel):
    peso_kg: float = Field(gt=0, le=1_000_000)
    conteiner: str | None = Field(None, max_length=30)
    sem_conteiner: bool = False
    pecas: int | None = Field(None, gt=0)
    data_entrada: date | None = None
    nf: str | None = Field(None, max_length=60)
    observacao: str | None = Field(None, max_length=500)
    confirmacoes: dict[str, str] = Field(default_factory=dict)

    def dados(self) -> svc.LoteDados:
        return svc.LoteDados(self.peso_kg, self.conteiner, self.sem_conteiner, self.pecas, self.data_entrada,
                             self.nf, self.observacao, self.confirmacoes)


class NaoEntrada(BaseModel):
    motivo: Literal["ESTORNO_BAIXA_MEGA", "ACERTO_INVENTARIO_MEGA", "TRANSFERENCIA_CODIGOS", "OUTRO"]
    justificativa: str = Field(max_length=500)


class Reabrir(BaseModel):
    justificativa: str = Field(max_length=500)


@router.get("")
def listar(situacao: Literal["ABERTA", "RESOLVIDA", "DESCARTADA", "ENCERRADA", "TODAS"] = "ABERTA",
           busca: str | None = Query(None, max_length=60), db: Session = Depends(get_db),
           _: Usuario = Depends(VER)) -> dict:
    return svc.listar(db, situacao=situacao, busca=busca)


@router.get("/motivos")
def motivos(_: Usuario = Depends(VER)) -> list[dict]:
    return [{"codigo": k, "descricao": v} for k, v in svc.MOTIVOS.items()]


@router.get("/{pid}")
def detalhe(pid: int, db: Session = Depends(get_db), _: Usuario = Depends(VER)) -> dict:
    return svc.pendencia_dict(db, svc._pendencia(db, pid))


@router.post("/{pid}/criar-lote/validar")
def criar_lote_validar(pid: int, c: CriarLote, db: Session = Depends(get_db), _: Usuario = Depends(ALTERAR)) -> dict:
    return svc.validar_criar_lote(db, pid, c.dados()).como_dict()


@router.post("/{pid}/criar-lote", status_code=201)
def criar_lote(pid: int, c: CriarLote, request: Request, db: Session = Depends(get_db),
               u: Usuario = Depends(ALTERAR)) -> dict:
    return svc.criar_lote(db, pid, c.dados(), usuario=u, ip=deps.ip_cliente(request))


@router.post("/{pid}/nao-e-entrada")
def nao_e_entrada(pid: int, c: NaoEntrada, request: Request, db: Session = Depends(get_db),
                  u: Usuario = Depends(ALTERAR)) -> dict:
    return svc.nao_e_entrada(db, pid, c.motivo, c.justificativa, usuario=u, ip=deps.ip_cliente(request))


@router.post("/{pid}/reabrir")
def reabrir(pid: int, c: Reabrir, request: Request, db: Session = Depends(get_db),
            u: Usuario = Depends(ADMIN)) -> dict:
    return svc.reabrir(db, pid, c.justificativa, usuario=u, ip=deps.ip_cliente(request))
