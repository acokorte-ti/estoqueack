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
from app.services import movimentos as mov
from app.services.base import lote_visivel, so_rj_no_rio
from app.services.solicitacoes import ligas_equivalentes

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


def _lote(db: Session, lote_id: int, usuario: Usuario | None = None) -> Lote:
    l = db.get(Lote, lote_id)
    if l is None or (usuario is not None and not lote_visivel(usuario, l)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lote não encontrado.")
    return l


def _visivel(f: dict, u: Usuario) -> dict:
    """[P10] Operação RJ vê só o RJ no Rio: o filtro de estoque fica travado."""
    if so_rj_no_rio(u):
        f = {**f, "estoque": "RJ_NO_RIO"}
    return f


@router.get("")
def listar(f: dict = Depends(filtros), pagina: int = Query(1, ge=1), por_pagina: int = Query(50, ge=1, le=200),
           db: Session = Depends(get_db), u: Usuario = Depends(deps.usuario_liberado)) -> dict:
    return paginar(estoque.lote_resumo(db, estoque.consulta_lotes(db, _visivel(f, u))), pagina, por_pagina)


@router.get("/agrupado")
def listar_agrupado(f: dict = Depends(filtros), pagina: int = Query(1, ge=1),
                    por_pagina: int = Query(50, ge=1, le=200), db: Session = Depends(get_db),
                    u: Usuario = Depends(deps.usuario_liberado)) -> dict:
    itens = estoque.lote_resumo(db, estoque.consulta_lotes(db, _visivel(f, u)))
    return paginar(estoque.agrupado(itens), pagina, por_pagina)


def filtros_reto(estoque_: Estoque | None = Query(None, alias="estoque"), liga: list[str] = Query(default=[]),
                 bitola_origem: str | None = Query(None, max_length=40), bitola_de: float | None = None,
                 bitola_ate: float | None = None, conteiner: str | None = None, codigo_mega: int | None = None,
                 com_saldo: bool = True, incluir_sobras: bool = False, criado_de: date | None = None,
                 criado_ate: date | None = None) -> dict:
    return {"estoque": estoque_, "ligas": liga, "bitola_origem": bitola_origem, "bitola_de": bitola_de,
            "bitola_ate": bitola_ate, "conteiner": conteiner, "codigo_mega": codigo_mega, "com_saldo": com_saldo,
            "incluir_sobras": incluir_sobras, "criado_de": criado_de, "criado_ate": criado_ate}


def reto_visivel(f: dict, u: Usuario) -> dict:
    """[P10] Operação RJ: estoque travado em RJ no Rio (onde não há lote RETO); nunca RETO de Itu."""
    return {**f, "estoque": "RJ_NO_RIO"} if so_rj_no_rio(u) else f


@router.get("/reto-por-origem")
def reto_por_origem(f: dict = Depends(filtros_reto), db: Session = Depends(get_db),
                    u: Usuario = Depends(deps.usuario_liberado)) -> dict:
    """Aba "RETO por origem" da T04: quantos kg de RETO vieram de cada bitola e contêiner."""
    r = estoque.reto_por_origem(db, reto_visivel(f, u))
    r["estoque_travado"] = "RJ_NO_RIO" if so_rj_no_rio(u) else None
    vazio = "Nenhum RETO no RJ no Rio" if so_rj_no_rio(u) else "Nenhum RETO nos filtros"
    r["mensagem_vazio"] = vazio if r["vazio"] else None
    return r


@router.get("/compativeis")
def compativeis(liga: str, formato: Literal["RETANGULAR", "REDONDO"] = "RETANGULAR",
                espessura: float | None = Query(None, gt=0), largura: float | None = Query(None, gt=0),
                diametro: float | None = Query(None, gt=0), comprimento: float | None = Query(None, gt=0),
                quantidade: int = Query(1, ge=1), estoque_: Estoque | None = Query(None, alias="estoque"),
                db: Session = Depends(get_db), u: Usuario = Depends(deps.usuario_liberado)) -> dict:
    """T07 passo 2: mesma liga (ou equivalente, com selo), bitola que comporta a peça e saldo disponível.
    Ordem: menor sobremetal, depois o lote mais antigo."""
    from app.domain import corte as calc
    from app.models import Liga
    alvo = db.scalar(select(Liga).where(Liga.codigo == liga.strip().upper()))
    if alvo is None:
        return {"itens": [], "total": 0}
    ligas = {alvo.id} | ligas_equivalentes(db, alvo.id)
    f = _visivel({"estoque": estoque_, "com_saldo": True}, u)
    lotes = [l for l in estoque.consulta_lotes(db, f) if l.item.liga_id in ligas and l.status == "ATIVO"]
    res = mov.reservado(db, [l.id for l in lotes])
    acabada = calc.Dimensoes(formato, espessura, largura, diametro, comprimento)
    saida = []
    for l, base in zip(lotes, estoque.lote_resumo(db, lotes), strict=True):
        it = l.item
        if it.formato != "RETO":
            if formato == "REDONDO" and (it.formato != "REDONDO" or (diametro and it.diametro < diametro)):
                continue
            if formato == "RETANGULAR":
                if it.formato != "RETANGULAR":
                    continue
                bit, pec = sorted([it.espessura or 0, it.largura or 0]), sorted([espessura or 0, largura or 0])
                if pec[0] > bit[0] + 1e-9 or pec[1] > bit[1] + 1e-9:
                    continue
        disponivel = round(float(l.saldo_kg) - res.get(l.id, 0.0), 3)
        if disponivel <= 0:
            continue
        bitola = None if it.formato == "RETO" else calc.Dimensoes(it.formato, it.espessura, it.largura, it.diametro)
        c = calc.calcular(bitola=bitola, acabada=acabada, quantidade=quantidade, densidade=float(it.liga.densidade),
                          sobremetal_comprimento_mm=5, sobremetal_largura_mm=None)
        saida.append({**base, "disponivel_kg": disponivel, "liga_equivalente": it.liga_id != alvo.id,
                      "peso_previsto_kg": c.peso_previsto_kg, "peso_peca_kg": c.peso_peca_kg,
                      "sobremetal_pct": c.sobremetal_pct, "substituido_por_id": it.substituido_por_id,
                      "criado_em": l.criado_em.isoformat()})
    saida.sort(key=lambda x: (x["sobremetal_pct"] if x["sobremetal_pct"] is not None else 1e9, x["criado_em"]))
    return {"itens": saida, "total": len(saida)}


@router.get("/{lote_id}")
def detalhe(lote_id: int, db: Session = Depends(get_db), u: Usuario = Depends(deps.usuario_liberado)) -> dict:
    l = _lote(db, lote_id, u)
    base = estoque.lote_resumo(db, [l])[0]
    base.update({"peso_inicial_kg": round(l.peso_inicial_kg, 3), "pecas_iniciais": l.pecas_iniciais,
                 "documento_entrada": l.documento_entrada,
                 "data_entrada": l.conteiner.data_entrada.isoformat() if l.conteiner and l.conteiner.data_entrada
                 else None, "custo_kg": l.custo_kg, "status": l.status, "criado_em": l.criado_em.isoformat()})
    return base


@router.get("/{lote_id}/arvore")
def arvore(lote_id: int, db: Session = Depends(get_db), u: Usuario = Depends(deps.usuario_liberado)) -> dict:
    return estoque.arvore(db, _lote(db, lote_id, u), u)


@router.get("/{lote_id}/movimentos")
def movimentos(lote_id: int, pagina: int = Query(1, ge=1), por_pagina: int = Query(100, ge=1, le=500),
               db: Session = Depends(get_db), u: Usuario = Depends(deps.usuario_liberado)) -> dict:
    _lote(db, lote_id, u)
    return paginar(estoque.movimentos(db, lote_id), pagina, por_pagina)


@router.get("/{lote_id}/destinacoes")
def destinacoes(lote_id: int, db: Session = Depends(get_db), u: Usuario = Depends(deps.usuario_liberado)) -> list:
    _lote(db, lote_id, u)
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
def notas(lote_id: int, db: Session = Depends(get_db), u: Usuario = Depends(deps.usuario_liberado)) -> list:
    _lote(db, lote_id, u)
    q = (select(Nota, Usuario.nome).outerjoin(Usuario, Nota.usuario_id == Usuario.id)
         .where(Nota.entidade == "LOTE", Nota.entidade_id == lote_id).order_by(Nota.id))
    return [{"id": n.id, "texto": n.texto, "usuario": nome, "criado_em": n.criado_em.isoformat()}
            for n, nome in db.execute(q)]


@router.post("/{lote_id}/notas", status_code=201)
def adicionar_nota(lote_id: int, dados: NotaEntrada, request: Request, db: Session = Depends(get_db),
                   u: Usuario = Depends(deps.usuario_liberado)) -> dict:
    _lote(db, lote_id, u)
    n = Nota(entidade="LOTE", entidade_id=lote_id, texto=dados.texto.strip(), usuario_id=u.id)
    db.add(n)
    db.flush()
    auditoria.registrar(db, "NOTA_CRIADA", usuario_id=u.id, entidade="lote", entidade_id=lote_id,
                        depois={"nota_id": n.id}, ip=deps.ip_cliente(request))
    db.commit()
    return {"id": n.id, "texto": n.texto, "usuario": u.nome, "criado_em": n.criado_em.isoformat()}
