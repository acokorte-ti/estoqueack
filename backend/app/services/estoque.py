"""Consultas de estoque por lote (T04/T05). Somente leitura."""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.domain.formato import kg_br
from app.domain.medidas import LIGA_MESMA_LINHA, ChaveMaterial, chave_material, interpretar
from app.models import Conteiner, Destinacao, ItemMP, Liga, Lote, Movimento, Nota, Usuario

from . import movimentos as mov

if TYPE_CHECKING:
    from app.domain.lotes import LoteInfo

BALDE = {("ITU", "ITU"): "ESTOQUE_MEGA", ("RJ", "RJ"): "RJ_NO_RIO", ("RJ", "ITU"): "RJ_EM_ITU"}
BALDE_INV = {v: k for k, v in BALDE.items()}

TIPO_MOV_DESCRICAO = {
    "SALDO_INICIAL": "Saldo inicial (carga)", "ENTRADA": "Entrada", "SAIDA_CORTE_RJ": "Corte no RJ",
    "ENVIO_ITU": "Envio para Itu", "RECEBIMENTO_ITU": "Recebimento em Itu", "CONSUMO_OP": "Consumo em OP",
    "GERA_SOBRA": "Sobra gerada", "GERA_RETO": "RETO gerado", "AJUSTE_INVENTARIO": "Ajuste de inventário",
    "ESTORNO": "Estorno", "SUCATA": "Sucata", "PERDA_CORTE": "Perda de corte", "ATRIBUIR_ORIGEM": "Origem atribuída",
}


def bitola(item: ItemMP) -> str:
    if item.formato == "RETO":
        return "RETO"
    if item.formato == "REDONDO" and item.diametro:
        return f"Ø{item.diametro:g}"
    if item.espessura and item.largura:
        return f"{item.espessura:g}X{item.largura:g}"
    return item.formato


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
        # spec v3.7 §1.4: código do Mega só existe no lote do Estoque Mega (o RJ não tem código)
        q = q.where(ItemMP.codigo_mega == f["codigo_mega"], Lote.planta_fiscal == "ITU", Lote.local_fisico == "ITU")
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


def chave_lote(item: ItemMP) -> ChaveMaterial:
    """Mesma linha Itu × RJ (spec v3.7 §1.4 + P28, 2026-11-11): liga (1.2344 = H13, 1.2379 = D2; MOD diferente),
    formato, seção do cadastro, comprimento informado na descrição e múltiplo. O código do Mega não entra."""
    k = chave_material(interpretar(item.descricao or ""), item.descricao, item.comprimento_fixado)
    liga = LIGA_MESMA_LINHA.get(item.liga.codigo, item.liga.codigo)
    if item.formato == "REDONDO":
        return ChaveMaterial(liga, "REDONDO", None, None, item.diametro, k.comprimento, k.multiplo)
    if item.formato == "RETANGULAR":
        return ChaveMaterial(liga, "RETANGULAR", item.espessura, item.largura, None, k.comprimento, k.multiplo)
    return ChaveMaterial(liga, item.formato, None, None, None, None, False)


def lote_resumo(db: Session, lotes: list[Lote]) -> list[dict]:
    ids = [l.id for l in lotes]
    res, dest, notas = mov.reservado(db, ids), _com_destinacao(db, ids), _com_nota(db, ids)
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
            "descricao": l.item.descricao,
            "codigo_mega": l.item.codigo_mega if (l.planta_fiscal, l.local_fisico) == ("ITU", "ITU") else None,
            "chave_material": chave_lote(l.item).texto,
            "estoque": BALDE.get((l.planta_fiscal, l.local_fisico)), "tipo": l.tipo,
            "saldo_kg": round(l.saldo_kg, 3), "reservado_kg": reservado,
            "disponivel_kg": round(l.saldo_kg - reservado, 3), "origem": origem,
            "indicadores": {"destinacao": l.id in dest, "nota": l.id in notas,
                            "origem_nao_identificada": not l.origem_identificada},
        })
    return saida


def agrupado(itens: list[dict]) -> list[dict]:
    """T04 "agrupado por liga × bitola" (spec v3.7 §1.4 + P28): Estoque Mega, RJ em Itu e RJ no Rio na mesma linha
    quando liga, bitola, comprimento e múltiplo coincidem; `codigos_itu` = códigos do Estoque Mega da linha."""
    g: dict[str, dict] = {}
    for i in itens:
        k = i["chave_material"]
        a = g.setdefault(k, {"chave": k, "liga": k.split(" ", 1)[0], "formato": i["formato"], "bitola": i["bitola"],
                             "lotes": 0, "saldo_kg": 0.0, "reservado_kg": 0.0, "disponivel_kg": 0.0,
                             "por_estoque": defaultdict(float), "codigos_itu": set(), "ligas": set()})
        a["lotes"] += 1
        for c in ("saldo_kg", "reservado_kg", "disponivel_kg"):
            a[c] = round(a[c] + i[c], 3)
        a["por_estoque"][i["estoque"]] = round(a["por_estoque"][i["estoque"]] + i["saldo_kg"], 3)
        a["ligas"].add(i["liga"])
        if i["codigo_mega"]:
            a["codigos_itu"].add(i["codigo_mega"])
    for a in g.values():
        a["por_estoque"] = {b: a["por_estoque"].get(b, 0.0) for b in BALDE.values()}
        a["codigos_itu"] = sorted(a["codigos_itu"])
        a["ligas"] = sorted(a["ligas"])
    return list(g.values())


LADO_ITU, LADO_RJ = "ITU", "RJ_NO_RIO"


def sugestao_por_bitola(itens: list[dict], peso_necessario_kg: float | None = None) -> list[dict]:
    """T07 passo 2, spec v3.5 (Fabiano, 2026-11-10): lotes compatíveis agrupados por liga e bitola EXATAS (mesmo
    formato e medidas; 21x202 e 21x203 nunca se juntam), comprimento informado e múltiplo (P28, 2026-11-11:
    1.2344 = H13 e 1.2379 = D2 ficam na mesma linha; MOD é outra liga). O código do Mega não entra na chave.
    Cada grupo tem os dois estoques lado a lado: "ITU" (Estoque Mega e RJ em Itu) e "RJ_NO_RIO", com o disponível,
    o total e "necessário × disponível". Liga equivalente vem em grupo à parte (`liga_equivalente`). Nada é escolhido
    sozinho: a escolha (um ou vários lotes, de estoques diferentes) é de quem monta a solicitação.

    `peso_necessario_kg` (do passo 3) vale para todos os grupos; sem ele, usa o peso previsto estimado do grupo
    (mesma bitola → mesmo previsto)."""
    grupos: dict[tuple, dict] = {}
    for i in itens:
        k = i["chave_material"]
        g = grupos.setdefault(k, {
            "chave": k, "liga": k.split(" ", 1)[0], "formato": i["formato"], "bitola": i["bitola"],
            "multiplo": i.get("multiplo"), "liga_equivalente": i["liga_equivalente"],
            "peso_previsto_kg": i["peso_previsto_kg"],
            "sobremetal_pct": i["sobremetal_pct"], "criado_em": i["criado_em"],
            "estoques": {LADO_ITU: {"disponivel_kg": 0.0, "lotes": []}, LADO_RJ: {"disponivel_kg": 0.0, "lotes": []}}})
        lado = LADO_RJ if i["estoque"] == "RJ_NO_RIO" else LADO_ITU
        g["estoques"][lado]["lotes"].append({k2: i[k2] for k2 in ("id", "codigo", "estoque", "conteiner", "codigo_mega",
                                                                  "liga", "liga_equivalente", "descricao", "tipo",
                                                                  "saldo_kg", "reservado_kg", "disponivel_kg",
                                                                  "indicadores")})
        g["liga_equivalente"] = g["liga_equivalente"] and i["liga_equivalente"]
        g["estoques"][lado]["disponivel_kg"] = round(g["estoques"][lado]["disponivel_kg"] + i["disponivel_kg"], 3)
        g["criado_em"] = min(g["criado_em"], i["criado_em"])
    out = []
    for g in grupos.values():
        total = round(sum(e["disponivel_kg"] for e in g["estoques"].values()), 3)
        nec = peso_necessario_kg if peso_necessario_kg else g["peso_previsto_kg"]
        g["total_disponivel_kg"] = total
        g["peso_necessario_kg"] = round(nec, 3) if nec else None
        g["falta_kg"] = round(max(nec - total, 0), 3) if nec else None
        g["sobra_kg"] = round(max(total - nec, 0), 3) if nec else None
        g["so_um_estoque"] = sum(1 for e in g["estoques"].values() if e["lotes"]) == 1
        if nec:
            g["frase"] = (f"Necessário {kg_br(nec)} × disponível {kg_br(total)}: "
                          + (f"falta {kg_br(g['falta_kg'])}" if g["falta_kg"] > 0 else f"sobra {kg_br(g['sobra_kg'])}"))
        else:
            g["frase"] = f"Disponível {kg_br(total)}"
        out.append(g)
    out.sort(key=lambda g: (g["liga_equivalente"], g["sobremetal_pct"] if g["sobremetal_pct"] is not None else 1e9,
                            g["criado_em"]))
    for g in out:
        del g["criado_em"]
    return out


def arvore(db: Session, lote: Lote, usuario: Usuario | None = None) -> dict:
    """Árvore de origem. [P10] Para a Operação RJ, lotes que não são do RJ no Rio (filhos em Itu) não aparecem, nem
    o saldo deles; a raiz passa a ser o ancestral mais alto ainda visível."""
    from .base import lote_visivel
    ver = (lambda l: True) if usuario is None else (lambda l: lote_visivel(usuario, l))
    r = lote
    vistos_: set[int] = set()
    while r.lote_pai_id is not None and r.id not in vistos_:
        vistos_.add(r.id)
        pai = db.get(Lote, r.lote_pai_id)
        if pai is None or not ver(pai):
            break
        r = pai
    filhos: dict[int | None, list[Lote]] = defaultdict(list)
    # carrega a família inteira (BFS a partir da raiz)
    fila, vistos = [r.id], {r.id}
    while fila:
        atual = fila.pop()
        for f in db.scalars(select(Lote).where(Lote.lote_pai_id == atual)):
            if f.id not in vistos and ver(f):
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
    from app.models import CopItem
    estornados = set(db.scalars(select(Movimento.estorno_de_id).where(Movimento.lote_id == lote_id,
                                                                      Movimento.estorno_de_id.is_not(None))))
    em_cop = set(db.scalars(select(CopItem.liberacao_id)))
    saldo, out = 0.0, []
    for m, nome in movs:
        saldo = round(saldo + m.kg, 3)
        estornavel = (m.tipo != "ESTORNO" and m.estorno_de_id is None and m.id not in estornados
                      and m.origem_ref is None                       # movimento da carga: corrigir por ajuste (T18)
                      and not (m.tipo == "SAIDA_CORTE_RJ" and m.liberacao_id in em_cop))
        out.append({"id": m.id, "data": (m.data_referencia or m.criado_em.date()).isoformat(), "tipo": m.tipo,
                    "tipo_descricao": TIPO_MOV_DESCRICAO.get(m.tipo, m.tipo), "kg": round(m.kg, 3),
                    "saldo_apos_kg": saldo, "op": m.op, "cop": m.cop_numero, "sa": m.sa_codigo,
                    "documento": m.documento, "usuario": nome, "justificativa": m.justificativa,
                    "estorno_de": m.estorno_de_id, "estornavel": estornavel,
                    "da_carga": m.origem_ref is not None})
    return out


# ---------------- RETO por origem (aba da T04, spec v3.4) ----------------

def lote_infos(db: Session) -> dict[int, LoteInfo]:
    """Monta os `LoteInfo` do domínio (árvore pai → filhos) a partir do banco, todos os lotes (a raiz pode estar
    fora do filtro). Bitola de origem anotada pela carga vem de `origem_ref["bitola_origem"]`."""
    from app.domain.lotes import LoteInfo
    q = (select(Lote).join(ItemMP, Lote.item_mp_id == ItemMP.id)
         .options(joinedload(Lote.item), joinedload(Lote.conteiner)))
    out = {}
    for l in db.scalars(q).unique():
        ref = l.origem_ref if isinstance(l.origem_ref, dict) else {}
        out[l.id] = LoteInfo(id=l.id, conteiner=l.conteiner.codigo if l.conteiner else "", liga=l.item.liga.codigo,
                             bitola=bitola(l.item), tipo=l.tipo, pai_id=l.lote_pai_id, saldo_kg=float(l.saldo_kg),
                             bitola_origem=ref.get("bitola_origem"))
    return out


def _norm_medida(t: str) -> str:
    return t.upper().replace("×", "X").replace(" ", "").replace("Ø", "")


def _primeiro_numero(b: str) -> float | None:
    import re
    m = re.search(r"\d+(?:[.,]\d+)?", b or "")
    return float(m.group().replace(",", ".")) if m else None


CLASSES = ("COMPLETA", "SO_BITOLA", "SEM_ORIGEM")


def reto_por_origem(db: Session, f: dict[str, Any]) -> dict[str, Any]:
    """Liga → bitola de origem → contêiner de origem, 3 classes separadas ("sem origem" em linha própria por liga).

    Filtros: estoque, ligas (lista), bitola_origem (texto), bitola_de/bitola_ate (1ª medida: espessura ou diâmetro),
    conteiner, codigo_mega, com_saldo (padrão ligado), incluir_sobras, criado_de/criado_ate."""
    from app.domain.lotes import origem_do_reto
    from app.domain.medidas import bitola_de_origem
    infos = lote_infos(db)
    tipos = ("RETO", "SOBRA") if f.get("incluir_sobras") else ("RETO",)
    lotes = [l for l in consulta_lotes(db, {"estoque": f.get("estoque"), "com_saldo": f.get("com_saldo", True),
                                            "codigo_mega": f.get("codigo_mega")})
             if l.tipo in tipos]
    ligas = {x.strip().upper() for x in (f.get("ligas") or []) if x.strip()}
    cont = (f.get("conteiner") or "").strip().upper()
    txt = _norm_medida(f.get("bitola_origem") or "")
    reservado = mov.reservado(db, [l.id for l in lotes])
    notas: dict[int, str] = {}
    if lotes:
        for eid, texto in db.execute(select(Nota.entidade_id, Nota.texto).where(
                Nota.entidade == "LOTE", Nota.entidade_id.in_([l.id for l in lotes])).order_by(Nota.id)):
            notas[eid] = f"{notas[eid]} | {texto}" if eid in notas else texto
    linhas: list[dict] = []
    for l in lotes:
        if ligas and l.item.liga.codigo.upper() not in ligas:
            continue
        if f.get("criado_de") and l.criado_em.date() < f["criado_de"]:
            continue
        if f.get("criado_ate") and l.criado_em.date() > f["criado_ate"]:
            continue
        bit, ct, classe = origem_do_reto(l.id, infos)
        if classe == "SO_BITOLA" and infos[l.id].bitola_origem and bit == infos[l.id].bitola_origem:
            bit = bitola_de_origem(bit, l.item.liga.codigo)      # R044: agrupa '25X610' com 'IMP-D2 25x610MM'
        if txt and txt not in _norm_medida(bit):
            continue
        n1 = _primeiro_numero(bit)
        if (f.get("bitola_de") is not None or f.get("bitola_ate") is not None) and (
                n1 is None or (f.get("bitola_de") is not None and n1 < f["bitola_de"])
                or (f.get("bitola_ate") is not None and n1 > f["bitola_ate"])):
            continue
        if cont and (ct or "").upper() != cont:
            continue
        res = round(min(reservado.get(l.id, 0.0), l.saldo_kg), 3)
        linhas.append({"lote_id": l.id, "lote": l.codigo, "estoque": BALDE.get((l.planta_fiscal, l.local_fisico)),
                       "tipo": l.tipo, "liga": l.item.liga.codigo, "bitola_origem": bit or None, "conteiner_origem": ct,
                       "classe": classe, "saldo_kg": round(float(l.saldo_kg), 3), "reservado_kg": res,
                       "disponivel_kg": round(float(l.saldo_kg) - res, 3), "criado_em": l.criado_em.isoformat(),
                       "nota": notas.get(l.id), "codigo_mega": l.item.codigo_mega})

    def soma(ls: list[dict]) -> dict[str, Any]:
        d = {"lotes": len(ls)}
        for c in ("saldo_kg", "reservado_kg", "disponivel_kg"):
            d[c] = round(sum(x[c] for x in ls), 3)
        return d

    def totais(ls: list[dict]) -> dict[str, Any]:
        por = {c: round(sum(x["saldo_kg"] for x in ls if x["classe"] == c), 3) for c in CLASSES}
        return {"com_origem_kg": por["COMPLETA"], "so_bitola_kg": por["SO_BITOLA"], "sem_origem_kg": por["SEM_ORIGEM"],
                "total_kg": round(sum(por.values()), 3), "lotes": len(ls),
                "reservado_kg": round(sum(x["reservado_kg"] for x in ls), 3),
                "disponivel_kg": round(sum(x["disponivel_kg"] for x in ls), 3)}

    saida_ligas = []
    for liga in sorted({x["liga"] for x in linhas}):
        da_liga = [x for x in linhas if x["liga"] == liga]
        bitolas = []
        com = [x for x in da_liga if x["classe"] != "SEM_ORIGEM"]
        for bit in sorted({x["bitola_origem"] or "" for x in com}, key=lambda b: (_primeiro_numero(b) or 0, b)):
            da_bit = [x for x in com if (x["bitola_origem"] or "") == bit]
            conts = []
            for ct, est in sorted({(x["conteiner_origem"], x["estoque"]) for x in da_bit},
                                  key=lambda t: (t[0] is None, t[0] or "", t[1] or "")):
                g = [x for x in da_bit if x["conteiner_origem"] == ct and x["estoque"] == est]
                conts.append({"conteiner": ct, "conteiner_texto": ct or "não informado", "estoque": est,
                              "classe": g[0]["classe"], **soma(g),
                              "lotes_detalhe": [{"id": x["lote_id"], "codigo": x["lote"], "saldo_kg": x["saldo_kg"]}
                                                for x in g]})
            bitolas.append({"bitola_origem": bit, "total_kg": round(sum(x["saldo_kg"] for x in da_bit), 3),
                            "conteineres": conts})
        sem = [x for x in da_liga if x["classe"] == "SEM_ORIGEM"]
        saida_ligas.append({
            "liga": liga, "bitolas": bitolas,
            "sem_origem": ({"texto": "Sem origem identificada", **soma(sem),
                            "por_estoque": {e: round(sum(x["saldo_kg"] for x in sem if x["estoque"] == e), 3)
                                            for e in sorted({x["estoque"] for x in sem})},
                            "lotes_detalhe": [{"id": x["lote_id"], "codigo": x["lote"], "saldo_kg": x["saldo_kg"],
                                               "estoque": x["estoque"]} for x in sem]} if sem else None),
            "totais": totais(da_liga)})
    return {"ligas": saida_ligas, "totais": totais(linhas), "lotes": linhas, "vazio": not linhas}
