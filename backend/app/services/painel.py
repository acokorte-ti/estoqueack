"""T03 Painel (pendências por perfil, atrasos, divergências com o Mega) e T16 Conciliação mínima (só leitura).

T16 mínima (decisão do Eduardo de 2026-11-04): código Mega × soma dos lotes do Estoque Mega (ITU/ITU), destacando
diferença acima de DIVERGENCIA_MEGA_KG. O tratamento (ajustar, marcar como explicada) fica para a F1.1.
"""
from __future__ import annotations

from collections import Counter
from datetime import timedelta
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import (CadastroSa, Cop, CopItem, Destinacao, ItemMP, Lote, MegaSaldo, Movimento, SolicitacaoCorte,
                        Usuario)

from . import cops as svc_cops
from . import entradas_mega, peso_real
from . import estoque as svc_estoque
from . import sas as svc_sas
from . import solicitacoes as svc_sol
from . import sync_mega
from .base import agora, hoje, parametro

ITENS_POR_PENDENCIA = 10


# ---------------- T16 mínima ----------------

def conciliacao(db: Session, *, somente_divergentes: bool = False) -> dict[str, Any]:
    limite = parametro(db, "DIVERGENCIA_MEGA_KG")
    lotes, n_lotes = svc_estoque.soma_lotes_por_codigo(db)
    catalogo = {c: d for c, d in db.execute(select(ItemMP.codigo_mega, ItemMP.descricao)
                                            .where(ItemMP.codigo_mega.is_not(None)))}
    mega = {m.codigo: m for m in db.scalars(select(MegaSaldo).where(MegaSaldo.codigo.in_(list(catalogo))))} \
        if catalogo else {}
    explic = entradas_mega.explicacoes_por_codigo(db)
    itens = []
    for cod in sorted(set(catalogo) & (set(mega) | set(lotes))):
        sm = float(mega[cod].saldo_kg) if cod in mega else 0.0
        sl = float(lotes.get(cod) or 0)
        if abs(sm) < 0.0005 and abs(sl) < 0.0005:
            continue
        dif = round(sm - sl, 3)
        ex = explic.get(cod, [])
        explicada = round(sum(e["kg"] for e in ex), 3)
        nao_expl = round(dif - explicada, 3)          # vermelho só para a diferença NÃO explicada na T15
        status = "OK" if abs(nao_expl) <= limite else ("MEGA_MAIOR" if nao_expl > 0 else "MEGA_MENOR")
        itens.append({"codigo": cod, "descricao": (mega[cod].descricao if cod in mega else None) or catalogo[cod],
                      "saldo_mega_kg": round(sm, 3), "soma_lotes_kg": round(sl, 3), "diferenca_kg": dif,
                      "status": status, "lotes": int(n_lotes.get(cod) or 0),
                      "explicada_t15_kg": explicada, "diferenca_nao_explicada_kg": nao_expl,
                      "explicada_na_t15": bool(ex), "explicacoes": ex})
    itens.sort(key=lambda x: (x["status"] == "OK", -abs(x["diferenca_kg"]), x["codigo"]))
    u = sync_mega.ultima(db, "ESTOQUE")
    cont = Counter(x["status"] for x in itens)
    # R065(2): os totais são sempre de TODOS os códigos; `somente_divergentes` filtra só a lista
    totais = {"codigos": len(itens), "ok": cont["OK"], "mega_maior": cont["MEGA_MAIOR"],
              "mega_menor": cont["MEGA_MENOR"],
              "saldo_mega_kg": round(sum(x["saldo_mega_kg"] for x in itens), 3),
              "soma_lotes_kg": round(sum(x["soma_lotes_kg"] for x in itens), 3)}
    if somente_divergentes:
        itens = [x for x in itens if x["status"] != "OK"]
    return {"limite_kg": limite,
            "ultima_sincronizacao": u.terminado_em.isoformat() if u and u.terminado_em else None,
            "totais": totais, "itens": itens}


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
    q = select(Cop).options(selectinload(Cop.itens)).where(Cop.situacao == "FECHADO").order_by(Cop.fechado_em)
    for c in db.scalars(q):
        # spec v3.16: o COP fica "segurando" até ter SA confirmado e R$/kg do precificador em todos os itens
        sem_sa, sem_rs = svc_sas.pendencias_nf(db, list(c.itens))
        if sem_sa or sem_rs:
            out.append({"cop_id": c.id, "cop": c.numero, "sas_pendentes": len(sem_sa),
                        "precificador_pendentes": len(sem_rs), "itens": len(c.itens),
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
    # R058/R060 (spec v3.11 §2.2 passo 7): só as pendências do peso real não encerradas, com os dias desde o
    # recebimento do COP; os campos da pendência (peso_real.itens) por cima do resumo da solicitação
    pend = {x["solicitacao_id"]: x for x in peso_real.itens(db)}
    inteiras = [_sol_item(db, s) | pend[s.id] | {"dias_desde_recebimento": pend[s.id]["dias"]}
                for s in db.scalars(select(SolicitacaoCorte).where(
                    SolicitacaoCorte.id.in_(list(pend))).order_by(SolicitacaoCorte.id))]
    inteiras.sort(key=lambda x: (x["recebido_em"], x["id"]))
    limite_peso = int(parametro(db, "PENDENCIA_PESO_REAL_DIAS"))
    abertos = list(db.scalars(select(CadastroSa).where(CadastroSa.situacao != "CONFIRMADO",
                                                       CadastroSa.origem != "CARGA").order_by(CadastroSa.criado_em)))
    atrasados = [{"id": s.id, "op": s.op, "situacao": s.situacao, "sa_codigo": s.sa_codigo,
                  "criado_em": s.criado_em.isoformat()} for s in abertos if svc_sas.atrasado(db, s)]
    insuf = [_sol_item(db, s) for s in db.scalars(select(SolicitacaoCorte).where(
        SolicitacaoCorte.situacao == "MATERIAL_INSUFICIENTE").order_by(SolicitacaoCorte.id))]
    entradas = [{"id": p["id"], "codigo": p["codigo"], "descricao": p["descricao"], "diferenca_kg": p["diferenca_kg"]}
                for p in entradas_mega.listar(db)["itens"]]
    return [
        _p("ENTRADA_MEGA_A_CLASSIFICAR", "Entradas Mega a classificar", entradas, "/entradas-mega", nivel="ALERTA"),
        _p("SA_SEGURANDO_COP", "SAs pendentes segurando COP no RJ", segurando, "/sa", nivel="ALERTA"),
        _p("COP_EM_TRANSITO", "COPs em trânsito para receber", transito, "/recebimentos"),
        _p("PECA_INTEIRA_AGUARDANDO_CORTE", "Peças inteiras do RJ aguardando peso real", inteiras, "/corte-itu",
           nivel="ALERTA" if any(x["vencida"] for x in inteiras) else "NORMAL")
        | {"limite_dias": limite_peso, "vencidas": sum(1 for x in inteiras if x["vencida"])},
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
    # códigos dos lotes numa consulta só (antes: um db.get por reserva)
    codigos = dict(db.execute(select(Lote.id, Lote.codigo).join(Destinacao, Destinacao.lote_id == Lote.id)
                              .where(Destinacao.ativa.is_(True))).all())
    for d in db.scalars(select(Destinacao).where(Destinacao.ativa.is_(True), Destinacao.validade.is_not(None),
                                                 Destinacao.validade >= hoje(),
                                                 Destinacao.validade <= hoje() + timedelta(days=dias))
                        .order_by(Destinacao.validade)):
        lote = codigos.get(d.lote_id)
        vencendo.append({"destinacao_id": d.id, "lote_id": d.lote_id, "lote": lote,
                         "tipo": d.tipo, "descricao": d.descricao, "kg": d.kg, "validade": d.validade.isoformat()})
    conc = conciliacao(db, somente_divergentes=True)
    excecoes = excecoes_da_semana(db)
    return [
        _p("RESERVA_VENCENDO", f"Reservas e restrições vencendo em {dias} dias", vencendo, "/reservas"),
        _p("DIVERGENCIA_MEGA", "Códigos com divergência com o Mega", conc["itens"], "/conciliacao", nivel="ALERTA"),
        _p("EXCECOES_SEMANA", "Exceções de tolerância justificadas (7 dias)", excecoes, "/relatorios/excecoes"),
    ]


def pendencias_financeiro(db: Session) -> list[dict]:
    """Perfil Financeiro (spec v3.21 T03): os SAs que esperam o R$/kg do precificador (SA da carga fica como veio).
    Os já achados no Mega (só falta o R$/kg para fechar e liberar a NF) vêm primeiro."""
    q = (select(CadastroSa).options(selectinload(CadastroSa.cop_item).selectinload(CopItem.cop))
         .where(CadastroSa.origem != "CARGA", or_(CadastroSa.rs_kg.is_(None), CadastroSa.rs_kg <= 0))
         .order_by(CadastroSa.criado_em, CadastroSa.id))
    itens = []
    for s in db.scalars(q):
        cop = s.cop_item.cop if s.cop_item else None
        itens.append({"id": s.id, "op": s.op, "cliente": s.cliente, "material": s.material, "dimensao": s.dimensao,
                      "peso_kg": s.peso_kg, "sa_codigo": s.sa_codigo, "situacao": s.situacao,
                      "sa_no_mega": svc_sas.sa_no_mega(s), "cop": cop.numero if cop else None,
                      "origem": s.origem, "criado_em": s.criado_em.isoformat()})
    itens.sort(key=lambda x: not x["sa_no_mega"])            # estável: dentro de cada grupo, o mais antigo primeiro
    return [
        _p("SA_SEM_PRECIFICADOR", "SAs aguardando o R$/kg do precificador", itens, "/sa",
           nivel="ALERTA" if any(x["sa_no_mega"] for x in itens) else "NORMAL")
        | {"no_mega": sum(1 for x in itens if x["sa_no_mega"])},
    ]


def excecoes_da_semana(db: Session, dias: int = 7) -> list[dict]:
    desde = agora() - timedelta(days=dias)
    out = []
    for m, nome in db.execute(select(Movimento, Usuario.nome).outerjoin(Usuario, Movimento.usuario_id == Usuario.id)
                              .where(Movimento.criado_em >= desde, Movimento.origem_ref.is_(None),  # fora a carga
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
    if p in ("FINANCEIRO", "ADMIN"):
        grupos["FINANCEIRO"] = pendencias_financeiro(db)
    rj = p == "OPERACAO_RJ"
    u = None if rj else sync_mega.ultima(db, "ESTOQUE", None)     # P10: o Marcelo não vê o Mega nem Itu
    ok = None if rj else sync_mega.ultima(db, "ESTOQUE")
    return {"perfil": p, "grupos": grupos, "atrasos": atrasos(db),
            "divergencias_mega": {"quantidade": divergencias_mega(db) if not rj else None,
                                  "limite_kg": parametro(db, "DIVERGENCIA_MEGA_KG")},
            "entradas_mega_a_classificar": {"quantidade": entradas_mega.contador(db) if not rj else None},
            "ultima_sincronizacao": {"terminado_em": ok.terminado_em.isoformat() if ok and ok.terminado_em else None,
                                     "situacao_ultima_tentativa": u.situacao if u else None}}
