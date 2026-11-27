"""T28 Histórico de cortes do RJ, só Admin (spec v3.26, contrato §16.8)."""
from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api import deps
from app.api.routes.exportar import _planilha
from app.core.db import get_db
from app.models import Usuario
from app.services import historico_cortes as svc

router = APIRouter(prefix="/admin", tags=["T28 histórico de cortes do RJ"])
ADMIN = deps.exigir_perfil()          # só ADMIN
Situacao = Literal["CORTE_PRONTO", "EM_COP", "EM_TRANSITO", "RECEBIDO", "ESTORNADO"]


def filtros(de: date | None = None, ate: date | None = None, op: int | None = Query(None, gt=0),
            busca: str | None = Query(None, max_length=60), origem: Literal["SISTEMA", "PLANILHA"] | None = None,
            situacao: list[Situacao] = Query(default=[]), estornados: bool = True) -> dict:
    return {"de": de, "ate": ate, "op": op, "busca": busca, "origem": origem, "situacao": situacao,
            "estornados": estornados}


@router.get("/cortes-rj")
def listar(f: dict = Depends(filtros), pagina: int = Query(1, ge=1), por_pagina: int = Query(100, ge=1, le=500),
           db: Session = Depends(get_db), _: Usuario = Depends(ADMIN)) -> dict:
    r = svc.listar(db, f)
    ini = (pagina - 1) * por_pagina
    return {**r, "itens": r["itens"][ini:ini + por_pagina], "pagina": pagina, "por_pagina": por_pagina}


@router.get("/cortes-rj.xlsx")
def exportar(f: dict = Depends(filtros), db: Session = Depends(get_db),
             _: Usuario = Depends(ADMIN)) -> StreamingResponse:
    cab = ["Data do corte", "OP", "Cliente", "Item", "Material", "Contêiner", "Lote", "Peças", "Peso real (kg)",
           "Previsto (kg)", "Diferença (%)", "COP", "Situação", "Origem", "Registrado por", "Registrado em",
           "Lote trocado", "Corrigido no COP", "Observação"]
    linhas = [[date.fromisoformat(x["data_corte"]), x["op"], x["cliente"], x["item_descricao"],
               f"{x['liga']} {x['bitola']}", x["conteiner"], x["lote"], x["pecas"], x["peso_real_kg"], x["previsto_kg"],
               x["diferenca_pct"], x["cop"], x["situacao_nome"], x["origem_nome"], x["registrado_por"],
               x["registrado_em"][:16].replace("T", " "), "sim" if x["lote_trocado"] else "",
               "sim" if x["corrigido"] else "", x["observacao"]] for x in svc.listar(db, f)["itens"]]
    return _planilha("Historico cortes RJ", cab, linhas,
                     [12, 9, 24, 28, 18, 11, 16, 7, 12, 12, 11, 7, 20, 22, 20, 17, 10, 12, 30])


@router.get("/cortes-rj/{lib_id}")
def detalhe(lib_id: int, db: Session = Depends(get_db), _: Usuario = Depends(ADMIN)) -> dict:
    return svc.detalhe(db, lib_id)
