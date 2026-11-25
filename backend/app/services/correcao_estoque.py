"""T27 Corrigir estoque, só Admin (spec v3.22, Eduardo, 2026-11-25; contrato §16.7).

Conferência física: lista os lotes que não são do Estoque Mega (planta fiscal RJ) e deixa o Admin corrigir tudo no
próprio sistema, sem justificativa obrigatória. O saldo entra como AJUSTE_INVENTARIO (o saldo continua igual à soma
dos movimentos); liga, medidas e descrição valem só para o lote (ele passa a um item do RJ com os dados novos); item
do Mega nunca muda. A recarga das planilhas (T25) apaga estas correções enquanto existir (escolha do Eduardo).
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.formato import kg_br
from app.domain.validacao import Nivel
from app.models import Auditoria, Conteiner, ItemMP, Liga, Lote, Nota, SolicitacaoCorte, Usuario

from . import auditoria, movimentos
from .base import Previa, exigir_sem_pendencias
from .estoque import bitola, chave_lote, consulta_lotes, lote_resumo, mapa_mesma_linha

ACAO = "LOTE_CORRIGIDO"
OBS_PADRAO = "Correção manual do estoque (Admin)"
NOME_ESTOQUE = {"RJ": "RJ no Rio", "ITU": "RJ em Itu"}
ROTULO = {"conteiner": "Contêiner", "liga": "Liga", "formato": "Formato", "espessura": "Espessura",
          "largura": "Largura", "diametro": "Diâmetro", "comprimento_fixado": "Comprimento", "descricao": "Descrição",
          "local_fisico": "Local", "saldo_kg": "Saldo", "custo_kg": "R$/kg"}
CAMPOS_ITEM = ("liga", "formato", "espessura", "largura", "diametro", "comprimento_fixado", "descricao")
MEDIDAS = ("formato", "espessura", "largura", "diametro")
SITUACOES_FECHADAS = ("CONCLUIDA", "CANCELADA", "RASCUNHO")


# ---------------- lista ----------------

def _corrigidos(db: Session, lotes: list[Lote]) -> dict[int, Any]:
    """Última correção manual de cada lote **depois da criação dele** (a recarga recria os lotes com os mesmos ids:
    correção de antes da carga não vale para o lote novo)."""
    if not lotes:
        return {}
    criado = {lt.id: lt.criado_em for lt in lotes}
    q = (select(Auditoria.entidade_id, func.max(Auditoria.quando))
         .where(Auditoria.acao == ACAO, Auditoria.entidade == "lote",
                Auditoria.entidade_id.in_([str(i) for i in criado]))
         .group_by(Auditoria.entidade_id))
    out = {}
    for ent, quando in db.execute(q):
        lid = int(ent)
        if quando is not None and criado.get(lid) is not None and quando >= criado[lid]:
            out[lid] = quando
    return out


def _linhas(db: Session, lotes: list[Lote]) -> list[dict[str, Any]]:
    base = {d["id"]: d for d in lote_resumo(db, lotes)}
    corr = _corrigidos(db, lotes)
    out = []
    for lt in lotes:
        it = lt.item
        ref = lt.origem_ref or {}
        out.append(base[lt.id] | {
            "item_id": it.id, "espessura": it.espessura, "largura": it.largura, "diametro": it.diametro,
            "comprimento_fixado": it.comprimento_fixado, "planta_fiscal": lt.planta_fiscal,
            "local_fisico": lt.local_fisico, "documento_entrada": lt.documento_entrada,
            "origem_carga": ({"arquivo": ref.get("arquivo"), "aba": ref.get("aba"), "linha": ref.get("linha")}
                             if ref.get("aba") or ref.get("arquivo") else None),
            "corrigido": lt.id in corr, "corrigido_em": corr[lt.id].isoformat() if lt.id in corr else None,
        })
    return out


def listar(db: Session, f: dict[str, Any]) -> list[dict[str, Any]]:
    lotes = consulta_lotes(db, {**f, "planta_fiscal": "RJ"})
    return _linhas(db, lotes)


def linha(db: Session, lote: Lote) -> dict[str, Any]:
    return _linhas(db, [lote])[0]


# ---------------- correção ----------------

def _num(v: Any) -> float | None:
    return None if v is None else round(float(v), 3)


def _atual(lote: Lote) -> dict[str, Any]:
    it = lote.item
    return {"conteiner": lote.conteiner.codigo if lote.conteiner else None, "liga": it.liga.codigo,
            "formato": it.formato, "espessura": _num(it.espessura), "largura": _num(it.largura),
            "diametro": _num(it.diametro), "comprimento_fixado": it.comprimento_fixado, "descricao": it.descricao,
            "local_fisico": lote.local_fisico, "saldo_kg": round(float(lote.saldo_kg), 3),
            "custo_kg": _num(lote.custo_kg)}


def _normalizar(dados: dict[str, Any]) -> dict[str, Any]:
    d = dict(dados)
    if "conteiner" in d:
        d["conteiner"] = (d["conteiner"] or "").strip().upper() or None
    if "liga" in d and d["liga"] is not None:
        d["liga"] = d["liga"].strip()
    for k in ("descricao", "comprimento_fixado"):
        if k in d and d[k] is not None:
            d[k] = " ".join(str(d[k]).split()) or None
    for k in ("espessura", "largura", "diametro", "saldo_kg", "custo_kg"):
        if k in d:
            d[k] = _num(d[k]) if d[k] not in ("", None) else None
    return d


def _alvo(atual: dict[str, Any], dados: dict[str, Any]) -> dict[str, Any]:
    alvo = {**atual, **{k: v for k, v in dados.items() if k in atual}}
    # medida que não vale para o formato sai (Ø no retangular, E × L no redondo)
    if alvo["formato"] == "RETANGULAR":
        alvo["diametro"] = None
    elif alvo["formato"] == "REDONDO":
        alvo["espessura"] = alvo["largura"] = None
    return alvo


def _igual(a: Any, b: Any) -> bool:
    if isinstance(a, int | float) and isinstance(b, int | float):
        return abs(float(a) - float(b)) < 0.0005
    return a == b


def _fmt(campo: str, v: Any) -> str:
    if v is None or v == "":
        return "—"
    if campo == "local_fisico":
        return NOME_ESTOQUE.get(v, v)
    if campo == "saldo_kg":
        return kg_br(v)
    if campo == "custo_kg":
        return f"R$ {v:.2f}".replace(".", ",")
    if isinstance(v, float):
        return f"{v:g}".replace(".", ",")
    return str(v)


def _item_virtual(alvo: dict[str, Any], liga: Liga) -> ItemMP:
    """Item fora da sessão, só para calcular a bitola e a chave de busca depois da correção."""
    return ItemMP(descricao=alvo["descricao"] or "", liga=liga, liga_id=liga.id, formato=alvo["formato"],
                  espessura=alvo["espessura"], largura=alvo["largura"], diametro=alvo["diametro"],
                  comprimento_fixado=alvo["comprimento_fixado"])


def _liga(db: Session, codigo: str | None) -> Liga | None:
    if not codigo:
        return None
    return db.scalar(select(Liga).where(func.upper(Liga.codigo) == codigo.upper()))


def validar(db: Session, lote: Lote, dados: dict[str, Any]) -> Previa:
    return _preparar(db, lote, dados)[0]


def _preparar(db: Session, lote: Lote, dados: dict[str, Any]) -> tuple[Previa, dict[str, Any], list[str]]:
    """Prévia + valores finais (`alvo`) + campos que mudam."""
    p = Previa()
    r = p.resultado
    dados = _normalizar(dados)
    atual = _atual(lote)
    alvo = _alvo(atual, dados)
    liga = _liga(db, alvo["liga"])
    if liga is not None:
        alvo["liga"] = liga.codigo          # "h13" digitado vale como H13 do catálogo
    if lote.planta_fiscal != "RJ":
        r.adicionar("LOTE_ESTOQUE_MEGA", Nivel.ERRO,
                    f"O lote {lote.codigo} é do Estoque Mega: o saldo e o cadastro dele vêm do Mega.")
    mudou = [c for c in atual if not _igual(atual[c], alvo[c])]
    p.efeitos = [{"campo": c, "rotulo": ROTULO[c], "antes": atual[c], "depois": alvo[c]} for c in mudou]
    if not mudou:
        r.adicionar("SEM_MUDANCA", Nivel.ERRO, "Nada mudou neste lote.")
        p.frase = f"Lote {lote.codigo}: nada a corrigir."
        return p, alvo, mudou
    p.frase = f"Lote {lote.codigo}: " + "; ".join(
        f"{ROTULO[c].lower()} {_fmt(c, atual[c])} → {_fmt(c, alvo[c])}" for c in mudou) + "."

    if liga is None:
        r.adicionar("LIGA_INEXISTENTE", Nivel.ERRO,
                    f"A liga \"{alvo['liga'] or ''}\" não está no catálogo (Administração → Ligas e densidades).")
    if alvo["formato"] not in ("RETANGULAR", "REDONDO", "RETO"):
        r.adicionar("MEDIDA_FALTANDO", Nivel.ERRO, "Escolha o formato: retangular, redondo ou RETO.")
    elif alvo["formato"] == "RETANGULAR" and not (alvo["espessura"] and alvo["largura"]
                                                   and alvo["espessura"] > 0 and alvo["largura"] > 0):
        r.adicionar("MEDIDA_FALTANDO", Nivel.ERRO, "Material retangular precisa de espessura e largura (mm).")
    elif alvo["formato"] == "REDONDO" and not (alvo["diametro"] and alvo["diametro"] > 0):
        r.adicionar("MEDIDA_FALTANDO", Nivel.ERRO, "Material redondo precisa do diâmetro (mm).")
    if not alvo["descricao"]:
        r.adicionar("DESCRICAO_VAZIA", Nivel.ERRO, "Escreva a descrição do material.")

    # a busca do Pedir corte (T07) e a consulta agrupada (T04) acham o lote pela liga e pela bitola
    item_mudou = any(c in CAMPOS_ITEM for c in mudou)
    if liga is not None and item_mudou and not r.erros:
        antes_b, depois_b = bitola(lote.item), bitola(_item_virtual(alvo, liga))
        mapa = mapa_mesma_linha(db)
        antes_k, depois_k = chave_lote(lote.item, mapa).texto, chave_lote(_item_virtual(alvo, liga), mapa).texto
        if "liga" in mudou:
            r.adicionar("LIGA_ALTERADA", Nivel.ALERTA,
                        f"A liga passa de {atual['liga']} para {liga.codigo}: no Pedir corte este lote deixa de "
                        f"aparecer para pedidos de {atual['liga']} {antes_b} e passa a aparecer para "
                        f"{liga.codigo} {depois_b}.", antes=atual["liga"], depois=liga.codigo)
        if any(c in MEDIDAS for c in mudou) and antes_b != depois_b:
            r.adicionar("MEDIDA_ALTERADA", Nivel.ALERTA,
                        f"A bitola passa de {antes_b} para {depois_b}: no Pedir corte este lote deixa de aparecer "
                        f"para pedidos de {alvo['liga']} {antes_b} e passa a aparecer para {alvo['liga']} {depois_b}.",
                        antes=antes_b, depois=depois_b)
        if antes_k != depois_k and "liga" not in mudou and antes_b == depois_b:
            r.adicionar("LINHA_ALTERADA", Nivel.ALERTA,
                        f"A linha do lote na consulta e no Pedir corte passa de \"{antes_k}\" para \"{depois_k}\" "
                        "(o comprimento e o múltiplo são lidos da descrição).", antes=antes_k, depois=depois_k)
        if "descricao" in mudou:
            r.adicionar("DESCRICAO_ALTERADA", Nivel.ALERTA,
                        "A descrição aparece nas telas, no Excel e na busca por texto; o comprimento e o múltiplo "
                        "do material são lidos dela.")
    if "local_fisico" in mudou:
        r.adicionar("LOCAL_ALTERADO", Nivel.ALERTA,
                    f"O lote passa de {NOME_ESTOQUE[atual['local_fisico']]} para "
                    f"{NOME_ESTOQUE.get(alvo['local_fisico'], alvo['local_fisico'])} sem COP (não gera movimento "
                    "nem NF).")
    if "conteiner" in mudou:
        if alvo["conteiner"] is None:
            r.adicionar("CONTEINER_NOVO", Nivel.ALERTA, "O lote fica sem contêiner.")
        elif db.scalar(select(Conteiner.id).where(Conteiner.codigo == alvo["conteiner"])) is None:
            r.adicionar("CONTEINER_NOVO", Nivel.ALERTA, f"O contêiner {alvo['conteiner']} não existe: será criado.")
    if item_mudou or "local_fisico" in mudou:
        ops = list(db.scalars(select(SolicitacaoCorte.op).where(
            SolicitacaoCorte.lote_id == lote.id, SolicitacaoCorte.situacao.not_in(SITUACOES_FECHADAS))))
        if ops:
            r.adicionar("SOLICITACAO_ABERTA", Nivel.ALERTA,
                        f"{len(ops)} pedido(s) de corte em aberto usam este lote (OP {', '.join(map(str, ops[:5]))}"
                        f"{'…' if len(ops) > 5 else ''}): eles passam a usar o lote corrigido.")
    if "saldo_kg" in mudou:
        novo = alvo["saldo_kg"]
        if novo is None or novo < 0:
            r.adicionar("SALDO_NEGATIVO", Nivel.ERRO, "O saldo não pode ficar vazio nem negativo.")
        else:
            dif = round(novo - atual["saldo_kg"], 3)
            r.adicionar("AJUSTE_SALDO", Nivel.ALERTA,
                        f"Ajuste de inventário de {'+' if dif > 0 else ''}{kg_br(dif)} (o histórico do lote fica).",
                        diferenca_kg=dif)
            reservado = movimentos.reservado(db, [lote.id]).get(lote.id, 0.0)
            if novo + 0.0005 < reservado:
                r.adicionar("SALDO_ABAIXO_RESERVADO", Nivel.ALERTA,
                            f"O saldo fica abaixo do reservado ({kg_br(reservado)}).")
    if "custo_kg" in mudou and alvo["custo_kg"] is not None and alvo["custo_kg"] < 0:
        r.adicionar("SALDO_NEGATIVO", Nivel.ERRO, "O R$/kg não pode ser negativo.")
    return p, alvo, mudou


def _item_do_lote(db: Session, lote: Lote, alvo: dict[str, Any], liga: Liga, mudou: list[str]) -> ItemMP:
    """O lote passa a um item do RJ (sem código Mega) com os dados novos: o igual, se já existir; senão um novo.
    Nada muda no item antigo, que pode ser de outros lotes (ou do Mega)."""
    q = select(ItemMP).where(ItemMP.codigo_mega.is_(None), ItemMP.liga_id == liga.id,
                             ItemMP.formato == alvo["formato"], ItemMP.descricao == alvo["descricao"])
    for campo in ("espessura", "largura", "diametro", "comprimento_fixado"):
        col = getattr(ItemMP, campo)
        q = q.where(col.is_(None) if alvo[campo] is None else col == alvo[campo])
    existente = db.scalar(q.order_by(ItemMP.id))
    if existente is not None:
        return existente
    velho = lote.item
    mesmo_material = not any(c in ("liga", *MEDIDAS) for c in mudou)
    novo = ItemMP(codigo_mega=None, descricao=alvo["descricao"], liga_id=liga.id, formato=alvo["formato"],
                  espessura=alvo["espessura"], largura=alvo["largura"], diametro=alvo["diametro"],
                  comprimento_fixado=alvo["comprimento_fixado"], um=velho.um, observacao_uso=velho.observacao_uso,
                  restricao_uso=velho.restricao_uso,
                  paridade_item_id=velho.paridade_item_id if mesmo_material else None)
    db.add(novo)
    db.flush()
    return novo


def gravar(db: Session, lote_id: int, dados: dict[str, Any], *, observacao: str | None,
           confirmacoes: dict[str, str] | None, usuario: Usuario, ip: str | None) -> tuple[Lote, int | None]:
    lote = movimentos.lote_ou_404(db, lote_id, travar=True)
    previa, alvo, mudou = _preparar(db, lote, dados)
    exigir_sem_pendencias(previa, confirmacoes)
    antes = {c: _atual(lote)[c] for c in mudou}
    obs = " ".join((observacao or "").split())[:400] or None

    if "conteiner" in mudou:
        if alvo["conteiner"] is None:
            lote.conteiner_id = None
        else:
            ct = db.scalar(select(Conteiner).where(Conteiner.codigo == alvo["conteiner"]))
            if ct is None:
                ct = Conteiner(codigo=alvo["conteiner"], observacao="Criado na correção do estoque (T27)")
                db.add(ct)
                db.flush()
            lote.conteiner_id = ct.id
    if any(c in CAMPOS_ITEM for c in mudou):
        item = _item_do_lote(db, lote, alvo, _liga(db, alvo["liga"]), mudou)
        lote.item_mp_id = item.id
    if "local_fisico" in mudou:
        lote.local_fisico = alvo["local_fisico"]
    if "custo_kg" in mudou:
        lote.custo_kg = alvo["custo_kg"]
    mov_id = None
    if "saldo_kg" in mudou:
        m = movimentos.lancar(db, lote, "AJUSTE_INVENTARIO", round(alvo["saldo_kg"] - float(lote.saldo_kg), 3),
                              usuario_id=usuario.id, justificativa=obs or OBS_PADRAO)
        mov_id = m.id
    db.flush()
    db.refresh(lote)
    depois = {c: alvo[c] for c in mudou}
    auditoria.registrar(db, ACAO, usuario_id=usuario.id, entidade="lote", entidade_id=lote.id,
                        antes=antes | ({"observacao": obs} if obs else {}), depois=depois, ip=ip)
    texto = "Correção manual (Admin): " + "; ".join(
        f"{ROTULO[c]} {_fmt(c, antes[c])} → {_fmt(c, depois[c])}" for c in mudou) + "." + (f" {obs}" if obs else "")
    db.add(Nota(entidade="LOTE", entidade_id=lote.id, texto=texto[:2000], usuario_id=usuario.id))
    db.commit()
    return lote, mov_id

