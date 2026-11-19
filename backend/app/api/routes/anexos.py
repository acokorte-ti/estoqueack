"""Documentos anexos (spec v3.15 "Documentos anexos"; contrato §16.4).

O arquivo vai **puro no corpo** (Content-Type do arquivo), com tipo/nome/descrição na query: sem multipart (não
precisa de dependência nova). Só usuário logado; Operação RJ só o que é de lote do RJ no Rio [P10].
"""
from __future__ import annotations

import unicodedata
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api import deps
from app.core.db import get_db
from app.models import Usuario
from app.services import anexos as svc

router = APIRouter(tags=["anexos"])
ADMIN = deps.exigir_perfil()
Tipo = Literal["NF", "PACKING_LIST", "OUTRO"]   # precificador não é anexo (Eduardo, 2026-11-19, pendências 7)


class Justificativa(BaseModel):
    justificativa: str = Field(max_length=500)


async def _corpo(request: Request, db: Session) -> bytes:
    tamanho = request.headers.get("content-length", "")
    if tamanho.isdigit():
        svc.conferir_tamanho(db, int(tamanho))   # recusa antes de ler um arquivo grande
    return await request.body()


@router.post("/lotes/{lote_id}/anexos", status_code=201)
async def anexar_no_lote(lote_id: int, request: Request, tipo: Tipo, nome: str = Query(min_length=1, max_length=255),
                         descricao: str | None = Query(None, max_length=120), db: Session = Depends(get_db),
                         u: Usuario = Depends(deps.usuario_liberado)) -> dict:
    dados = await _corpo(request, db)
    return svc.anexar_no_lote(db, lote_id, tipo=tipo, nome=nome, descricao=descricao, dados=dados, usuario=u,
                              ip=deps.ip_cliente(request))


@router.post("/entradas-nf/{entrada_id}/anexos", status_code=201)
async def anexar_na_entrada(entrada_id: int, request: Request, tipo: Tipo,
                            nome: str = Query(min_length=1, max_length=255),
                            descricao: str | None = Query(None, max_length=120), db: Session = Depends(get_db),
                            u: Usuario = Depends(deps.usuario_liberado)) -> dict:
    dados = await _corpo(request, db)
    return svc.anexar_na_entrada(db, entrada_id, tipo=tipo, nome=nome, descricao=descricao, dados=dados, usuario=u,
                                 ip=deps.ip_cliente(request))


@router.get("/anexos/{anexo_id}/arquivo")
def arquivo(anexo_id: int, baixar: bool = False, db: Session = Depends(get_db),
            u: Usuario = Depends(deps.usuario_liberado)) -> Response:
    a = svc.anexo_ou_404(db, anexo_id, u)
    dados = svc.conteudo(db, a)
    simples = unicodedata.normalize("NFKD", a.nome_arquivo).encode("ascii", "ignore").decode().replace('"', "")
    disp = "attachment" if baixar else "inline"
    return Response(content=dados, media_type=a.content_type, headers={
        "Content-Disposition": f"{disp}; filename=\"{simples or 'documento'}\"; "
                               f"filename*=UTF-8''{quote(a.nome_arquivo)}",
        "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@router.post("/anexos/{anexo_id}/apagar")
def apagar(anexo_id: int, c: Justificativa, request: Request, db: Session = Depends(get_db),
           u: Usuario = Depends(deps.usuario_liberado)) -> dict:
    return svc.apagar(db, anexo_id, c.justificativa, usuario=u, ip=deps.ip_cliente(request))


@router.post("/anexos/{anexo_id}/restaurar")
def restaurar(anexo_id: int, request: Request, db: Session = Depends(get_db), u: Usuario = Depends(ADMIN)) -> dict:
    return svc.restaurar(db, anexo_id, usuario=u, ip=deps.ip_cliente(request))
