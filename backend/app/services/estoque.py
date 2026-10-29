"""Consultas de estoque por lote (T04/T05). Somente leitura."""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models import Conteiner, Destinacao, ItemMP, Liga, Lote, Movimento, Nota, Usuario

BALDE = {("ITU", "ITU"): "ESTOQUE_MEGA", ("RJ", "RJ"): "RJ_NO_RIO", ("RJ", "ITU"): "RJ_EM_ITU"}
BALDE_INV = {v: k for k, v in BALDE.items()}

TIPO_MOV_DESCRICAO = {
    "SALDO_INICIAL": "Saldo inicial (carga)", "ENTRADA": "Entrada", "SAIDA_CORTE_RJ": "Corte no RJ",
    "ENVIO_ITU": "Envio para Itu", "RECEBIMENTO_ITU": "Recebimento em Itu", "CONSUMO_OP": "Consumo em OP",
    "GERA_SOBRA": "Sobra gerada", "GERA_RETO": "RETO gerado", "AJUSTE_INVENTARIO": "Ajuste de inventário",
    "ESTORNO": "Estorno", "SUCATA": "Sucata",
}


def bitola(item: ItemMP) -> str:
    if item.formato == "RETO":
        return "RETO"
    if item.formato == "REDONDO" and item.diametro:
        return f"Ø{item.diametro:g}"
    if item.espessura and item.largura:
        return f"{item.espessura:g}X{item.largura:g}"
    return item.formato


def _reservas(db: Session, ids: list[int]) -> dict[int, float]:
    if not ids:
        return {}
    hoje = date.today()
    q = (select(Destinacao.lote_id, func.coalesce(func.sum(Destinacao.kg), 0))
         .where(Destinacao.lote_id.in_(ids), Destinacao.ativa.is_(True), Destinacao.tipo == "RESERVA",
                or_(Destinacao.validade.is_(None), Destinacao.validade >= hoje))
         .group_by(Destinacao.lote_id))
    return {i: float(k) for i, k in db.execute(q)}


def _com_destinacao(db: Session, ids: list[int]) -> set[int]:
    if not ids:
        return set()
    hoje = date.today()
    return set(db.scalars(select(Destinacao.lote_id).where(
        Destinacao.lote_id.in_(ids), Destinacao.ativa.is_(True),
        or_(Destinacao.validade.is_(None), Destinacao.validade >= hoje))))


def _com_nota(db: Session, ids: list[int]) -> set[int]:
    if not ids:
        return set()
    return set(db.scalars(select(Nota.entidade_id).where(Nota.entidade == "LOTE", Nota.entidade_id.in_(ids))))


def raiz(db: Session, lote: Lote) -> Lote:
    atual, vistos = lote, set()
    while atual.lote_pai_id is not None and atual.id not in vistos:
        vistos.add(atual.id)
        atual = db.get(Lote, atual.lote_pai_id)
    return atual


def consulta_lotes(db: Session, f: dict[str, Any]):
    q = (select(Lote).join(ItemMP, Lote.item_mp_id == ItemMP.id).join(Liga, ItemMP.liga_id == Liga.id)
         .outerjoin(Conteiner, Lote.conteiner_id == Conteiner.id)
         .options(joinedload(Lote.item).joinedload(ItemMP.liga), joinedload(Lote.conteiner)))
    if f.get("estoque"):
        pf, lf = BALDE_INV[f["estoque"]]
        q = q.where(Lote.planta_fiscal == pf, Lote.local_fisico == lf)
    if f.get("liga"):
        q = q.where(Liga.codigo == f["liga"].strip().upper())
    if f.get("formato"):
        q = q.where(ItemMP.formato == f["formato"])
    for campo in ("espessura", "largura", "diametro"):
        col = getattr(ItemMP, campo)
        if f.get(f"{campo}_de") is not None:
            q = q.where(col >= f[f"{campo}_de"])
        if f.get(f"{campo}_ate") is not None:
            q = q.where(col <= f[f"{campo}_ate"])
    if f.get("conteiner"):
        q = q.where(Conteiner.codigo == f["conteiner"].strip().upper())
    if f.get("codigo_mega") is not None:
        q = q.where(ItemMP.codigo_mega == f["codigo_mega"])
    if f.get("com_saldo", True):
        q = q.where(Lote.saldo_kg > 0)
    if f.get("origem_nao_identificada"):
        q = q.where(Lote.origem_identificada.is_(False))
    if f.get("busca"):
        t = f"%{f['busca'].strip()}%"
        q = q.where(or_(Lote.codigo.ilike(t), Conteiner.codigo.ilike(t), ItemMP.descricao.ilike(t)))
    q = q.order_by(Liga.codigo, ItemMP.formato, ItemMP.espessura, ItemMP.largura, ItemMP.diametro, Lote.codigo)
    lotes = list(db.scalars(q).unique())
    if f.get("com_destinacao"):
        com = _com_destinacao(db, [l.id for l in lotes])
        lotes = [l for l in lotes if l.id in com]
    return lotes


def lote_resumo(db: Session, lotes: list[Lote]) -> list[dict]:
    ids = [l.id for l in lotes]
    res, dest, notas = _reservas(db, ids), _com_destinacao(db, ids), _com_nota(db, ids)
    saida = []
    for l in lotes:
        reservado = round(min(res.get(l.id, 0.0), l.saldo_kg), 3)
        origem = None
        if l.lote_pai_id is not None:
            r = raiz(db, l)
            origem = {"lote": r.codigo, "conteiner": r.conteiner.codigo if r.conteiner else None,
                      "bitola": bitola(r.item)}
        saida.append({
            "id": l.id, "codigo": l.codigo, "conteiner": l.conteiner.codigo if l.conteiner else None,
            "liga": l.item.liga.codigo, "formato": l.item.formato, "bitola": bitola(l.item),
            "descricao": l.item.descricao, "codigo_mega": l.item.codigo_mega,
            "estoque": BALDE.get((l.planta_fiscal, l.local_fisico)), "tipo": l.tipo,
            "saldo_kg": round(l.saldo_kg, 3), "reservado_kg": reservado,
            "disponivel_kg": round(l.saldo_kg - reservado, 3), "origem": origem,
            "indicadores": {"destinacao": l.id in dest, "nota": l.id in notas,
                            "origem_nao_identificada": not l.origem_identificada},
        })
    return saida


def agrupado(itens: list[dict]) -> list[dict]:
    g: dict[tuple, dict] = {}
    for i in itens:
        k = (i["liga"], i["formato"], i["bitola"])
        a = g.setdefault(k, {"liga": k[0], "formato": k[1], "bitola": k[2], "lotes": 0, "saldo_kg": 0.0,
                             "reservado_kg": 0.0, "disponivel_kg": 0.0, "por_estoque": defaultdict(float)})
        a["lotes"] += 1
        for c in ("saldo_kg", "reservado_kg", "disponivel_kg"):
            a[c] = round(a[c] + i[c], 3)
        a["por_estoque"][i["estoque"]] = round(a["por_estoque"][i["estoque"]] + i["saldo_kg"], 3)
    for a in g.values():
        a["por_estoque"] = {b: a["por_estoque"].get(b, 0.0) for b in BALDE.values()}
    return list(g.values())


def arvore(db: Session, lote: Lote) -> dict:
    r = raiz(db, lote)
    filhos: dict[int | None, list[Lote]] = defaultdict(list)
    # carrega a família inteira (BFS a partir da raiz)
    fila, vistos = [r.id], {r.id}
    while fila:
        atual = fila.pop()
        for f in db.scalars(select(Lote).where(Lote.lote_pai_id == atual)):
            if f.id not in vistos:
                vistos.add(f.id)
                filhos[atual].append(f)
                fila.append(f.id)

    def no(l: Lote) -> dict:
        return {"id": l.id, "codigo": l.codigo, "tipo": l.tipo, "bitola": bitola(l.item),
                "conteiner": l.conteiner.codigo if l.conteiner else None, "saldo_kg": round(l.saldo_kg, 3),
                "estoque": BALDE.get((l.planta_fiscal, l.local_fisico)),
                "filhos": [no(f) for f in sorted(filhos[l.id], key=lambda x: x.id)]}
    return {"raiz": no(r), "atual_id": lote.id}


def movimentos(db: Session, lote_id: int) -> list[dict]:
    movs = db.execute(select(Movimento, Usuario.nome).outerjoin(Usuario, Movimento.usuario_id == Usuario.id)
                      .where(Movimento.lote_id == lote_id)
                      .order_by(func.coalesce(Movimento.data_referencia, func.date(Movimento.criado_em)),
                                Movimento.id)).all()
    saldo, out = 0.0, []
    for m, nome in movs:
        saldo = round(saldo + m.kg, 3)
        out.append({"id": m.id, "data": (m.data_referencia or m.criado_em.date()).isoformat(), "tipo": m.tipo,
                    "tipo_descricao": TIPO_MOV_DESCRICAO.get(m.tipo, m.tipo), "kg": round(m.kg, 3),
                    "saldo_apos_kg": saldo, "op": m.op, "cop": m.cop_numero, "sa": m.sa_codigo,
                    "documento": m.documento, "usuario": nome, "justificativa": m.justificativa,
                    "estorno_de": m.estorno_de_id})
    return out
