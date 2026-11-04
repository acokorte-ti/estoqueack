"""Monta o PLANO da carga inicial (especificação §10) a partir das planilhas lidas, sem gravar nada.

O plano é o que vai para a prévia (relatório) e, depois de aprovado, para `gravar.py`. Decisões de interpretação:

- **Lotes RJ no Rio**: uma linha da ESTOQUE 2026 = um lote. Saldo inicial = PESO INICIAL; cada célula de consumo vira
  uma SAIDA_CORTE_RJ com OP e data do comentário. Confere com a coluna TOTAL EM ESTOQUE (AN).
- **Lotes esgotados**: contêiner + material do HISTORICO que não está mais na ESTOQUE 2026. Entram com a entrada e
  uma baixa "saídas anteriores ao sistema" até zero, só para consulta e para ligar o histórico de cortes.
- **Paridade RJ ↔ CM [P06]**: material RJ (liga + bitola) ligado à linha do Estoque Geral de mesma bitola e mesma
  família de liga (1.2344→H13, A8 MOD→A8, 1.2379→D2). Sempre "a confirmar" pelo Fabiano.
- **RJ em Itu**: coluna "ESTOQUE RJ (em Itu)" do Estoque Geral, um lote por item, origem não identificada [P07].
- **Estoque Mega**: saldo do Mega no dia (tabela mega_saldo da sincronização), um lote por código, origem não
  identificada. Código RETO vira lote RETO.
- **Histórico**: Controle de Corte → solicitações, cortes (liberações) e COPs; planilha de SA → SAs confirmados.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from app.domain.medidas import interpretar

from . import planilhas as P

FAMILIA = {"1.2344": "H13", "A8MOD": "A8", "1.2379": "D2"}
TOL_KG = 5.0
TERMOS_RESTRICAO = ("RESERVAD", "NAO USAR", "NÃO USAR", "SOMENTE", "DESTINA", "EXCLUSIV", "LIBERACAO DE VENDAS",
                    "LIBERAÇÃO DE VENDAS", "SO PARA", "SÓ PARA", "P/ DESFOLHADEIRA", "CONTRATO")


# ---------------- estruturas do plano ----------------

@dataclass
class Pendencia:
    tipo: str
    gravidade: str            # BLOQUEIA (não entra) | REVISAR (entra, mas o Fabiano confere) | INFO
    descricao: str
    origem: dict[str, Any] | None = None
    sugestao: str | None = None


@dataclass
class ItemP:
    chave: tuple
    descricao: str
    liga: str
    formato: str
    espessura: float | None = None
    largura: float | None = None
    diametro: float | None = None
    codigo_mega: int | None = None
    comprimento_fixado: str | None = None
    observacao_uso: str | None = None
    substituido_por: tuple | None = None
    origem: dict[str, Any] | None = None


@dataclass
class MovP:
    tipo: str
    kg: float
    op: int | None = None
    data: date | None = None
    documento: str | None = None
    justificativa: str | None = None
    origem: dict[str, Any] | None = None
    liberacao: LibP | None = None


@dataclass
class LoteP:
    item: tuple
    planta: str
    local: str
    conteiner: str | None
    peso_inicial: float
    tipo: str = "ORIGINAL"
    pecas: int | None = None
    custo_kg: float | None = None
    origem_identificada: bool = True
    documento: str | None = None
    movimentos: list[MovP] = field(default_factory=list)
    notas: list[str] = field(default_factory=list)
    destinacoes: list[tuple[str, str]] = field(default_factory=list)   # (tipo, descrição)
    conferencia_kg: float | None = None     # valor da planilha para conferir o saldo
    origem: dict[str, Any] | None = None
    estoque: str = ""

    @property
    def saldo(self) -> float:
        return round(sum(m.kg for m in self.movimentos), 3)


@dataclass
class LibP:
    lote: LoteP
    pecas: int
    peso_kg: float
    data: date
    cop: int | None
    situacao_item: str | None          # EM_TRANSITO | RECEBIDO | None (fora de COP)
    origem: dict[str, Any] | None = None


@dataclass
class SolP:
    op: int
    item_codigo: int | None
    cliente: str | None
    lote: LoteP
    modo: str
    quantidade: int
    formato: str
    acabada: tuple[float | None, float | None, float | None]
    peso_previsto: float
    instrucao: str | None
    instrucao_processo: str | None
    observacao: str | None
    prazo: date | None
    data: date | None
    situacao: str
    liberacoes: list[LibP] = field(default_factory=list)
    origem: dict[str, Any] | None = None


@dataclass
class SaP:
    linha: P.LinhaSa
    lote: LoteP | None
    solicitacao: SolP | None


@dataclass
class Plano:
    itens: dict[tuple, ItemP] = field(default_factory=dict)
    ligas_novas: dict[str, float] = field(default_factory=dict)
    lotes: list[LoteP] = field(default_factory=list)
    paridades: list[dict[str, Any]] = field(default_factory=list)
    solicitacoes: list[SolP] = field(default_factory=list)
    cops: dict[int, dict[str, Any]] = field(default_factory=dict)
    sas: list[SaP] = field(default_factory=list)
    pendencias: list[Pendencia] = field(default_factory=list)
    conferencias: list[dict[str, Any]] = field(default_factory=list)
    contagens: dict[str, Any] = field(default_factory=dict)
    data_mega: str | None = None

    def pend(self, tipo: str, gravidade: str, descricao: str, origem=None, sugestao=None) -> None:
        self.pendencias.append(Pendencia(tipo, gravidade, descricao, origem, sugestao))


# ---------------- chaves de material ----------------

def medida(desc: str):
    m = interpretar(desc or "")
    return m


def chave_item(liga: str | None, m) -> tuple:
    if m.formato == "REDONDO":
        return ("RJ", liga, "REDONDO", None, None, m.diametro)
    if m.formato == "RETANGULAR":
        return ("RJ", liga, "RETANGULAR", m.espessura, m.largura, None)
    return ("RJ", liga, m.formato, None, None, None)


def chave_familia(desc: str) -> tuple:
    m = medida(desc)
    liga = FAMILIA.get(m.liga, m.liga)
    return chave_item(liga, m)[1:]


def _formato_valido(m) -> str:
    return m.formato if m.formato in ("RETANGULAR", "REDONDO", "RETO") else "RETANGULAR"


# ---------------- montagem ----------------

@dataclass
class Contexto:
    ligas: dict[str, float]                    # código → densidade
    mega_saldo: dict[int, dict[str, Any]]      # código → {saldo_kg, descricao, peso_especifico}
    data_mega: str | None
    op_existe: Callable[[int], bool | None]     # None = não deu para verificar (Mega fora)
    hoje: date


def _liga(plano: Plano, ctx: Contexto, codigo: str | None, origem, densidade: float | None = None) -> str:
    if not codigo:
        codigo = "DESCONHECIDA"
    if codigo not in ctx.ligas and codigo not in plano.ligas_novas:
        plano.ligas_novas[codigo] = densidade if densidade and 6 < densidade < 10 else 7.85
        plano.pend("LIGA_NOVA", "REVISAR", f"Liga \"{codigo}\" não está no catálogo: entra com densidade "
                   f"{plano.ligas_novas[codigo]:g}. Conferir a densidade na T22.", origem)
    return codigo


def montar(ctx: Contexto, estoque: list[P.LinhaEstoque2026], historico: list[dict], geral: list[P.LinhaGeral],
           corte: list[P.LinhaCorte], sas: list[P.LinhaSa]) -> Plano:
    pl = Plano(data_mega=ctx.data_mega)
    _catalogo_geral(pl, ctx, geral)
    lotes_rj = _lotes_rj_no_rio(pl, ctx, estoque, historico)
    _paridade(pl, estoque, geral)
    _esgotados_historico(pl, ctx, estoque, historico, lotes_rj)
    _rj_em_itu(pl, geral)
    _estoque_mega(pl, ctx, geral)
    _restricoes_e_avisos(pl, geral)
    _solicitacoes(pl, ctx, corte, lotes_rj, estoque)
    _sas(pl, sas, lotes_rj)
    _ops_mal_digitadas(pl, ctx, estoque, corte)
    _conferencias(pl, estoque, geral, corte, sas)
    return pl


def _catalogo_geral(pl: Plano, ctx: Contexto, geral: list[P.LinhaGeral]) -> None:
    vistos: dict[int, int] = {}
    for g in geral:
        m = medida(g.descricao)
        liga = _liga(pl, ctx, m.liga, g.origem)
        if g.codigo and g.codigo in vistos:
            pl.pend("CM_REPETIDO", "REVISAR", f"Código Mega {g.codigo} aparece nas linhas {vistos[g.codigo]} e "
                    f"{g.linha} do Estoque Geral: fica a 1ª.", g.origem)
            continue
        if m.formato == "DESCONHECIDO":
            pl.pend("DESCRICAO_NAO_INTERPRETADA", "REVISAR", f"Não deu para ler a bitola de \"{g.descricao}\".",
                    g.origem)
        ch = ("CM", g.codigo) if g.codigo else ("GERAL", g.linha)
        uso = "; ".join(x for x in (g.clientes_uso, g.obs) if x) or None
        pl.itens[ch] = ItemP(ch, g.descricao.strip()[:200], liga, _formato_valido(m), m.espessura, m.largura,
                             m.diametro, g.codigo, g.comprimento_fixado, uso[:500] if uso else None, origem=g.origem)
        if g.codigo:
            vistos[g.codigo] = g.linha


def _item_rj(pl: Plano, ctx: Contexto, desc: str, origem) -> tuple:
    """Item do lote RJ: o do Estoque Geral de mesma liga e bitola (exata) ou um item só do RJ."""
    m = medida(desc)
    liga = _liga(pl, ctx, m.liga, origem)
    alvo = chave_item(liga, m)[1:]
    cands = [it for it in pl.itens.values() if (it.liga, it.formato, it.espessura, it.largura, it.diametro) == alvo]
    if cands:
        cands.sort(key=lambda it: (it.codigo_mega is None, it.chave[1] if it.chave[0] == "GERAL" else 0))
        return cands[0].chave
    ch = chave_item(liga, m)
    if ch not in pl.itens:
        nome = f"{liga} " + (f"Ø{m.diametro:g}" if m.formato == "REDONDO" else
                             f"{m.espessura:g}X{m.largura:g}" if m.formato == "RETANGULAR" else m.formato)
        pl.itens[ch] = ItemP(ch, nome, liga, _formato_valido(m), m.espessura, m.largura, m.diametro, origem=origem)
    return ch


def _data_consumo(dm: tuple[int, int] | None, hoje: date) -> date | None:
    if not dm:
        return None
    d, mes = dm
    for ano in (hoje.year, hoje.year - 1):
        try:
            x = date(ano, mes, d)
        except ValueError:
            return None
        if x <= hoje:
            return x
    return None


def _lotes_rj_no_rio(pl: Plano, ctx: Contexto, estoque: list[P.LinhaEstoque2026],
                     historico: list[dict] | None = None) -> dict[tuple, list[LoteP]]:
    idx: dict[tuple, list[LoteP]] = defaultdict(list)
    entrada: dict[tuple, date] = {}
    for h in historico or []:
        if h["data"]:
            k = (h["conteiner"], chave_familia(h["descricao"]))
            entrada[k] = min(entrada.get(k, h["data"]), h["data"])
    for e in estoque:
        item = _item_rj(pl, ctx, e.material, e.origem)
        lote = LoteP(item, "RJ", "RJ", e.conteiner, e.peso_inicial, pecas=e.pecas, custo_kg=e.valor_unitario,
                     conferencia_kg=e.total_estoque, origem=e.origem, estoque="RJ_NO_RIO")
        lote.notas.append(f"Material na planilha: {e.material}")
        if e.comentario_pecas:
            lote.notas.append(f"Peças (comentário da planilha): {e.comentario_pecas}")
        if e.peso_inicial > 0:
            # R036: o saldo inicial vem antes do 1º consumo, para o saldo acumulado nunca ficar negativo no histórico:
            # data de entrada do contêiner (HISTORICO) ou, se não houver ou for depois, a véspera do 1º consumo.
            datas = [d for c in e.consumos if (d := _data_consumo(c.dia_mes, ctx.hoje))]
            d0 = entrada.get((e.conteiner, chave_familia(e.material)))
            if datas and (d0 is None or d0 > min(datas)):
                d0 = min(datas) - timedelta(days=1)
            lote.movimentos.append(MovP("SALDO_INICIAL", e.peso_inicial, data=d0, documento="Carga ESTOQUE 2026",
                                        origem=e.origem))
        for c in e.consumos:
            if c.sem_op:
                pl.pend("SEM_OP", "REVISAR", f"{e.conteiner} {e.material}: consumo de {c.kg:g} kg sem OP "
                        f"(\"{c.comentario}\"). Material só existe com OP [P15].", c.origem,
                        "Informar a OP correta ou lançar como ajuste")
            elif not c.ops:
                pl.pend("CONSUMO_SEM_OP", "REVISAR", f"{e.conteiner} {e.material}: consumo de {c.kg:g} kg sem OP "
                        f"legível (\"{c.comentario}\").", c.origem)
            op = c.ops[0] if c.ops else None
            extra = f" (comentário com várias OPs: {', '.join(map(str, c.ops))})" if len(c.ops) > 1 else ""
            lote.movimentos.append(MovP("SAIDA_CORTE_RJ", -c.kg, op=op, data=_data_consumo(c.dia_mes, ctx.hoje),
                                        documento=(c.comentario or "")[:60] or None,
                                        justificativa=("Carga: consumo da planilha" + extra)[:500], origem=c.origem))
        if lote.saldo < -0.001:
            pl.pend("SALDO_NEGATIVO", "BLOQUEIA", f"{e.conteiner} {e.material}: consumos maiores que o peso inicial.",
                    e.origem)
        pl.lotes.append(lote)
        idx[(e.conteiner, chave_familia(e.material))].append(lote)
    return idx


def _paridade(pl: Plano, estoque: list[P.LinhaEstoque2026], geral: list[P.LinhaGeral]) -> None:
    geral_fam: dict[tuple, list[P.LinhaGeral]] = defaultdict(list)
    for g in geral:
        geral_fam[chave_familia(g.descricao)].append(g)
    rj: dict[tuple, dict[str, Any]] = {}
    for e in estoque:
        k = chave_familia(e.material)
        a = rj.setdefault(k, {"descricoes": Counter(), "kg": 0.0, "origem": e.origem})
        a["descricoes"][e.material] += 1
        a["kg"] += e.total_estoque
    usados = set()
    for k, a in rj.items():
        cands = geral_fam.get(k, [])
        desc_rj = a["descricoes"].most_common(1)[0][0]
        if not cands:
            prox = _proximos(k, geral_fam)
            sug = "; ".join(f"{g.codigo or '-'} {g.descricao}" for g in prox[:3])
            pl.paridades.append({"descricao_rj": desc_rj, "chave": k, "item_mp": None, "cm": None,
                                 "kg_rj_planilha": round(a["kg"], 3), "kg_rj_geral": None, "situacao": "SEM CM",
                                 "outros_candidatos": [f"(bitola próxima) {x}" for x in sug.split("; ") if x]})
            if a["kg"] > 0:
                pl.pend("PARIDADE_SEM_CM", "REVISAR", f"Material RJ \"{desc_rj}\" ({a['kg']:.1f} kg) sem linha "
                        "de mesma bitola no Estoque Geral (sem código Mega).", a["origem"],
                        f"Bitola próxima no Estoque Geral: {sug}" if sug else
                        "Indicar o código Mega do material ou confirmar que é só do RJ")
            continue
        cands = sorted(cands, key=lambda g: (-(g.rj_no_rio or 0), g.codigo is None))
        esc = cands[0]
        usados.update(id(c) for c in cands)
        kg_geral = round(sum(c.rj_no_rio for c in cands), 3)
        sit = "OK" if abs(kg_geral - a["kg"]) <= TOL_KG else "TOTAL DIFERENTE"
        ch_item = ("CM", esc.codigo) if esc.codigo else ("GERAL", esc.linha)
        pl.paridades.append({"descricao_rj": desc_rj, "chave": k, "item_mp": ch_item, "cm": esc.codigo,
                             "descricao_geral": esc.descricao, "kg_rj_planilha": round(a["kg"], 3),
                             "kg_rj_geral": kg_geral, "situacao": sit,
                             "outros_candidatos": [f"{c.codigo or '-'} {c.descricao}" for c in cands[1:]]})
        if sit != "OK":
            pl.pend("PARIDADE_TOTAL_DIFERENTE", "REVISAR",
                    f"{desc_rj}: ESTOQUE 2026 soma {a['kg']:.1f} kg e o Estoque Geral (RJ no Rio) {kg_geral:.1f} kg "
                    f"(diferença {a['kg'] - kg_geral:+.1f} kg).", a["origem"])
        if len(cands) > 1:
            pl.pend("PARIDADE_AMBIGUA", "REVISAR", f"{desc_rj}: {len(cands)} linhas do Estoque Geral com a mesma "
                    f"bitola; escolhida {esc.codigo or '-'} {esc.descricao}.", a["origem"])
    for g in geral:
        if g.codigo and id(g) not in usados and g.rj_no_rio > TOL_KG:
            pl.pend("CM_SEM_MATERIAL_RJ", "INFO", f"{g.codigo} {g.descricao}: {g.rj_no_rio:.1f} kg em \"RJ no Rio\" "
                    "no Estoque Geral, sem material igual na ESTOQUE 2026.", g.origem)


def _proximos(k: tuple, geral_fam: dict[tuple, list]) -> list:
    """Linhas do Estoque Geral da mesma família e formato com bitola até 2 mm de diferença."""
    liga, formato, e, l, d = k
    out = []
    for (lg, fm, e2, l2, d2), gs in geral_fam.items():
        if lg != liga or fm != formato:
            continue
        if formato == "REDONDO" and d and d2 and abs(d - d2) <= 2:
            out.append((abs(d - d2), gs))
        elif formato == "RETANGULAR" and e and l and e2 and l2 and abs(e - e2) <= 2 and abs(l - l2) <= 2:
            out.append((abs(e - e2) + abs(l - l2), gs))
    return [g for _, gs in sorted(out, key=lambda x: x[0]) for g in gs]


def _esgotados_historico(pl: Plano, ctx: Contexto, estoque, historico: list[dict],
                         idx: dict[tuple, list[LoteP]]) -> None:
    ativos_ct = {e.conteiner for e in estoque}
    por_ct: dict[str, list[dict]] = defaultdict(list)
    for h in historico:
        por_ct[h["conteiner"]].append(h)
    for ct in sorted(ativos_ct - set(por_ct)):
        pl.pend("CONTEINER_SEM_ENTRADA", "INFO", f"Contêiner {ct} da ESTOQUE 2026 não tem entrada no HISTORICO "
                "(lote sem documento de entrada).", None)
    grupos: dict[tuple, list[dict]] = defaultdict(list)
    for h in historico:
        grupos[(h["conteiner"], chave_familia(h["descricao"]))].append(h)
    for (ct, k), hs in grupos.items():
        if (ct, k) in idx:
            for lote in idx[(ct, k)]:
                for h in hs:
                    partes = [f"{h['descricao']}", f"{h['entrada']:g} kg" if h["entrada"] else None,
                              f"{h['pecas']} pç" if h["pecas"] else None,
                              h["data"].isoformat() if h["data"] else None, h["obs"], h["historico"]]
                    lote.notas.append("HISTORICO: " + " · ".join(str(x) for x in partes if x))
            continue
        entrada = round(sum(h["entrada"] or 0 for h in hs), 3)
        if entrada <= 0:
            continue
        item = _item_rj(pl, ctx, hs[0]["descricao"], hs[0]["origem"])
        lote = LoteP(item, "RJ", "RJ", ct, entrada, pecas=sum(h["pecas"] or 0 for h in hs) or None,
                     origem=hs[0]["origem"], estoque="RJ_NO_RIO (esgotado)")
        lote.movimentos.append(MovP("SALDO_INICIAL", entrada, data=min((h["data"] for h in hs if h["data"]),
                                                                        default=None),
                                    documento="Carga HISTORICO", origem=hs[0]["origem"]))
        sucata = round(sum(h["sucata"] or 0 for h in hs), 3)
        if 0 < sucata <= entrada:
            lote.movimentos.append(MovP("SUCATA", -sucata, documento="Carga HISTORICO", origem=hs[0]["origem"]))
        resto = lote.saldo
        if resto > 0:
            lote.movimentos.append(MovP("AJUSTE_INVENTARIO", -resto, documento="Carga HISTORICO",
                                        justificativa="Carga inicial: contêiner fora da ESTOQUE 2026; saídas "
                                                      "anteriores ao sistema (lote esgotado, só consulta)",
                                        origem=hs[0]["origem"]))
        for h in hs:
            if h["obs"] or h["historico"]:
                lote.notas.append("HISTORICO: " + " · ".join(x for x in (h["obs"], h["historico"]) if x))
        pl.lotes.append(lote)
        idx[(ct, k)].append(lote)


def _rj_em_itu(pl: Plano, geral: list[P.LinhaGeral]) -> None:
    for g in geral:
        if g.rj_em_itu and g.rj_em_itu > 0:
            ch = ("CM", g.codigo) if g.codigo and ("CM", g.codigo) in pl.itens else ("GERAL", g.linha)
            if ch not in pl.itens:
                continue
            lote = LoteP(ch, "RJ", "ITU", None, g.rj_em_itu, origem_identificada=False, conferencia_kg=g.rj_em_itu,
                         origem=g.origem, estoque="RJ_EM_ITU")
            lote.movimentos.append(MovP("SALDO_INICIAL", g.rj_em_itu, documento="Carga Estoque Geral (RJ em Itu)",
                                        origem=g.origem))
            if g.obs_itu:
                lote.notas.append(f"Observação do Estoque Geral (RJ em Itu): {g.obs_itu}")
            pl.lotes.append(lote)
            pl.pend("RJ_EM_ITU_SEM_ORIGEM", "INFO", f"{g.descricao}: {g.rj_em_itu:.1f} kg RJ em Itu entram com "
                    "origem não identificada [P07].", g.origem, "Atribuir origem (T05) quando souber o contêiner")


def _estoque_mega(pl: Plano, ctx: Contexto, geral: list[P.LinhaGeral]) -> None:
    if not ctx.mega_saldo:
        pl.pend("SEM_SALDO_MEGA", "BLOQUEIA", "Sem saldo do Mega (sincronização não rodou): os lotes do Estoque "
                "Mega não podem ser criados.", None, "Rodar \"Sincronizar agora\" antes da carga")
        return
    # Universo do Estoque Mega: códigos do Estoque Geral + códigos do Mega cuja descrição traz uma liga de aço
    # conhecida. O resto (bronze, rolamento, fita, inox…) também é "MP" no Mega, mas não é matéria-prima de aço
    # deste controle: fica de fora, listado nas pendências.
    conhecidas = set(ctx.ligas) | {it.liga for it in pl.itens.values() if it.codigo_mega}
    fora: list[tuple[int, str, float]] = []
    for cod, s in sorted(ctx.mega_saldo.items()):
        kg = round(float(s["saldo_kg"] or 0), 3)
        if kg <= 0.0005:
            if kg < -0.0005:
                pl.pend("SALDO_MEGA_NEGATIVO", "INFO", f"Código {cod} {s.get('descricao')}: saldo negativo no Mega "
                        f"({kg:.3f} kg); não vira lote.", None)
            continue
        ch = ("CM", cod)
        if ch not in pl.itens:
            m = medida(s.get("descricao") or "")
            if m.liga not in conhecidas:
                fora.append((cod, s.get("descricao") or "", kg))
                continue
            liga = _liga(pl, ctx, m.liga, None, s.get("peso_especifico"))
            pl.itens[ch] = ItemP(ch, (s.get("descricao") or f"Código {cod}")[:200], liga, _formato_valido(m),
                                 m.espessura, m.largura, m.diametro, cod)
            pl.pend("CM_FORA_DO_GERAL", "INFO", f"Código {cod} ({s.get('descricao')}) tem {kg:.1f} kg no Mega e não "
                    "está no Estoque Geral: item criado pela descrição do Mega.", None)
        it = pl.itens[ch]
        lote = LoteP(ch, "ITU", "ITU", None, kg, tipo="RETO" if it.formato == "RETO" else "ORIGINAL",
                     origem_identificada=False, conferencia_kg=kg, estoque="ESTOQUE_MEGA",
                     origem={"arquivo": "Mega (mega_saldo)", "aba": ctx.data_mega, "linha": cod})
        lote.movimentos.append(MovP("SALDO_INICIAL", kg, documento=f"Carga saldo Mega {ctx.data_mega or ''}".strip(),
                                    origem=lote.origem))   # com origem: movimento da carga, não estornável
        pl.lotes.append(lote)
    pl.contagens["mega_codigos_fora"] = len(fora)
    pl.contagens["mega_kg_fora"] = round(sum(k for _, _, k in fora), 3)
    for cod, desc, kg in fora:
        pl.pend("CM_FORA_DO_CATALOGO", "REVISAR", f"Código {cod} \"{desc}\": {kg:.1f} kg no Mega, não está no "
                "Estoque Geral e a descrição não traz liga de aço conhecida. Não vira lote.", None,
                "Confirmar que não é matéria-prima de aço; se for, incluir no Estoque Geral")


def _restricoes_e_avisos(pl: Plano, geral: list[P.LinhaGeral]) -> None:
    por_item: dict[tuple, list[LoteP]] = defaultdict(list)
    for l in pl.lotes:
        por_item[l.item].append(l)
    for g in geral:
        ch = ("CM", g.codigo) if g.codigo else ("GERAL", g.linha)
        if ch not in pl.itens:
            continue
        for texto, estoque in ((g.obs_rj, "RJ_NO_RIO"), (g.obs_itu, "RJ_EM_ITU")):
            if not texto:
                continue
            up = texto.upper()
            sub = re.search(r"SUBSTITU[IÍ]DO POR (.+)", texto, re.I)
            if sub:
                alvo = chave_familia(sub.group(1))
                achou = [it for it in pl.itens.values() if (FAMILIA.get(it.liga, it.liga), it.formato, it.espessura,
                                                            it.largura, it.diametro) == alvo and it.chave != ch]
                if achou:
                    pl.itens[ch].substituido_por = achou[0].chave
                else:
                    pl.pend("SUBSTITUTO_NAO_ENCONTRADO", "REVISAR", f"{g.descricao}: \"{texto}\" — substituto não "
                            "encontrado no catálogo.", g.origem)
                continue
            if any(t in up for t in TERMOS_RESTRICAO):
                alvos = [l for l in por_item.get(ch, []) if l.estoque == estoque] or por_item.get(ch, [])
                for l in alvos:
                    l.destinacoes.append(("RESTRICAO", texto[:300]))
                pl.pend("RESTRICAO_A_REVISAR", "REVISAR", f"{g.descricao}: \"{texto}\" vira restrição em "
                        f"{len(alvos)} lote(s).", g.origem, "Conferir se é reserva (com kg) ou restrição")
        for c in g.comentarios:
            if re.search(r"PEDID|COMPRA|PRAZO|EMBARC|CHEGA", c, re.I):
                pl.pend("MATERIAL_A_CHEGAR", "INFO", f"{g.descricao}: \"{c[:200]}\" (vai para T26).", g.origem)


def _parse_medida(txt: str | None) -> tuple[float | None, float | None, float | None]:
    nums = [float(x.replace(",", ".")) for x in re.findall(r"\d+(?:[.,]\d+)?", txt or "")]
    nums = (nums + [None, None, None])[:3]
    return nums[0], nums[1], nums[2]


def _previsto(lote: LoteP, it: ItemP, dens: float, instr: str | None, qtd: int, peso: float | None) -> float:
    if peso and peso > 0:
        return round(peso, 3)
    m = re.search(r"(\d+)\s*PE[CÇ]AS?\s*COM\s*(\d+(?:[.,]\d+)?)\s*MM", instr or "", re.I)
    if m:
        n, comp = int(m.group(1)), float(m.group(2).replace(",", "."))
        if it.formato == "REDONDO" and it.diametro:
            return round(3.14159265 / 4 * it.diametro ** 2 * comp * dens * 1e-6 * n, 3)
        if it.espessura and it.largura:
            return round(it.espessura * it.largura * comp * dens * 1e-6 * n, 3)
    return 0.0


def _solicitacoes(pl: Plano, ctx: Contexto, corte: list[P.LinhaCorte], idx: dict[tuple, list[LoteP]],
                  estoque) -> None:
    consumo_por_ct_op: dict[tuple, list[MovP]] = defaultdict(list)
    for l in pl.lotes:
        for m in l.movimentos:
            if m.tipo == "SAIDA_CORTE_RJ" and m.op:
                consumo_por_ct_op[(l.conteiner, m.op)].append(m)
    sem_cop: list[int] = []
    for c in corte:
        if not c.op:
            pl.pend("CORTE_SEM_OP", "BLOQUEIA", f"Controle de Corte linha {c.linha}: sem OP (\"{c.op_texto}\").",
                    c.origem)
            continue
        cand = idx.get((c.conteiner, chave_familia(c.mp or "")), [])
        if not cand:
            alt = re.findall(r"\bCH\s?\d+[A-Z]{1,3}\b", (c.observacao or "").upper())
            for ct in alt:
                cand = idx.get((ct.replace(" ", ""), chave_familia(c.mp or "")), [])
                if cand:
                    break
        if not cand:
            pl.pend("SOLICITACAO_SEM_LOTE", "BLOQUEIA", f"OP {c.op}: material {c.mp} / {c.conteiner} não encontrado "
                    "nos lotes (ESTOQUE 2026 nem HISTORICO). Linha não importada.", c.origem)
            continue
        lote = cand[0]
        it = pl.itens[lote.item]
        dens = ctx.ligas.get(it.liga) or pl.ligas_novas.get(it.liga) or 7.85
        modo = "TRAZER_INTEIRA" if (c.instrucao or "").upper().startswith("TRAZER") else "CORTAR_RJ"
        qtd = c.qtd if c.qtd and c.qtd > 0 else 1
        obs = (c.observacao or "").upper()
        if "CANCELAD" in obs:
            sit = "CANCELADA"
        elif c.liberacao_feita:
            sit = "CONCLUIDA" if c.recebido else "EM_TRANSITO"
        elif any(x in obs for x in ("INSUFICI", "FALTA MATERIAL")):
            sit = "MATERIAL_INSUFICIENTE"
        elif c.pecas_cortadas:
            sit = "CORTADA" if c.pecas_cortadas >= qtd else "CORTADA_PARCIAL"
        else:
            sit = "ENVIADA"
        s = SolP(c.op, c.item, c.cliente, lote, modo, qtd, it.formato, _parse_medida(c.medida),
                 _previsto(lote, it, dens, c.instrucao, qtd, c.peso), (c.instrucao or "")[:300] or None,
                 (c.instrucao_processo or "")[:300] or None,
                 "; ".join(x for x in (c.observacao if c.observacao not in ("-", None) else None,
                                       f"Peso informado: {c.peso_texto}" if c.peso is None and c.peso_texto and
                                       "INFORMAR" not in c.peso_texto.upper() else None) if x) or None,
                 c.prazo, c.data, sit, origem=c.origem)
        if sit in ("ENVIADA", "CORTADA_PARCIAL") and (c.status or "").upper().startswith("ATRASADO"):
            pl.pend("SOLICITACAO_ABERTA_ANTIGA", "REVISAR", f"OP {c.op} ({c.mp} / {c.conteiner}) aberta: "
                    f"\"{c.status}\". Entra na Fila RJ.", c.origem, "Cancelar ou manter")
        if c.pecas_cortadas or c.liberacao_feita:
            pecas = c.pecas_cortadas or qtd
            movs = consumo_por_ct_op.get((lote.conteiner, c.op), [])
            peso = c.peso2 if c.peso2 and c.peso2 > 0 else round(sum(-m.kg for m in movs), 3) or (c.peso or 0)
            if peso > 0:
                ncop = None
                mc = re.search(r"COP\s*(\d+)", obs)
                if mc:
                    ncop = int(mc.group(1))
                elif c.liberacao_feita:
                    sem_cop.append(c.linha)
                lib = LibP(lote, pecas, round(peso, 3), c.data_liberacao or c.data or ctx.hoje, ncop,
                           ("RECEBIDO" if c.recebido else "EM_TRANSITO") if c.liberacao_feita and ncop else None,
                           c.origem)
                s.liberacoes.append(lib)
                for m in movs:
                    if m.liberacao is None:
                        m.liberacao = lib
                if ncop:
                    cp = pl.cops.setdefault(ncop, {"numero": ncop, "datas": [], "itens": 0, "recebidos": 0})
                    cp["datas"].append(lib.data)
                    cp["itens"] += 1
                    cp["recebidos"] += 1 if c.recebido else 0
            else:
                pl.pend("CORTE_SEM_PESO", "REVISAR", f"OP {c.op}: corte registrado sem PESO2 nem consumo na ESTOQUE "
                        "2026; entra sem o corte.", c.origem)
        pl.solicitacoes.append(s)
    if sem_cop:
        pl.pend("LIBERACAO_SEM_COP", "INFO", f"{len(sem_cop)} cortes liberados sem número de COP na observação: "
                "entram como cortes concluídos, sem COP.", {"arquivo": P.ARQ_CORTE, "aba": "CONTROLE - CORTE RJ",
                                                            "linha": f"{sem_cop[0]}..{sem_cop[-1]}"})


def _sas(pl: Plano, sas: list[P.LinhaSa], idx: dict[tuple, list[LoteP]]) -> None:
    sol_por = {(s.op, s.lote.conteiner): s for s in pl.solicitacoes}
    itens_por_sa: dict[int, set[int]] = defaultdict(set)
    for x in sas:
        if not x.op and not x.sa_codigo:
            continue
        if x.sa_codigo is None:
            pl.pend("SA_SEM_CODIGO", "INFO", f"SA da OP {x.op} sem código numérico (\"{x.sa_codigo_texto}\").",
                    x.origem)
        if x.sa_codigo and x.item:
            itens_por_sa[x.sa_codigo].add(x.item)
        lote = None
        if x.origem_ct and x.material:
            cand = idx.get((x.origem_ct, chave_familia(f"{x.material} {x.dimensao or ''}")), [])
            lote = cand[0] if cand else None
        pl.sas.append(SaP(x, lote, sol_por.get((x.op, x.origem_ct))))
    for cod, itens in itens_por_sa.items():
        if len(itens) > 1:
            pl.pend("SA_CODIGO_COMPARTILHADO", "INFO", f"Código de SA {cod} usado para {len(itens)} itens: "
                    f"{', '.join(map(str, sorted(itens)))}.", None)


def _ops_mal_digitadas(pl: Plano, ctx: Contexto, estoque, corte) -> None:
    ops: dict[int, dict[str, Any]] = {}
    for e in estoque:
        for c in e.consumos:
            for o in c.ops:
                ops.setdefault(o, c.origem)
    for c in corte:
        if c.op:
            ops.setdefault(c.op, c.origem)
    nao_verificadas = 0
    for op, origem in sorted(ops.items()):
        if not 50000 <= op <= 200000:
            pl.pend("OP_MAL_DIGITADA", "REVISAR", f"OP {op} fora da faixa das OPs do Mega.", origem,
                    "Corrigir a OP na planilha")
            continue
        ex = ctx.op_existe(op)
        if ex is False:
            pl.pend("OP_MAL_DIGITADA", "REVISAR", f"OP {op} não existe no Mega.", origem, "Corrigir a OP na planilha")
        elif ex is None:
            nao_verificadas += 1
    pl.contagens["ops_citadas"] = len(ops)
    pl.contagens["ops_nao_verificadas_no_mega"] = nao_verificadas


def _conferencias(pl: Plano, estoque, geral, corte, sas) -> None:
    def add(nome, planilha, sistema, tol=TOL_KG, obs=None):
        dif = None if planilha is None or sistema is None else round(sistema - planilha, 3)
        ok = dif is not None and abs(dif) <= tol
        pl.conferencias.append({"conferencia": nome, "planilha": planilha, "sistema": sistema, "diferenca": dif,
                                "tolerancia": tol, "resultado": "OK" if ok else "DIFERENTE", "observacao": obs})
    rio = [l for l in pl.lotes if l.estoque == "RJ_NO_RIO"]
    add("(b) Total RJ no Rio × ESTOQUE 2026 (coluna TOTAL EM ESTOQUE)", round(sum(e.total_estoque for e in estoque), 3),
        round(sum(l.saldo for l in rio), 3))
    linhas_dif = [l for l in rio if l.conferencia_kg is not None and abs(l.saldo - l.conferencia_kg) > 0.01]
    add("(b) Lotes RJ no Rio com saldo ≠ planilha (linhas)", 0, len(linhas_dif), 0)
    add("(b) Total RJ no Rio × Estoque Geral (coluna RJ no Rio) — paridade",
        round(sum(g.rj_no_rio for g in geral), 3), round(sum(l.saldo for l in rio), 3),
        obs="Diferença esperada: a ESTOQUE 2026 e o Estoque Geral não batem 100 %; ver aba Paridade")
    itu = [l for l in pl.lotes if l.estoque == "RJ_EM_ITU"]
    add("(c) Total RJ em Itu × Materia Prima Geral (coluna RJ em Itu)", round(sum(g.rj_em_itu for g in geral), 3),
        round(sum(l.saldo for l in itu), 3))
    mega = [l for l in pl.lotes if l.estoque == "ESTOQUE_MEGA"]
    add("(a) Total Estoque Mega × saldo do Mega (MP de aço, filial 3)", None if not mega else
        round(sum(l.conferencia_kg or 0 for l in mega), 3), round(sum(l.saldo for l in mega), 3),
        obs=(f"Saldo do Mega de {pl.data_mega}. Fora do catálogo (não é aço): "
             f"{pl.contagens.get('mega_codigos_fora', 0)} códigos, {pl.contagens.get('mega_kg_fora', 0):.1f} kg")
        if pl.data_mega else "Sem saldo do Mega")
    add("(a) Estoque Geral (ESTOQUE MEGA de 20/10) × saldo do Mega hoje",
        round(sum(g.estoque_mega or 0 for g in geral), 3),
        round(sum(l.saldo for l in mega), 3), tol=10 ** 9, obs="Só informativo: a planilha é de 20/10")
    validas = [c for c in corte if c.op]
    add("(d) Solicitações históricas importadas × linhas do Controle de Corte", len(corte), len(pl.solicitacoes), 0,
        obs=f"{len(corte) - len(validas)} sem OP; o resto não importado está nas pendências (SOLICITACAO_SEM_LOTE)")
    add("(d) Cortes (liberações) importados", sum(1 for c in corte if c.pecas_cortadas or c.liberacao_feita),
        sum(len(s.liberacoes) for s in pl.solicitacoes), 0, obs="Cortes sem peso ficam de fora (CORTE_SEM_PESO)")
    cops_planilha = {int(m.group(1)) for c in corte if (m := re.search(r"COP\s*(\d+)", (c.observacao or "").upper()))}
    add("(d) COPs importados × COPs citados no Controle de Corte", len(cops_planilha), len(pl.cops), 0)
    add("(d) SAs históricos importados × linhas da planilha de SA", len([x for x in sas if x.op or x.sa_codigo]),
        len(pl.sas), 0)
    pl.contagens.update({
        "lotes_rj_no_rio": len(rio), "lotes_esgotados_historico": sum(1 for l in pl.lotes if "esgotado" in l.estoque),
        "lotes_rj_em_itu": len(itu), "lotes_estoque_mega": len(mega), "itens": len(pl.itens),
        "ligas_novas": len(pl.ligas_novas), "solicitacoes": len(pl.solicitacoes),
        "solicitacoes_ativas": sum(1 for s in pl.solicitacoes if s.situacao in ("ENVIADA", "CORTADA_PARCIAL",
                                                                                 "MATERIAL_INSUFICIENTE", "CORTADA")),
        "cops": len(pl.cops), "sas": len(pl.sas), "pendencias": len(pl.pendencias),
        "movimentos": sum(len(l.movimentos) for l in pl.lotes)})
