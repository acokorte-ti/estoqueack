"""T07 Nova solicitação, T08 Solicitações, T09 Fila RJ e T10 Registrar corte.

Contrato: docs/api/01_contrato_api.md §5–§6.
"""
from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api import deps
from app.core.config import Config
from app.core.db import get_db
from app.models import Usuario
from app.services import solicitacoes as svc

router = APIRouter(tags=["solicitações"])

ITU = deps.exigir_perfil("ESTOQUE")
RJ = deps.exigir_perfil("OPERACAO_RJ")
FILA = deps.exigir_perfil("OPERACAO_RJ", "ESTOQUE")
Modo = Literal["CORTAR_RJ", "TRAZER_INTEIRA"]


class Medida(BaseModel):
    formato: Literal["RETANGULAR", "REDONDO"] = "RETANGULAR"
    espessura: float | None = Field(None, gt=0)
    largura: float | None = Field(None, gt=0)
    diametro: float | None = Field(None, gt=0)
    comprimento: float | None = Field(None, gt=0)


class Bruto(BaseModel):
    espessura: float | None = Field(None, gt=0)
    largura: float | None = Field(None, gt=0)
    diametro: float | None = Field(None, gt=0)
    comprimento: float | None = Field(None, gt=0)


class ItemSolicitacao(BaseModel):
    lote_id: int
    modo: Modo
    quantidade: int = Field(gt=0, le=100000)
    sobremetal_comprimento_mm: float | None = Field(None, ge=0, le=1000)
    sobremetal_largura_mm: float | None = Field(None, ge=0, le=1000)
    bruto: Bruto | None = None
    comprimento_barra_mm: float | None = Field(None, gt=0)
    instrucao: str | None = Field(None, max_length=300)
    instrucao_processo: str | None = Field(None, max_length=300)


class OpManual(BaseModel):
    item_codigo: int | None = None
    item_descricao: str | None = Field(None, max_length=200)
    cliente: str | None = Field(None, max_length=160)


class SolicitacaoCorpo(BaseModel):
    op: int = Field(gt=0, description="OP obrigatória [P15]")
    liga: str | None = Field(None, max_length=30, description="Liga pedida (para o selo de liga equivalente)")
    medida: Medida
    itens: list[ItemSolicitacao] = Field(min_length=1, max_length=10)
    prazo: date | None = None
    observacao: str | None = Field(None, max_length=1000)
    op_manual: OpManual | None = Field(None, description="Só quando o Mega está fora do ar")
    enviar: bool = False
    consumo_misto: bool = Field(False, description="OP com consumo nos dois estoques (parte de Itu pela T13) [P26]")
    confirmacoes: dict[str, str] = Field(default_factory=dict)


def _entrada(c: SolicitacaoCorpo) -> svc.SolicitacaoEntrada:
    return svc.SolicitacaoEntrada(
        op=c.op, liga=c.liga, medida=c.medida.model_dump(), prazo=c.prazo, observacao=c.observacao,
        op_manual=c.op_manual.model_dump() if c.op_manual else None, confirmacoes=c.confirmacoes,
        consumo_misto=c.consumo_misto,
        itens=[svc.ItemEntrada(lote_id=i.lote_id, modo=i.modo, quantidade=i.quantidade,
                               sobremetal_comprimento_mm=i.sobremetal_comprimento_mm,
                               sobremetal_largura_mm=i.sobremetal_largura_mm,
                               bruto=i.bruto.model_dump() if i.bruto else None,
                               comprimento_barra_mm=i.comprimento_barra_mm, instrucao=i.instrucao,
                               instrucao_processo=i.instrucao_processo) for i in c.itens])


# ---------------- T07 ----------------

@router.post("/solicitacoes/validar")
def validar(c: SolicitacaoCorpo, db: Session = Depends(get_db), cfg: Config = Depends(deps.config),
            _: Usuario = Depends(ITU)) -> dict:
    previa = svc.validar(db, cfg, _entrada(c))[0]
    db.rollback()   # a consulta da OP atualiza o cache; a prévia não grava nada
    return previa.como_dict()


@router.post("/solicitacoes", status_code=201)
def criar(c: SolicitacaoCorpo, request: Request, db: Session = Depends(get_db), cfg: Config = Depends(deps.config),
          u: Usuario = Depends(ITU)) -> dict:
    sols = svc.criar(db, cfg, _entrada(c), enviar=c.enviar, usuario=u, ip=deps.ip_cliente(request))
    return {"solicitacoes": [svc.detalhe(db, s) for s in sols]}


@router.put("/solicitacoes/{sol_id}")
def editar_rascunho(sol_id: int, c: SolicitacaoCorpo, request: Request, db: Session = Depends(get_db),
                    cfg: Config = Depends(deps.config), u: Usuario = Depends(ITU)) -> dict:
    s = svc.atualizar_rascunho(db, cfg, sol_id, _entrada(c), enviar=c.enviar, usuario=u, ip=deps.ip_cliente(request))
    return svc.detalhe(db, s)


class Confirmacoes(BaseModel):
    confirmacoes: dict[str, str] = Field(default_factory=dict)


@router.post("/solicitacoes/{sol_id}/enviar")
def enviar(sol_id: int, c: Confirmacoes, request: Request, db: Session = Depends(get_db),
           cfg: Config = Depends(deps.config), u: Usuario = Depends(ITU)) -> dict:
    return svc.detalhe(db, svc.enviar_rascunho(db, cfg, sol_id, c.confirmacoes, usuario=u,
                                               ip=deps.ip_cliente(request)))


# ---------------- T08 ----------------

Situacao = Literal["RASCUNHO", "ENVIADA", "MATERIAL_INSUFICIENTE", "CORTADA_PARCIAL", "CORTADA", "EM_COP",
                   "SA_PRONTO", "EM_TRANSITO", "AGUARDANDO_CORTE_ITU", "CONCLUIDA", "CANCELADA"]


@router.get("/solicitacoes")
def listar(situacao: list[Situacao] = Query(default=[]), op: int | None = None, cliente: str | None = None,
           liga: str | None = None, conteiner: str | None = None, de: date | None = None, ate: date | None = None,
           somente_atrasadas: bool = False, pagina: int = Query(1, ge=1), por_pagina: int = Query(50, ge=1, le=200),
           db: Session = Depends(get_db), u: Usuario = Depends(deps.usuario_liberado)) -> dict:
    sols = svc.listar(db, u, {"situacao": situacao, "op": op, "cliente": cliente, "liga": liga, "conteiner": conteiner,
                              "de": de, "ate": ate, "somente_atrasadas": somente_atrasadas})
    ini = (pagina - 1) * por_pagina
    return {"itens": [svc.resumo(db, s) for s in sols[ini:ini + por_pagina]], "total": len(sols), "pagina": pagina,
            "por_pagina": por_pagina}


@router.get("/solicitacoes/{sol_id}")
def detalhe(sol_id: int, db: Session = Depends(get_db), u: Usuario = Depends(deps.usuario_liberado)) -> dict:
    return svc.detalhe(db, svc.obter(db, sol_id, u))


class Motivo(BaseModel):
    motivo: str | None = Field(None, max_length=500)


class Justificativa(BaseModel):
    justificativa: str = Field(min_length=10, max_length=500)


class TrocaLote(BaseModel):
    lote_id: int
    confirmacoes: dict[str, str] = Field(default_factory=dict)


class TrocaOp(BaseModel):
    op: int = Field(gt=0)
    justificativa: str = Field(min_length=10, max_length=500)


@router.post("/solicitacoes/{sol_id}/cancelar")
def cancelar(sol_id: int, c: Motivo, request: Request, db: Session = Depends(get_db),
             u: Usuario = Depends(ITU)) -> dict:
    return svc.detalhe(db, svc.cancelar(db, sol_id, c.motivo, usuario=u, ip=deps.ip_cliente(request)))


@router.post("/solicitacoes/{sol_id}/trocar-lote/validar")
def validar_troca_lote(sol_id: int, c: TrocaLote, db: Session = Depends(get_db), cfg: Config = Depends(deps.config),
                       _: Usuario = Depends(ITU)) -> dict:
    previa = svc.validar_troca_lote(db, cfg, sol_id, c.lote_id)
    db.rollback()
    return previa.como_dict()


@router.post("/solicitacoes/{sol_id}/trocar-lote")
def trocar_lote(sol_id: int, c: TrocaLote, request: Request, db: Session = Depends(get_db),
                cfg: Config = Depends(deps.config), u: Usuario = Depends(ITU)) -> dict:
    return svc.detalhe(db, svc.trocar_lote(db, cfg, sol_id, c.lote_id, c.confirmacoes, usuario=u,
                                           ip=deps.ip_cliente(request)))


@router.post("/solicitacoes/{sol_id}/encerrar")
def encerrar(sol_id: int, c: Justificativa, request: Request, db: Session = Depends(get_db),
             u: Usuario = Depends(ITU)) -> dict:
    return svc.detalhe(db, svc.encerrar_saldo_pendente(db, sol_id, c.justificativa, usuario=u,
                                                       ip=deps.ip_cliente(request)))


@router.post("/solicitacoes/{sol_id}/trocar-op")
def trocar_op(sol_id: int, c: TrocaOp, request: Request, db: Session = Depends(get_db),
              u: Usuario = Depends(ITU)) -> dict:
    s, avisos = svc.trocar_op(db, sol_id, c.op, c.justificativa, usuario=u, ip=deps.ip_cliente(request))
    return {**svc.detalhe(db, s), "avisos": avisos}


@router.post("/solicitacoes/{sol_id}/duplicar", status_code=201)
def duplicar(sol_id: int, request: Request, db: Session = Depends(get_db), u: Usuario = Depends(ITU)) -> dict:
    return svc.detalhe(db, svc.duplicar(db, sol_id, usuario=u, ip=deps.ip_cliente(request)))


# ---------------- T09 / T10 ----------------

@router.get("/fila-rj")
def fila(db: Session = Depends(get_db), _: Usuario = Depends(FILA)) -> list[dict]:
    return [svc.resumo(db, s) for s in svc.fila_rj(db)]


class Observacao(BaseModel):
    observacao: str = Field(min_length=10, max_length=500)


@router.post("/solicitacoes/{sol_id}/material-insuficiente")
def material_insuficiente(sol_id: int, c: Observacao, request: Request, db: Session = Depends(get_db),
                          u: Usuario = Depends(RJ)) -> dict:
    return svc.detalhe(db, svc.material_insuficiente(db, sol_id, c.observacao, usuario=u,
                                                     ip=deps.ip_cliente(request)))


class LinhaCorte(BaseModel):
    lote_id: int
    pecas: int = Field(ge=0, le=100000)
    peso_real_kg: float = Field(gt=0)
    comprimento_barra_mm: float | None = Field(None, gt=0)


class CorteCorpo(BaseModel):
    linhas: list[LinhaCorte] = Field(min_length=1, max_length=10)
    data_corte: date | None = None
    observacao: str | None = Field(None, max_length=1000)
    confirmacoes: dict[str, str] = Field(default_factory=dict)


def _corte(c: CorteCorpo) -> svc.CorteEntrada:
    return svc.CorteEntrada(linhas=[svc.LinhaCorte(**l.model_dump()) for l in c.linhas], data_corte=c.data_corte,
                            observacao=c.observacao, confirmacoes=c.confirmacoes)


@router.post("/solicitacoes/{sol_id}/corte/validar")
def validar_corte(sol_id: int, c: CorteCorpo, db: Session = Depends(get_db), cfg: Config = Depends(deps.config),
                  _: Usuario = Depends(RJ)) -> dict:
    return svc.validar_corte(db, cfg, svc.obter(db, sol_id), _corte(c)).como_dict()


@router.post("/solicitacoes/{sol_id}/corte", status_code=201)
def registrar_corte(sol_id: int, c: CorteCorpo, request: Request, db: Session = Depends(get_db),
                    cfg: Config = Depends(deps.config), u: Usuario = Depends(RJ)) -> dict:
    return svc.detalhe(db, svc.registrar_corte(db, cfg, sol_id, _corte(c), usuario=u, ip=deps.ip_cliente(request)))
