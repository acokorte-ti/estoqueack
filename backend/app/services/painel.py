"""T03 Painel (pendências por perfil, atrasos, divergências com o Mega) e T16 Conciliação mínima (só leitura).

T16 mínima (decisão do Eduardo de 2026-11-04): código Mega × soma dos lotes do Estoque Mega (ITU/ITU), destacando
diferença acima de DIVERGENCIA_MEGA_KG. O tratamento (ajustar, marcar como explicada) fica para a F1.1.
"""
from __future__ import annotations

from collections import Counter
from datetime import timedelta
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import CadastroSa, Cop, Destinacao, ItemMP, Lote, MegaSaldo, Movimento, SolicitacaoCorte, Usuario

from . import cops as svc_cops
from . import sas as svc_sas
from . import solicitacoes as svc_sol
from . import sync_mega
from .base import agora, hoje, parametro

ITENS_POR_PENDENCIA = 10


# ---------------- T16 mínima ----------------

def conciliacao(db: Session, *, somente_divergentes: bool = False) -> dict[str, Any]:
    limite = parametro(db, "DIVERGENCIA_MEGA_KG")
    lotes = dict(db.execute(
        select(ItemMP.codigo_mega, func.coalesce(func.sum(Lote.saldo_kg), 0)).join(Lote, Lote.item_mp_id == ItemMP.id)
        .where(Lote.planta_fiscal == "ITU", Lote.local_fisico == "ITU", ItemMP.codigo_mega.is_not(None))
        .group_by(ItemMP.codigo_mega)).all())
    n_lotes = dict(db.execute(
        select(ItemMP.codigo_mega, func.count(Lote.id)).join(Lote, Lote.item_mp_id == ItemMP.id)
        .where(Lote.planta_fiscal == "ITU", Lote.local_fisico == "ITU", Lote.saldo_kg > 0,
               ItemMP.codigo_mega.is_not(None)).group_by(ItemMP.codigo_mega)).all())
    catalogo = {c: d for c, d in db.execute(select(ItemMP.codigo_mega, ItemMP.descricao)
                                            .where(ItemMP.codigo_mega.is_not(None)))}
    mega = {m.codigo: m for m in db.scalars(select(MegaSaldo).where(MegaSaldo.codigo.in_(list(catalogo))))} \
        if catalogo else {}
    itens = []
    for cod in sorted(set(catalogo) & (set(mega) | set(lotes))):
        sm = float(mega[cod].saldo_kg) if cod in mega else 0.0
        sl = float(lotes.get(cod) or 0)
        if abs(sm) < 0.0005 and abs(sl) < 0.0005:
            continue
        dif = round(sm - sl, 3)
        status = "OK" if abs(dif) <= limite else ("MEGA_MAIOR" if dif > 0 else "MEGA_MENOR")
        if somente_divergentes and status == "OK":
            continue
        itens.append({"codigo": cod, "descricao": (mega[cod].descricao if cod in mega else None) or catalogo[cod],
                      "saldo_mega_kg": round(sm, 3), "soma_lotes_kg": round(sl, 3), "diferenca_kg": dif,
                      "status": status, "lotes": int(n_lotes.get(cod) or 0)})
    itens.sort(key=lambda x: (x["status"] == "OK", -abs(x["diferenca_kg"]), x["codigo"]))
    u = sync_mega.ultima(db, "ESTOQUE")
    cont = Counter(x["status"] for x in itens)
    return {"limite_kg": limite,
            "ultima_sincronizacao": u.terminado_em.isoformat() if u and u.terminado_em else None,
            "totais": {"codigos": len(itens), "ok": cont["OK"], "mega_maior": cont["MEGA_MAIOR"],
                       "mega_menor": cont["MEGA_MENOR"],
                       "saldo_mega_kg": round(sum(x["saldo_mega_kg"] for x in itens), 3),
                       "soma_lotes_kg": round(sum(x["soma_lotes_kg"] for x in itens), 3)},
            "itens": itens}


def divergencias_mega(db: Session) -> int:
    t = conciliacao(db, somente_divergentes=True)["totais"]
    return t["mega_maior"] + t["mega_menor"]


# ---------------- T03 pendências ----------------

def _p(codigo: str, titulo: str, itens: list[dict], link: str, *, nivel: str = "NORMAL",
       quantidade: int | None = None) -> dict[str, Any]:
    return {"codigo": codigo, "titulo": titulo, "quantidade": len(itens) if quantidade is None else quantidade,
            "nivel": nivel if (quantidade if quantidade is not None else len(itens)) else "NORMAL", "link": link,
            "itens": itens[:ITENS_POR_PENDENCIA]}


def _cops_segurando(db: Session) -> list[dict]:
    out = []
    for c in db.scalars(select(Cop).where(Cop.situacao == "FECHADO").order_by(Cop.fechado_em)):
        pend = [i for i in c.itens if (s := svc_cops._sa_do_item(db, i)) is None or s.situacao != "CONFIRMADO"]
        if pend:
            out.append({"cop_id": c.id, "cop": c.numero, "sas_pendentes": len(pend), "itens": len(c.itens),
                        "fechado_em": c.fechado_em.isoformat() if c.fechado_em else None})
    return out


def _sol_item(db: Session, s: SolicitacaoCorte) -> dict:
    d = svc_sol.resumo(db, s)
    return {k: d[k] for k in ("id", "numero", "op", "cliente", "quantidade", "prazo", "situacao", "atraso",
                              "dias_em_aberto")} | {"material": f"{d['lote']['liga']} {d['lote']['bitola']}",
                                                    "conteiner": d["lote"]["conteiner"]}


def pendencias_itu(db: Session) -> list[dict]:
    segurando = _cops_segurando(db)
    transito = [svc_cops.cop_dict(db, c, com_itens=False) for c in svc_cops.listar(db, ["ENVIADO", "RECEBIDO_PARCIAL"])]
    inteiras = [_sol_item(db, s) for s in db.scalars(select(SolicitacaoCorte).where(
        SolicitacaoCorte.situacao == "AGUARDANDO_CORTE_ITU").order_by(SolicitacaoCorte.id))]
    abertos = list(db.scalars(select(CadastroSa).where(CadastroSa.situacao != "CONFIRMADO",
                                                       CadastroSa.origem != "CARGA").order_by(CadastroSa.criado_em)))
    atrasados = [{"id": s.id, "op": s.op, "situacao": s.situacao, "sa_codigo": s.sa_codigo,
                  "criado_em": s.criado_em.isoformat()} for s in abertos if svc_sas.atrasado(db, s)]
    insuf = [_sol_item(db, s) for s in db.scalars(select(SolicitacaoCorte).where(
        SolicitacaoCorte.situacao == "MATERIAL_INSUFICIENTE").order_by(SolicitacaoCorte.id))]
    return [
        _p("SA_SEGURANDO_COP", "SAs pendentes segurando COP no RJ", segurando, "/sa", nivel="ALERTA"),
        _p("COP_EM_TRANSITO", "COPs em trânsito para receber", transito, "/recebimentos"),
        _p("PECA_INTEIRA_AGUARDANDO_CORTE", "Peças inteiras aguardando corte em Itu", inteiras, "/cortes-itu"),
        _p("SA_SEM_CONFIRMACAO", "SAs sem confirmação no Mega há mais do prazo", atrasados, "/sa", nivel="ALERTA"),
        _p("MATERIAL_INSUFICIENTE", "Solicitações com material insuficiente (trocar lote ou cancelar)", insuf,
           "/solicitacoes?situacao=MATERIAL_INSUFICIENTE", nivel="ALERTA"),
    ]


def pendencias_rj(db: Session) -> list[dict]:
    fila = [_sol_item(db, s) for s in svc_sol.fila_rj(db)]
    atrasadas = [x for x in fila if x["atraso"] == "ATRASADO"]
    aguardando_sa = _cops_segurando(db)
    aguardando_nf = [svc_cops.cop_dict(db, c, com_itens=False) for c in svc_cops.listar(db, ["FECHADO"])
                     if svc_cops.situacao_exibida(db, c) == "AGUARDANDO_NF"]
    prontos = [svc_cops.pronto_dict(l) for l in svc_cops.cortes_prontos(db)]
    abertos = [svc_cops.cop_dict(db, c, com_itens=False) for c in svc_cops.listar(db, ["ABERTO"])]
    return [
        _p("FILA_CORTE", "Fila de corte (por prazo)", fila, "/fila-rj",
           nivel="ALERTA" if atrasadas else "NORMAL"),
        _p("FILA_CORTE_ATRASADA", "Solicitações atrasadas (> 15 dias)", atrasadas, "/fila-rj", nivel="ALERTA"),
        _p("CORTES_FORA_DE_COP", "Cortes prontos fora de COP", prontos, "/cops"),
        _p("COP_ABERTO", "COPs abertos", abertos, "/cops"),
        _p("COP_AGUARDANDO_SA", "Cortes aguardando SA de Itu", aguardando_sa, "/cops"),
        _p("COP_AGUARDANDO_NF", "COPs com SA pronto aguardando NF para enviar", aguardando_nf, "/cops", nivel="ALERTA"),
    ]


def pendencias_analise(db: Session) -> list[dict]:
    dias = int(parametro(db, "AVISO_RESERVA_DIAS"))
    vencendo = []
    for d in db.scalars(select(Destinacao).where(Destinacao.ativa.is_(True), Destinacao.validade.is_not(None),
                                                 Destinacao.validade >= hoje(),
                                                 Destinacao.validade <= hoje() + timedelta(days=dias))
                        .order_by(Destinacao.validade)):
        lote = db.get(Lote, d.lote_id)
        vencendo.append({"destinacao_id": d.id, "lote_id": d.lote_id, "lote": lote.codigo if lote else None,
                         "tipo": d.tipo, "descricao": d.descricao, "kg": d.kg, "validade": d.validade.isoformat()})
    conc = conciliacao(db, somente_divergentes=True)
    excecoes = excecoes_da_semana(db)
    return [
        _p("RESERVA_VENCENDO", f"Reservas e restrições vencendo em {dias} dias", vencendo, "/reservas"),
        _p("DIVERGENCIA_MEGA", "Códigos com divergência com o Mega", conc["itens"], "/conciliacao", nivel="ALERTA"),
        _p("EXCECOES_SEMANA", "Exceções de tolerância justificadas (7 dias)", excecoes, "/relatorios/excecoes"),
    ]


def excecoes_da_semana(db: Session, dias: int = 7) -> list[dict]:
    desde = agora() - timedelta(days=dias)
    out = []
    for m, nome in db.execute(select(Movimento, Usuario.nome).outerjoin(Usuario, Movimento.usuario_id == Usuario.id)
                              .where(Movimento.criado_em >= desde,
                                     or_(Movimento.confirmacoes.is_not(None),
                                         Movimento.tipo.in_(("AJUSTE_INVENTARIO", "ESTORNO"))))
                              .order_by(Movimento.id.desc())):
        if m.confirmacoes is None and m.tipo not in ("AJUSTE_INVENTARIO", "ESTORNO"):
            continue
        out.append({"movimento_id": m.id, "lote_id": m.lote_id, "tipo": m.tipo, "kg": m.kg, "op": m.op,
                    "codigos": sorted((m.confirmacoes or {}).keys()), "justificativa": m.justificativa,
                    "usuario": nome, "criado_em": m.criado_em.isoformat()})
    return out


def atrasos(db: Session) -> dict[str, int]:
    c = Counter()
    for s in db.scalars(select(SolicitacaoCorte).where(SolicitacaoCorte.situacao.in_(
            ("ENVIADA", "CORTADA_PARCIAL", "MATERIAL_INSUFICIENTE")))):
        _, f = svc_sol.faixa_atraso(db, s)
        if f:
            c[f] += 1
    return {"NORMAL": c["NORMAL"], "ATENCAO": c["ATENCAO"], "ATRASADO": c["ATRASADO"]}


def pendencias(db: Session, usuario: Usuario) -> dict[str, Any]:
    grupos: dict[str, list[dict]] = {}
    p = usuario.perfil
    if p in ("ESTOQUE", "ADMIN"):
        grupos["ESTOQUE"] = pendencias_itu(db)
    if p in ("OPERACAO_RJ", "ADMIN"):
        grupos["OPERACAO_RJ"] = pendencias_rj(db)
    if p in ("ANALISE", "ADMIN"):
        grupos["ANALISE"] = pendencias_analise(db)
    u = sync_mega.ultima(db, "ESTOQUE", None)
    ok = sync_mega.ultima(db, "ESTOQUE")
    return {"perfil": p, "grupos": grupos, "atrasos": atrasos(db),
            "divergencias_mega": {"quantidade": divergencias_mega(db) if p != "OPERACAO_RJ" else None,
                                  "limite_kg": parametro(db, "DIVERGENCIA_MEGA_KG")},
            "ultima_sincronizacao": {"terminado_em": ok.terminado_em.isoformat() if ok and ok.terminado_em else None,
                                     "situacao_ultima_tentativa": u.situacao if u else None}}
