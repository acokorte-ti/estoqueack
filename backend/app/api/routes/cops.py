"""T11 COP, T12 Receber COP e T14 SA. Contrato: docs/api/01_contrato_api.md §7–§9."""
from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api import deps
from app.core.db import get_db
from app.models import Usuario
from app.services import cops, sas

router = APIRouter(tags=["COP e SA"])

RJ = deps.exigir_perfil("OPERACAO_RJ")
ITU = deps.exigir_perfil("ESTOQUE")
VER_COP = deps.exigir_perfil("OPERACAO_RJ", "ESTOQUE", "ANALISE")
VER_SA = deps.exigir_perfil("ESTOQUE", "OPERACAO_RJ", "ANALISE")
RS_KG = deps.exigir_perfil("ESTOQUE", "ANALISE")
SituacaoCop = Literal["ABERTO", "FECHADO", "ENVIADO", "RECEBIDO_PARCIAL", "RECEBIDO"]
Emitente = Literal["FIO_CERTO", "MEDIO_VALE", "OUTRO"]


# ---------------- T11 ----------------

@router.get("/cops")
def listar(situacao: list[SituacaoCop] = Query(default=[]), db: Session = Depends(get_db),
           _: Usuario = Depends(VER_COP)) -> list[dict]:
    return [cops.cop_dict(db, c, com_itens=False) for c in cops.listar(db, situacao)]


@router.get("/cops/proximo-numero")
def proximo(db: Session = Depends(get_db), _: Usuario = Depends(VER_COP)) -> dict:
    return {"numero": cops.proximo_numero(db)}


@router.get("/cops/cortes-prontos")
def cortes_prontos(db: Session = Depends(get_db), _: Usuario = Depends(VER_COP)) -> list[dict]:
    return [cops.pronto_dict(l) for l in cops.cortes_prontos(db)]


class NovoCop(BaseModel):
    numero: int | None = Field(None, gt=0)
    observacao: str | None = Field(None, max_length=1000)


@router.post("/cops", status_code=201)
def criar(c: NovoCop, request: Request, db: Session = Depends(get_db), u: Usuario = Depends(RJ)) -> dict:
    return cops.cop_dict(db, cops.criar(db, c.numero, c.observacao, usuario=u, ip=deps.ip_cliente(request)))


@router.get("/cops/{cop_id}")
def detalhe(cop_id: int, db: Session = Depends(get_db), _: Usuario = Depends(VER_COP)) -> dict:
    return cops.cop_dict(db, cops.obter(db, cop_id))


class Itens(BaseModel):
    liberacao_ids: list[int] = Field(min_length=1, max_length=200)


@router.post("/cops/{cop_id}/itens")
def adicionar(cop_id: int, c: Itens, request: Request, db: Session = Depends(get_db), u: Usuario = Depends(RJ)) -> dict:
    return cops.cop_dict(db, cops.adicionar_itens(db, cop_id, c.liberacao_ids, usuario=u, ip=deps.ip_cliente(request)))


@router.delete("/cops/{cop_id}/itens/{item_id}")
def remover(cop_id: int, item_id: int, request: Request, db: Session = Depends(get_db),
            u: Usuario = Depends(RJ)) -> dict:
    return cops.cop_dict(db, cops.remover_item(db, cop_id, item_id, usuario=u, ip=deps.ip_cliente(request)))


@router.post("/cops/{cop_id}/fechar")
def fechar(cop_id: int, request: Request, db: Session = Depends(get_db), u: Usuario = Depends(RJ)) -> dict:
    return cops.cop_dict(db, cops.fechar(db, cop_id, usuario=u, ip=deps.ip_cliente(request)))


class Justificativa(BaseModel):
    justificativa: str = Field(min_length=10, max_length=500)


@router.post("/cops/{cop_id}/reabrir")
def reabrir(cop_id: int, c: Justificativa, request: Request, db: Session = Depends(get_db),
            u: Usuario = Depends(RJ)) -> dict:
    return cops.cop_dict(db, cops.reabrir(db, cop_id, c.justificativa, usuario=u, ip=deps.ip_cliente(request)))


class NfCorpo(BaseModel):
    numero: str = Field(min_length=1, max_length=20)
    emitente: Emitente
    data: date | None = None
    item_ids: list[int] | None = Field(None, description="Vazio: todos os itens. Senão: 'NF diferente para itens "
                                                          "selecionados'")


@router.post("/cops/{cop_id}/nf")
def nf(cop_id: int, c: NfCorpo, request: Request, db: Session = Depends(get_db), u: Usuario = Depends(RJ)) -> dict:
    return cops.cop_dict(db, cops.informar_nf(db, cop_id, c.numero, c.emitente, c.data, c.item_ids, usuario=u,
                                              ip=deps.ip_cliente(request)))


@router.post("/cops/{cop_id}/enviar/validar")
def validar_envio(cop_id: int, db: Session = Depends(get_db), _: Usuario = Depends(RJ)) -> dict:
    return cops.validar_envio(db, cops.obter(db, cop_id)).como_dict()


@router.post("/cops/{cop_id}/enviar")
def enviar(cop_id: int, request: Request, db: Session = Depends(get_db), u: Usuario = Depends(RJ)) -> dict:
    return cops.cop_dict(db, cops.enviar(db, cop_id, usuario=u, ip=deps.ip_cliente(request)))


# ---------------- T12 ----------------

@router.get("/recebimentos")
def em_transito(db: Session = Depends(get_db), _: Usuario = Depends(deps.exigir_perfil("ESTOQUE", "OPERACAO_RJ"))
                ) -> list[dict]:
    return [cops.cop_dict(db, c, com_itens=False) for c in cops.listar(db, ["ENVIADO", "RECEBIDO_PARCIAL"])]


class ItemRecebido(BaseModel):
    cop_item_id: int
    peso_conferido_kg: float | None = Field(None, gt=0)


class Recebimento(BaseModel):
    itens: list[ItemRecebido] = Field(min_length=1, max_length=200)
    confirmacoes: dict[str, str] = Field(default_factory=dict)


def _rec(c: Recebimento) -> cops.RecebimentoEntrada:
    return cops.RecebimentoEntrada([cops.ItemRecebido(**i.model_dump()) for i in c.itens], c.confirmacoes)


@router.post("/cops/{cop_id}/receber/validar")
def validar_recebimento(cop_id: int, c: Recebimento, db: Session = Depends(get_db), _: Usuario = Depends(ITU)) -> dict:
    return cops.validar_recebimento(db, cops.obter(db, cop_id), _rec(c)).como_dict()


@router.post("/cops/{cop_id}/receber")
def receber(cop_id: int, c: Recebimento, request: Request, db: Session = Depends(get_db),
            u: Usuario = Depends(ITU)) -> dict:
    return cops.cop_dict(db, cops.receber(db, cop_id, _rec(c), usuario=u, ip=deps.ip_cliente(request)))


class Divergencia(BaseModel):
    cop_item_id: int
    tipo: Literal["FALTANDO", "DANIFICADO", "PESO_DIFERENTE"]
    pecas: int | None = Field(None, ge=0)
    kg: float | None = Field(None, ge=0)
    observacao: str = Field(min_length=3, max_length=1000)


@router.post("/cops/{cop_id}/divergencias", status_code=201)
def divergencia(cop_id: int, c: Divergencia, request: Request, db: Session = Depends(get_db),
                u: Usuario = Depends(ITU)) -> dict:
    d = cops.registrar_divergencia(db, cop_id, c.cop_item_id, c.tipo, c.pecas, c.kg, c.observacao, usuario=u,
                                   ip=deps.ip_cliente(request))
    return {"id": d.id}


# ---------------- T14 ----------------

SituacaoSa = Literal["PENDENTE", "PREPARADO", "AGUARDANDO_MEGA", "CONFIRMADO"]
OrigemSa = Literal["COP", "CORTE_ITU", "CARGA"]


@router.get("/sas")
def listar_sas(situacao: list[SituacaoSa] = Query(default=[]), origem: list[OrigemSa] = Query(default=[]),
               op: int | None = None, cop: int | None = None, nao_exportados: bool = False,
               pagina: int = Query(1, ge=1), por_pagina: int = Query(100, ge=1, le=500),
               db: Session = Depends(get_db), u: Usuario = Depends(VER_SA)) -> dict:
    if not situacao and not op and not cop:
        situacao = ["PENDENTE", "PREPARADO", "AGUARDANDO_MEGA"]
    linhas = sas.listar(db, {"situacao": situacao, "origem": origem or ["COP", "CORTE_ITU"], "op": op, "cop": cop,
                             "nao_exportados": nao_exportados}, u)
    ini = (pagina - 1) * por_pagina
    segurando = [cops.cop_dict(db, c, com_itens=False) for c in cops.listar(db, ["FECHADO"])
                 if cops.situacao_exibida(db, c) == "FECHADO"]
    return {"itens": [sas.para_dict(db, s) for s in linhas[ini:ini + por_pagina]], "total": len(linhas),
            "pagina": pagina, "por_pagina": por_pagina, "cops_aguardando_sa": segurando}


@router.get("/sas/{sa_id}")
def detalhe_sa(sa_id: int, db: Session = Depends(get_db), u: Usuario = Depends(VER_SA)) -> dict:
    return sas.para_dict(db, sas.obter(db, sa_id, usuario=u))


class EdicaoSa(BaseModel):
    rs_kg: float | None = Field(None, ge=0)
    sa_descricao: str | None = Field(None, max_length=200)
    ncm: str | None = Field(None, max_length=15)
    icms: str | None = Field(None, max_length=10)
    ipi: str | None = Field(None, max_length=10)
    pedido: str | None = Field(None, max_length=40)
    quantidade: int | None = Field(None, gt=0)
    peso_kg: float | None = Field(None, gt=0)


@router.patch("/sas/{sa_id}")
def editar_sa(sa_id: int, c: EdicaoSa, request: Request, db: Session = Depends(get_db),
              u: Usuario = Depends(RS_KG)) -> dict:
    dados = c.model_dump(exclude_unset=True)
    if u.perfil == "ANALISE" and set(dados) - {"rs_kg"}:
        dados = {k: v for k, v in dados.items() if k == "rs_kg"}
    return sas.para_dict(db, sas.editar(db, sa_id, dados, usuario=u, ip=deps.ip_cliente(request)))


class Ids(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=500)


@router.post("/sas/preparar")
def preparar(c: Ids, request: Request, db: Session = Depends(get_db), u: Usuario = Depends(ITU)) -> list[dict]:
    return [sas.para_dict(db, s) for s in sas.preparar(db, c.ids, usuario=u, ip=deps.ip_cliente(request))]


class CodigoSa(BaseModel):
    sa_codigo: int = Field(gt=0)
    confirmacoes: dict[str, str] = Field(default_factory=dict)


@router.post("/sas/{sa_id}/codigo/validar")
def validar_codigo(sa_id: int, c: CodigoSa, db: Session = Depends(get_db), _: Usuario = Depends(ITU)) -> dict:
    return sas.validar_codigo(db, sas.obter(db, sa_id), c.sa_codigo).como_dict()


@router.post("/sas/{sa_id}/codigo")
def informar_codigo(sa_id: int, c: CodigoSa, request: Request, db: Session = Depends(get_db),
                    u: Usuario = Depends(ITU)) -> dict:
    return sas.para_dict(db, sas.informar_codigo(db, sa_id, c.sa_codigo, c.confirmacoes, usuario=u,
                                                 ip=deps.ip_cliente(request)))


class Verificar(BaseModel):
    ids: list[int] | None = None


@router.post("/sas/verificar")
def verificar(c: Verificar, db: Session = Depends(get_db), _: Usuario = Depends(ITU)) -> dict:
    alvo = [sas.obter(db, i) for i in c.ids] if c.ids else sas.listar(db, {"situacao": ["AGUARDANDO_MEGA"]})
    res = sas.verificar(db, alvo)
    db.commit()
    return res


class NfB2(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=500)
    numero: str = Field(min_length=1, max_length=20)
    emitente: Emitente
    data: date | None = None


@router.post("/sas/nf")
def nf_b2(c: NfB2, request: Request, db: Session = Depends(get_db), u: Usuario = Depends(ITU)) -> list[dict]:
    return [sas.para_dict(db, s) for s in sas.informar_nf_b2(db, c.ids, c.numero, c.emitente, c.data, usuario=u,
                                                             ip=deps.ip_cliente(request))]
