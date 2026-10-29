"""T04 Consulta de estoque e T05 Detalhe do lote (contrato em docs/api/01_contrato_api.md)."""
from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api import deps
from app.core.db import get_db
from app.models import Destinacao, Lote, Nota, Usuario
from app.services import auditoria, estoque

router = APIRouter(prefix="/lotes", tags=["estoque"])

Estoque = Literal["ESTOQUE_MEGA", "RJ_NO_RIO", "RJ_EM_ITU"]
Formato = Literal["RETANGULAR", "REDONDO", "RETO"]


def filtros(estoque_: Estoque | None = Query(None, alias="estoque"), liga: str | None = None,
            formato: Formato | None = None, espessura_de: float | None = None, espessura_ate: float | None = None,
            largura_de: float | None = None, largura_ate: float | None = None, diametro_de: float | None = None,
            diametro_ate: float | None = None, conteiner: str | None = None, codigo_mega: int | None = None,
            com_saldo: bool = True, com_destinacao: bool = False, origem_nao_identificada: bool = False,
            busca: str | None = Query(None, max_length=60)) -> dict:
    return {"estoque": estoque_, "liga": liga, "formato": formato, "espessura_de": espessura_de,
            "espessura_ate": espessura_ate, "largura_de": largura_de, "largura_ate": largura_ate,
            "diametro_de": diametro_de, "diametro_ate": diametro_ate, "conteiner": conteiner,
            "codigo_mega": codigo_mega, "com_saldo": com_saldo, "com_destinacao": com_destinacao,
            "origem_nao_identificada": origem_nao_identificada, "busca": busca}


def paginar(itens: list, pagina: int, por_pagina: int) -> dict:
    ini = (pagina - 1) * por_pagina
    return {"itens": itens[ini:ini + por_pagina], "total": len(itens), "pagina": pagina, "por_pagina": por_pagina}


def _lote(db: Session, lote_id: int) -> Lote:
    l = db.get(Lote, lote_id)
    if l is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lote não encontrado.")
    return l


@router.get("")
def listar(f: dict = Depends(filtros), pagina: int = Query(1, ge=1), por_pagina: int = Query(50, ge=1, le=200),
           db: Session = Depends(get_db), _: Usuario = Depends(deps.usuario_liberado)) -> dict:
    return paginar(estoque.lote_resumo(db, estoque.consulta_lotes(db, f)), pagina, por_pagina)


@router.get("/agrupado")
def listar_agrupado(f: dict = Depends(filtros), pagina: int = Query(1, ge=1),
                    por_pagina: int = Query(50, ge=1, le=200), db: Session = Depends(get_db),
                    _: Usuario = Depends(deps.usuario_liberado)) -> dict:
    itens = estoque.lote_resumo(db, estoque.consulta_lotes(db, f))
    return paginar(estoque.agrupado(itens), pagina, por_pagina)


@router.get("/{lote_id}")
def detalhe(lote_id: int, db: Session = Depends(get_db), _: Usuario = Depends(deps.usuario_liberado)) -> dict:
    l = _lote(db, lote_id)
    base = estoque.lote_resumo(db, [l])[0]
    base.update({"peso_inicial_kg": round(l.peso_inicial_kg, 3), "pecas_iniciais": l.pecas_iniciais,
                 "documento_entrada": l.documento_entrada,
                 "data_entrada": l.conteiner.data_entrada.isoformat() if l.conteiner and l.conteiner.data_entrada
                 else None, "custo_kg": l.custo_kg, "status": l.status, "criado_em": l.criado_em.isoformat()})
    return base


@router.get("/{lote_id}/arvore")
def arvore(lote_id: int, db: Session = Depends(get_db), _: Usuario = Depends(deps.usuario_liberado)) -> dict:
    return estoque.arvore(db, _lote(db, lote_id))


@router.get("/{lote_id}/movimentos")
def movimentos(lote_id: int, pagina: int = Query(1, ge=1), por_pagina: int = Query(100, ge=1, le=500),
               db: Session = Depends(get_db), _: Usuario = Depends(deps.usuario_liberado)) -> dict:
    _lote(db, lote_id)
    return paginar(estoque.movimentos(db, lote_id), pagina, por_pagina)


@router.get("/{lote_id}/destinacoes")
def destinacoes(lote_id: int, db: Session = Depends(get_db), _: Usuario = Depends(deps.usuario_liberado)) -> list:
    _lote(db, lote_id)
    hoje = date.today()
    q = (select(Destinacao, Usuario.nome).outerjoin(Usuario, Destinacao.criado_por_id == Usuario.id)
         .where(Destinacao.lote_id == lote_id, Destinacao.ativa.is_(True),
                or_(Destinacao.validade.is_(None), Destinacao.validade >= hoje)).order_by(Destinacao.id))
    return [{"id": d.id, "tipo": d.tipo, "descricao": d.descricao, "kg": d.kg,
             "validade": d.validade.isoformat() if d.validade else None, "criado_por": nome,
             "criado_em": d.criado_em.isoformat()} for d, nome in db.execute(q)]


class NotaEntrada(BaseModel):
    texto: str = Field(min_length=1, max_length=2000)


@router.get("/{lote_id}/notas")
def notas(lote_id: int, db: Session = Depends(get_db), _: Usuario = Depends(deps.usuario_liberado)) -> list:
    _lote(db, lote_id)
    q = (select(Nota, Usuario.nome).outerjoin(Usuario, Nota.usuario_id == Usuario.id)
         .where(Nota.entidade == "LOTE", Nota.entidade_id == lote_id).order_by(Nota.id))
    return [{"id": n.id, "texto": n.texto, "usuario": nome, "criado_em": n.criado_em.isoformat()}
            for n, nome in db.execute(q)]


@router.post("/{lote_id}/notas", status_code=201)
def adicionar_nota(lote_id: int, dados: NotaEntrada, request: Request, db: Session = Depends(get_db),
                   u: Usuario = Depends(deps.usuario_liberado)) -> dict:
    _lote(db, lote_id)
    n = Nota(entidade="LOTE", entidade_id=lote_id, texto=dados.texto.strip(), usuario_id=u.id)
    db.add(n)
    db.flush()
    auditoria.registrar(db, "NOTA_CRIADA", usuario_id=u.id, entidade="lote", entidade_id=lote_id,
                        depois={"nota_id": n.id}, ip=deps.ip_cliente(request))
    db.commit()
    return {"id": n.id, "texto": n.texto, "usuario": u.nome, "criado_em": n.criado_em.isoformat()}
