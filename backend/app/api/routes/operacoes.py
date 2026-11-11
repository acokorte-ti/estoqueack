"""T13 Corte em Itu, T06 Entrada por NF, T17 Reservas e restrições, T18 Ajuste e estorno, T05 Atribuir origem e
T23 Parâmetros. Contrato: docs/api/01_contrato_api.md §10–§14."""
from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import deps
from app.core.config import Config
from app.core.db import get_db
from app.models import Conteiner, EntradaNf, Parametro, Usuario
from app.services import auditoria, corte_itu, operacoes
from app.services.base import ErroNegocio, NaoEncontrado, agora

router = APIRouter(tags=["operações"])

ITU = deps.exigir_perfil("ESTOQUE")
RJ = deps.exigir_perfil("OPERACAO_RJ")
RESERVA = deps.exigir_perfil("ESTOQUE", "ANALISE")
ESTORNO = deps.exigir_perfil("ESTOQUE", "OPERACAO_RJ")
ADMIN = deps.exigir_perfil()   # só ADMIN


# ---------------- T13 ----------------

class OpManual(BaseModel):
    item_codigo: int | None = None
    cliente: str | None = Field(None, max_length=160)


class CorteItuCorpo(BaseModel):
    op: int = Field(gt=0)
    lote_id: int
    consumo_kg: float = Field(gt=0)
    sobra_kg: float = Field(0, ge=0)
    sobra_na_bitola: bool = True
    pecas: int | None = Field(None, ge=0)
    peso_usado_kg: float | None = Field(None, gt=0, description="Peso do material antes do corte (padrão: saldo)")
    previsto_kg: float | None = Field(None, gt=0)
    data_corte: date | None = None
    observacao: str | None = Field(None, max_length=1000)
    op_manual: OpManual | None = None
    consumo_misto: bool = Field(False, description="Parte de Itu de uma OP com consumo Itu + RJ [P26]")
    confirmacoes: dict[str, str] = Field(default_factory=dict)


def _ci(c: CorteItuCorpo) -> corte_itu.CorteItuEntrada:
    d = c.model_dump()
    d["op_manual"] = c.op_manual.model_dump() if c.op_manual else None
    return corte_itu.CorteItuEntrada(**d)


@router.get("/cortes-itu/sugestao")
def sugestao(op: int, db: Session = Depends(get_db), _: Usuario = Depends(ITU)) -> dict:
    lote = corte_itu.lote_sugerido(db, op)
    return {"lote_id": lote.id if lote else None, "lote": lote.codigo if lote else None}


@router.post("/cortes-itu/validar")
def validar_corte_itu(c: CorteItuCorpo, db: Session = Depends(get_db), cfg: Config = Depends(deps.config),
                      _: Usuario = Depends(ITU)) -> dict:
    previa = corte_itu.validar(db, cfg, _ci(c))[0]
    db.rollback()
    return previa.como_dict()


@router.post("/cortes-itu", status_code=201)
def registrar_corte_itu(c: CorteItuCorpo, request: Request, db: Session = Depends(get_db),
                        cfg: Config = Depends(deps.config), u: Usuario = Depends(ITU)) -> dict:
    return corte_itu.para_dict(db, corte_itu.registrar(db, cfg, _ci(c), usuario=u, ip=deps.ip_cliente(request)))


# ---------------- T06 ----------------

class ItemNf(BaseModel):
    liga: str = Field(min_length=1, max_length=30)
    formato: Literal["RETANGULAR", "REDONDO"]
    espessura: float | None = Field(None, gt=0)
    largura: float | None = Field(None, gt=0)
    diametro: float | None = Field(None, gt=0)
    descricao_nf: str | None = Field(None, max_length=200)
    pecas: int | None = Field(None, ge=0)
    peso_kg: float = Field(gt=0)
    comprimento: str | None = Field(None, max_length=40)
    custo_kg: float | None = Field(None, ge=0)


class EntradaCorpo(BaseModel):
    numero: str = Field(min_length=1, max_length=20)
    data: date
    fornecedor: str = Field(min_length=2, max_length=120)
    conteiner: str = Field(min_length=2, max_length=30)
    itens: list[ItemNf] = Field(min_length=1, max_length=100)
    confirmacoes: dict[str, str] = Field(default_factory=dict)


def _en(c: EntradaCorpo) -> operacoes.EntradaNfDados:
    return operacoes.EntradaNfDados(c.numero, c.data, c.fornecedor, c.conteiner,
                                    [operacoes.ItemNf(**i.model_dump()) for i in c.itens], c.confirmacoes)


@router.get("/conteineres")
def conteineres(busca: str | None = Query(None, max_length=30), db: Session = Depends(get_db),
                _: Usuario = Depends(deps.usuario_liberado)) -> list[dict]:
    q = select(Conteiner).order_by(Conteiner.codigo)
    if busca:
        q = q.where(Conteiner.codigo.ilike(f"%{busca.strip()}%"))
    return [{"id": c.id, "codigo": c.codigo, "data_entrada": c.data_entrada.isoformat() if c.data_entrada else None}
            for c in db.scalars(q.limit(200))]


@router.get("/entradas-nf")
def listar_entradas(db: Session = Depends(get_db), _: Usuario = Depends(deps.usuario_liberado)) -> list[dict]:
    return [operacoes.entrada_dict(db, n) for n in db.scalars(select(EntradaNf).order_by(EntradaNf.id.desc())
                                                                   .limit(200))]


@router.post("/entradas-nf/validar")
def validar_entrada(c: EntradaCorpo, db: Session = Depends(get_db), _: Usuario = Depends(RJ)) -> dict:
    return operacoes.validar_entrada(db, _en(c)).como_dict()


@router.post("/entradas-nf", status_code=201)
def registrar_entrada(c: EntradaCorpo, request: Request, db: Session = Depends(get_db),
                      u: Usuario = Depends(RJ)) -> dict:
    return operacoes.entrada_dict(db, operacoes.registrar_entrada(db, _en(c), usuario=u, ip=deps.ip_cliente(request)))


# ---------------- T17 ----------------

class DestinacaoCorpo(BaseModel):
    tipo: Literal["RESERVA", "RESTRICAO"]
    descricao: str = Field(min_length=3, max_length=300)
    kg: float | None = Field(None, gt=0)
    validade: date | None = None


@router.post("/lotes/{lote_id}/destinacoes", status_code=201)
def criar_destinacao(lote_id: int, c: DestinacaoCorpo, request: Request, db: Session = Depends(get_db),
                     u: Usuario = Depends(RESERVA)) -> dict:
    d = operacoes.criar_destinacao(db, lote_id, c.tipo, c.descricao, c.kg, c.validade, usuario=u,
                                   ip=deps.ip_cliente(request))
    return {"id": d.id, "tipo": d.tipo, "descricao": d.descricao, "kg": d.kg,
            "validade": d.validade.isoformat() if d.validade else None}


@router.post("/destinacoes/{dest_id}/encerrar", status_code=204)
def encerrar_destinacao(dest_id: int, request: Request, db: Session = Depends(get_db),
                        u: Usuario = Depends(RESERVA)):
    operacoes.encerrar_destinacao(db, dest_id, usuario=u, ip=deps.ip_cliente(request))


# ---------------- T18 ----------------

class AjusteCorpo(BaseModel):
    saldo_contado_kg: float = Field(ge=0)
    justificativa: str = Field("", max_length=500)


@router.post("/lotes/{lote_id}/ajuste/validar")
def validar_ajuste(lote_id: int, c: AjusteCorpo, db: Session = Depends(get_db), _: Usuario = Depends(ITU)) -> dict:
    return operacoes.validar_ajuste(db, lote_id, c.saldo_contado_kg).como_dict()


@router.post("/lotes/{lote_id}/ajuste", status_code=201)
def ajustar(lote_id: int, c: AjusteCorpo, request: Request, db: Session = Depends(get_db),
            u: Usuario = Depends(ITU)) -> dict:
    m = operacoes.ajustar(db, lote_id, c.saldo_contado_kg, c.justificativa, usuario=u, ip=deps.ip_cliente(request))
    return {"movimento_id": m.id, "kg": m.kg}


class Justificativa(BaseModel):
    justificativa: str = Field(min_length=10, max_length=500)


@router.post("/movimentos/{mov_id}/estorno", status_code=201)
def estornar(mov_id: int, c: Justificativa, request: Request, db: Session = Depends(get_db),
             u: Usuario = Depends(ESTORNO)) -> dict:
    m = operacoes.estornar(db, mov_id, c.justificativa, usuario=u, ip=deps.ip_cliente(request))
    return {"movimento_id": m.id, "kg": m.kg, "estorno_de": m.estorno_de_id}


class OrigemCorpo(BaseModel):
    conteiner: str = Field(min_length=2, max_length=30)
    lote_pai_id: int | None = None
    justificativa: str = Field(min_length=10, max_length=500)


@router.post("/lotes/{lote_id}/atribuir-origem")
def atribuir_origem(lote_id: int, c: OrigemCorpo, request: Request, db: Session = Depends(get_db),
                    u: Usuario = Depends(ITU)) -> dict:
    l = operacoes.atribuir_origem(db, lote_id, c.conteiner, c.lote_pai_id, c.justificativa, usuario=u,
                                  ip=deps.ip_cliente(request))
    return {"id": l.id, "codigo": l.codigo, "origem_identificada": l.origem_identificada}


# ---------------- T23 ----------------

@router.get("/parametros")
def parametros(db: Session = Depends(get_db), _: Usuario = Depends(deps.usuario_liberado)) -> list[dict]:
    return [{"chave": p.chave, "valor": p.valor, "tipo": p.tipo, "descricao": p.descricao,
             "atualizado_em": p.atualizado_em.isoformat()} for p in db.scalars(select(Parametro)
                                                                              .order_by(Parametro.chave))]


class ValorParametro(BaseModel):
    valor: str = Field(min_length=1, max_length=200)


@router.patch("/parametros/{chave}")
def alterar_parametro(chave: str, c: ValorParametro, request: Request, db: Session = Depends(get_db),
                      u: Usuario = Depends(ADMIN)) -> dict:
    p = db.get(Parametro, chave)
    if p is None:
        raise NaoEncontrado("Parâmetro não encontrado.")
    v = c.valor.strip()
    if p.tipo == "NUMERO":
        try:
            if float(v.replace(",", ".")) < 0:
                raise ValueError
        except ValueError:
            raise ErroNegocio("Informe um número maior ou igual a zero.") from None
    antes = p.valor
    p.valor, p.atualizado_em, p.atualizado_por_id = v, agora(), u.id
    auditoria.registrar(db, "PARAMETRO_ALTERADO", usuario_id=u.id, entidade="parametro", entidade_id=chave,
                        antes={"valor": antes}, depois={"valor": v}, ip=deps.ip_cliente(request))
    db.commit()
    return {"chave": p.chave, "valor": p.valor}
