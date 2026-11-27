"""T28 Histórico de cortes do RJ, só Admin (spec v3.26, contrato §16.8).

Cada linha é um corte registrado no RJ (`liberacao_corte`): os do sistema (T10) e os que vieram do Controle de Corte
na carga. O "log" de cada corte são os movimentos ligados a ele (saída do corte, estorno, ajuste da correção no COP) e
as correções feitas no COP (auditoria `COP_ITEM_EDITADO`). Só leitura.
"""
from __future__ import annotations

import unicodedata
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Auditoria, CopItem, ItemMP, LiberacaoCorte, Lote, Movimento, SolicitacaoCorte, Usuario

from .base import NaoEncontrado
from .estoque import TIPO_MOV_DESCRICAO, bitola

SITUACAO_NOME = {"CORTE_PRONTO": "Corte pronto (fora de COP)", "SEM_COP": "Sem COP (concluído)", "EM_COP": "No COP",
                 "EM_TRANSITO": "Enviado a Itu", "RECEBIDO": "Recebido em Itu", "ESTORNADO": "Estornado"}
ORIGEM_NOME = {"SISTEMA": "Sistema", "PLANILHA": "Planilha (Controle de Corte)"}


def _sem_acento(t: str) -> str:
    return unicodedata.normalize("NFD", t).encode("ascii", "ignore").decode().lower()


def _situacao(lib: LiberacaoCorte) -> str:
    if lib.estornada:
        return "ESTORNADO"
    if lib.cop_item is None:
        # mesma regra dos "cortes prontos" do COP: corte histórico da carga liberado sem número de COP, com a
        # solicitação já concluída ou em trânsito, não espera COP
        prontas = ("CORTADA", "CORTADA_PARCIAL", "MATERIAL_INSUFICIENTE")
        return "CORTE_PRONTO" if lib.solicitacao.situacao in prontas else "SEM_COP"
    return lib.cop_item.situacao


def _edicoes_cop(db: Session) -> dict[int, list]:
    """cop_item.id → auditorias COP_ITEM_EDITADO (a recarga reinicia os ids: o chamador filtra pela data do corte)."""
    out: dict[int, list] = {}
    for a in db.scalars(select(Auditoria).where(Auditoria.acao == "COP_ITEM_EDITADO").order_by(Auditoria.id)):
        item = (a.depois or {}).get("item")
        if isinstance(item, int):
            out.setdefault(item, []).append(a)
    return out


def _edicoes_do_corte(lib: LiberacaoCorte, edicoes: dict[int, list]) -> list:
    if lib.cop_item is None:
        return []
    return [a for a in edicoes.get(lib.cop_item.id, []) if a.quando >= lib.criado_em]


def _linha(lib: LiberacaoCorte, nomes: dict[int, str], edicoes: dict[int, list]) -> dict[str, Any]:
    sol, lote = lib.solicitacao, lib.lote
    item = lote.item
    previsto = (round(float(sol.peso_previsto_kg) * lib.pecas / sol.quantidade, 3)
                if sol.peso_previsto_kg and sol.quantidade else None)
    real = round(float(lib.peso_real_kg), 3)
    cop = lib.cop_item.cop if lib.cop_item else None
    origem = "PLANILHA" if lib.origem_ref else "SISTEMA"
    situacao = _situacao(lib)
    return {
        "id": lib.id, "data_corte": lib.data_corte.isoformat(), "registrado_em": lib.criado_em.isoformat(),
        "registrado_por": nomes.get(lib.usuario_id) if lib.usuario_id else None,
        "origem": origem, "origem_nome": ORIGEM_NOME[origem], "origem_ref": lib.origem_ref,
        "solicitacao_id": sol.id, "solicitacao": f"S-{sol.id:06d}", "op": sol.op, "cliente": sol.cliente,
        "item_descricao": sol.item_descricao, "modo": sol.modo,
        "lote_id": lote.id, "lote": lote.codigo, "liga": item.liga.codigo, "bitola": bitola(item),
        "conteiner": lote.conteiner.codigo if lote.conteiner else None,
        "lote_trocado": lote.id != sol.lote_id,
        "pecas": lib.pecas, "peso_real_kg": real, "previsto_kg": previsto,
        "diferenca_pct": round((real - previsto) / previsto * 100, 1) if previsto else None,
        "comprimento_barra_mm": lib.comprimento_barra_mm, "observacao": lib.observacao,
        "cop": cop.numero if cop else None, "cop_id": cop.id if cop else None,
        "situacao": situacao, "situacao_nome": SITUACAO_NOME.get(situacao, situacao),
        "estornado": lib.estornada, "corrigido": bool(_edicoes_do_corte(lib, edicoes)),
    }


def _consulta(db: Session):
    return (select(LiberacaoCorte)
            .options(selectinload(LiberacaoCorte.solicitacao),
                     selectinload(LiberacaoCorte.lote).selectinload(Lote.item).selectinload(ItemMP.liga),
                     selectinload(LiberacaoCorte.lote).selectinload(Lote.conteiner),
                     selectinload(LiberacaoCorte.cop_item).selectinload(CopItem.cop))
            .order_by(LiberacaoCorte.data_corte.desc(), LiberacaoCorte.id.desc()))


def listar(db: Session, f: dict[str, Any]) -> dict[str, Any]:
    q = _consulta(db)
    de, ate = f.get("de"), f.get("ate")
    if de:
        q = q.where(LiberacaoCorte.data_corte >= de)
    if ate:
        q = q.where(LiberacaoCorte.data_corte <= ate)
    if f.get("op"):
        da_op = select(SolicitacaoCorte.id).where(SolicitacaoCorte.op == f["op"])
        q = q.where(LiberacaoCorte.solicitacao_id.in_(da_op))
    if f.get("origem") == "PLANILHA":
        q = q.where(LiberacaoCorte.origem_ref.is_not(None))
    elif f.get("origem") == "SISTEMA":
        q = q.where(LiberacaoCorte.origem_ref.is_(None))
    if not f.get("estornados", True):
        q = q.where(LiberacaoCorte.estornada.is_(False))
    nomes = dict(db.execute(select(Usuario.id, Usuario.nome)).all())
    edicoes = _edicoes_cop(db)
    linhas = [_linha(lib, nomes, edicoes) for lib in db.scalars(q)]
    termo = _sem_acento((f.get("busca") or "").strip())
    if termo:
        linhas = [x for x in linhas if termo in _sem_acento(" ".join(str(v) for v in (
            x["op"], x["cliente"], x["item_descricao"], x["liga"], x["bitola"], f"{x['liga']} {x['bitola']}",
            x["conteiner"], x["lote"], x["registrado_por"], x["cop"]) if v is not None))]
    if f.get("situacao"):
        linhas = [x for x in linhas if x["situacao"] in f["situacao"]]
    validos = [x for x in linhas if not x["estornado"]]
    totais = {"cortes": len(validos), "pecas": sum(x["pecas"] for x in validos),
              "peso_real_kg": round(sum(x["peso_real_kg"] for x in validos), 3),
              "estornados": len(linhas) - len(validos),
              "sistema": sum(1 for x in validos if x["origem"] == "SISTEMA"),
              "planilha": sum(1 for x in validos if x["origem"] == "PLANILHA")}
    datas = [x["data_corte"] for x in linhas]
    return {"itens": linhas, "total": len(linhas), "totais": totais,
            "periodo": {"de": min(datas), "ate": max(datas)} if datas else None}


def detalhe(db: Session, lib_id: int) -> dict[str, Any]:
    lib = db.scalar(_consulta(db).where(LiberacaoCorte.id == lib_id))
    if lib is None:
        raise NaoEncontrado("Corte não encontrado.")
    nomes = dict(db.execute(select(Usuario.id, Usuario.nome)).all())
    edicoes = _edicoes_do_corte(lib, _edicoes_cop(db))
    d = _linha(lib, nomes, {lib.cop_item.id: edicoes} if lib.cop_item else {})
    movs = db.scalars(select(Movimento).where(Movimento.liberacao_id == lib.id).order_by(Movimento.id)).all()
    ids = {m.lote_id for m in movs}
    lotes = {l.id: l.codigo for l in db.scalars(select(Lote).where(Lote.id.in_(ids)))} if ids else {}
    d["confirmacoes"] = lib.confirmacoes or {}
    d["movimentos"] = [{"id": m.id, "tipo": m.tipo, "tipo_descricao": TIPO_MOV_DESCRICAO.get(m.tipo, m.tipo),
                        "kg": round(float(m.kg), 3), "lote": lotes.get(m.lote_id), "lote_id": m.lote_id,
                        "data": (m.data_referencia or m.criado_em.date()).isoformat(),
                        "registrado_em": m.criado_em.isoformat(),
                        "usuario": nomes.get(m.usuario_id) if m.usuario_id else None,
                        "justificativa": m.justificativa, "da_carga": m.origem_ref is not None} for m in movs]
    d["correcoes"] = [{"quando": a.quando.isoformat(), "usuario": nomes.get(a.usuario_id) if a.usuario_id else None,
                       "antes": {k: (a.antes or {}).get(k) for k in ("op", "cliente", "pecas", "peso_kg")},
                       "depois": {k: (a.depois or {}).get(k) for k in ("op", "cliente", "pecas", "peso_kg")},
                       "motivo": (a.depois or {}).get("motivo")} for a in edicoes]
    return d
