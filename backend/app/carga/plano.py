"""Monta o PLANO da carga inicial (especificação §10) a partir das planilhas lidas, sem gravar nada.

O plano é o que vai para a prévia (relatório) e, depois de aprovado, para `gravar.py`. Decisões de interpretação:

- **Lotes RJ no Rio**: uma linha da ESTOQUE 2026 = um lote. Saldo inicial = PESO INICIAL; cada célula de consumo vira
  uma SAIDA_CORTE_RJ com OP e data do comentário. Confere com a coluna TOTAL EM ESTOQUE (AN).
- **Lotes esgotados**: contêiner + material do HISTORICO que não está mais na ESTOQUE 2026. Entram com a entrada e
  uma baixa "saídas anteriores ao sistema" até zero, só para consulta e para ligar o histórico de cortes.
- **Paridade RJ × Itu (spec v3.7 §1.4 + P28, 2026-11-11)**: o lote do RJ (no Rio e em Itu) NÃO recebe código do Mega;
  fica num item próprio sem código. A carga só classifica: mesma linha de Itu quando liga (1.2344 = H13, 1.2379 = D2;
  MOD diferente), formato, seção, comprimento informado e múltiplo são iguais (`medidas.chave_material`). O relatório
  "Paridade RJ x Itu" é conferido pelo Eduardo e pelo Fabiano antes da recarga.
- **RJ em Itu**: coluna "ESTOQUE RJ (em Itu)" do Estoque Geral, item sem código, origem não identificada [P07].
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

from app.domain.medidas import ChaveMaterial, chave_material, interpretar

from . import planilhas as P

FAMILIA = {"1.2344": "H13", "A8MOD": "A8", "1.2379": "D2"}
TOL_KG = 5.0
# R038 / §10.7: densidades da revisão do BLOCO 1 (aba 3, "Densidade proposta") e das ligas que não são aço
DENSIDADES_REVISADAS = {
    "N2360M": 7.85, "K-100": 7.70, "D3": 7.70, "OH255": 7.85, "VF800": 7.80, "OH251": 7.85, "1.2721": 7.85,
    "S1": 7.88, "45CRNI4MO": 7.85, "CPM10V": 7.41, "Z-WEAR": 7.75, "CPM-9V": 7.45, "M2": 8.16, "T1": 8.67,
    "SAE-52100": 7.81, "TENAX300": 7.80, "HGNI06": 7.85, "W360": 7.80, "SAE-1020": 7.85, "SAE-1045": 7.85,
    "SAE-4340": 7.85, "SAE-8620": 7.85, "HARDOX": 7.85, "1.2311": 7.85, "ASTM-A36": 7.85,
    "INOX-304": 7.93, "INOX-316": 8.00, "BRONZE": 8.80, "LATAO": 8.50, "COBRE-BERILIO": 8.25,
    "TITANIO-6AL4V": 4.43, "METAL-DURO": 14.50,
}
ALIAS_LIGA = {"AISI-M2": "M2", "Z.WER": "Z-WEAR"}
# descrições que não traziam a liga (aba 3 da revisão): corrigidas só na carga
DESCRICAO_CORRIGIDA = {"01 126": "O1 Ø126", "OH 251  1.2721 STEEL BARS 65X245X3555": "1.2721 65X245X3555",
                       "ASTM A-36 CHP 6,30X2530MM": "ASTM-A36 6,30X2530MM"}
# ligas que não são aço, pela descrição do Mega (decisão do Fabiano: entra quem teve movimento em 2 anos)
LIGAS_POR_TEXTO = (("METAL DURO", "METAL-DURO"), ("INOX 316", "INOX-316"), ("INOX-316", "INOX-316"),
                   ("316L", "INOX-316"), ("INOX", "INOX-304"), ("BRONZE", "BRONZE"), ("LATAO", "LATAO"),
                   ("LATÃO", "LATAO"), ("BERILIO", "COBRE-BERILIO"), ("BERÍLIO", "COBRE-BERILIO"),
                   ("TITANIO", "TITANIO-6AL4V"), ("TITÂNIO", "TITANIO-6AL4V"))
# solicitações ativas revistas pelo Fabiano
SITUACAO_REVISADA = {94394: "CONCLUIDA", 94429: "CONCLUIDA", 94528: "CONCLUIDA", 94529: "CONCLUIDA",
                     92756: "CANCELADA", 93620: "CANCELADA", 94356: "CANCELADA", 94646: "CANCELADA",
                     96111: "CANCELADA", 96674: "CANCELADA", 96772: "CANCELADA", 97662: "CANCELADA"}
# "RESERVADO CPR" era só observação da planilha (decisão do Eduardo, 04/11): não entra
TERMOS_RESTRICAO = ("NAO USAR", "NÃO USAR", "SOMENTE", "DESTINA", "EXCLUSIV", "LIBERACAO DE VENDAS",
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
    pai: LoteP | None = None            # lote de origem (RETO filho), quando a origem existe no cadastro

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
    kardex_entraram: list[dict[str, Any]] = field(default_factory=list)
    pendencias: list[Pendencia] = field(default_factory=list)
    conferencias: list[dict[str, Any]] = field(default_factory=list)
    contagens: dict[str, Any] = field(default_factory=dict)
    data_mega: str | None = None

    def pend(self, tipo: str, gravidade: str, descricao: str, origem=None, sugestao=None) -> None:
        self.pendencias.append(Pendencia(tipo, gravidade, descricao, origem, sugestao))


# ---------------- chaves de material ----------------

def medida(desc: str):
    d = (desc or "").strip()
    d = DESCRICAO_CORRIGIDA.get(d, d)
    d = re.sub(r"^01\s+", "O1 Ø", d)                     # "01 126" = O1 Ø126 (zero no lugar da letra O)
    d = re.sub(r"^OH\s*25[15]\s+", "", d)                # "OH 251  1.2721 STEEL BARS …" = 1.2721
    return interpretar(d)


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


def chave_mat(desc: str, comprimento_fixado: str | None = None) -> ChaveMaterial:
    """Identidade do material para a mesma linha Itu × RJ (P28)."""
    return chave_material(medida(desc), desc, comprimento_fixado)


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
    # códigos (entre os pedidos) com movimento no kardex do Mega nos últimos 2 anos; None = não deu para consultar
    kardex: Callable[[list[int]], set[int] | None] = lambda _codigos: None


def _liga(plano: Plano, ctx: Contexto, codigo: str | None, origem, densidade: float | None = None) -> str:
    if not codigo:
        codigo = "NAO-INFORMADA"                 # §10.7: "DESCONHECIDA"/"?" não são liga
    codigo = ALIAS_LIGA.get(codigo, codigo)
    if codigo not in ctx.ligas and codigo not in plano.ligas_novas:
        if codigo in DENSIDADES_REVISADAS:
            plano.ligas_novas[codigo] = DENSIDADES_REVISADAS[codigo]
            plano.pend("LIGA_NOVA", "INFO", f"Liga \"{codigo}\" criada com a densidade da revisão "
                       f"({plano.ligas_novas[codigo]:g}).", origem)
        else:
            plano.ligas_novas[codigo] = densidade if densidade and 1 < densidade < 25 else 7.85
            plano.pend("LIGA_NOVA", "REVISAR", f"Liga \"{codigo}\" não está no catálogo nem na revisão: entra com "
                       f"densidade {plano.ligas_novas[codigo]:g}. Conferir na T22.", origem)
    return codigo


def montar(ctx: Contexto, estoque: list[P.LinhaEstoque2026], historico: list[dict], geral: list[P.LinhaGeral],
           corte: list[P.LinhaCorte], sas: list[P.LinhaSa]) -> Plano:
    pl = Plano(data_mega=ctx.data_mega)
    _catalogo_geral(pl, ctx, geral)
    lotes_rj = _lotes_rj_no_rio(pl, ctx, estoque, historico)
    _paridade(pl, estoque, geral)
    _esgotados_historico(pl, ctx, estoque, historico, lotes_rj)
    _rj_em_itu(pl, ctx, geral)
    _estoque_mega(pl, ctx, geral)
    _ligar_reto_origem(pl)
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
        if not g.codigo:
            continue        # linha sem código = só material do RJ: o item é criado sem código pelo lote RJ (v3.7)
        ch = ("CM", g.codigo)
        uso = "; ".join(x for x in (g.clientes_uso, g.obs) if x) or None
        pl.itens[ch] = ItemP(ch, g.descricao.strip()[:200], liga, _formato_valido(m), m.espessura, m.largura,
                             m.diametro, g.codigo, g.comprimento_fixado, uso[:500] if uso else None, origem=g.origem)
        if g.codigo:
            vistos[g.codigo] = g.linha


def _item_rj(pl: Plano, ctx: Contexto, desc: str, origem, comprimento_fixado: str | None = None) -> tuple:
    """Item do lote RJ (no Rio e em Itu): SEMPRE sem código do Mega (spec v3.7 §1.4, decisão de 2026-11-11). Um item
    por liga real + formato + seção + comprimento + múltiplo (P28); a escrita da descrição não conta."""
    m = medida(desc)
    liga = _liga(pl, ctx, m.liga, origem)
    k = chave_mat(desc, comprimento_fixado)
    ch = ("RJ", liga, k.formato, k.espessura, k.largura, k.diametro, k.comprimento, k.multiplo)
    if ch not in pl.itens:
        nome = desc.strip()[:200] or f"{liga} {k.texto}"
        cf = comprimento_fixado if k.multiplo else None
        pl.itens[ch] = ItemP(ch, nome, liga, _formato_valido(m), k.espessura, k.largura, k.diametro,
                             comprimento_fixado=cf, origem=origem)
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


def _itu_por_chave(geral: list[P.LinhaGeral]) -> dict[ChaveMaterial, list[P.LinhaGeral]]:
    """Linhas de Itu = linhas do Estoque Geral com código do Mega."""
    idx: dict[ChaveMaterial, list[P.LinhaGeral]] = defaultdict(list)
    for g in geral:
        if g.codigo:
            idx[chave_mat(g.descricao, g.comprimento_fixado)].append(g)
    return idx


def _motivo_sem_par(k: ChaveMaterial, itu: dict[ChaveMaterial, list[P.LinhaGeral]]) -> tuple[str, list[P.LinhaGeral]]:
    """Por que o material RJ não tem linha igual em Itu (para o relatório), com a linha de Itu mais parecida."""
    if k.formato not in ("RETANGULAR", "REDONDO"):
        return "só no RJ", []                  # RETO / medida ilegível: não há bitola para comparar
    mesma_secao = [(c, gs) for c, gs in itu.items() if c.secao == k.secao]
    mesma = [(c, gs) for c, gs in mesma_secao if c.liga == k.liga]
    if mesma:
        c, gs = mesma[0]
        return ("múltiplo diferente" if c.multiplo != k.multiplo else "comprimento diferente"), gs
    so_liga = [(c, gs) for c, gs in mesma_secao if c.comprimento == k.comprimento and c.multiplo == k.multiplo]
    if so_liga:
        return "bitola igual, liga diferente", so_liga[0][1]
    prox = []
    for c, gs in itu.items():
        if c.liga != k.liga or c.formato != k.formato:
            continue
        if k.formato == "REDONDO" and c.diametro and k.diametro and abs(c.diametro - k.diametro) <= 2:
            prox.append((abs(c.diametro - k.diametro), gs))
        elif (k.formato == "RETANGULAR" and c.espessura and k.espessura and c.largura and k.largura
              and abs(c.espessura - k.espessura) <= 2 and abs(c.largura - k.largura) <= 2):
            prox.append((abs(c.espessura - k.espessura) + abs(c.largura - k.largura), gs))
    if prox:
        return "liga igual, bitola diferente", sorted(prox, key=lambda x: x[0])[0][1]
    return "só no RJ", []


def _linha_paridade(desc_rj: str, estoque: str, k: ChaveMaterial, kg: float, kg_geral: float | None,
                    itu: dict[ChaveMaterial, list[P.LinhaGeral]], item_rj: tuple | None, origem) -> dict[str, Any]:
    iguais = itu.get(k, [])
    liga_rj = medida(desc_rj).liga
    if iguais:
        ligas_itu = {medida(g.descricao).liga for g in iguais}
        motivo = ("liga e bitola iguais" if liga_rj in ligas_itu
                  else f"liga equivalente ({liga_rj} = {', '.join(sorted(x or '?' for x in ligas_itu))})")
        sit, ref = "MESMA LINHA", iguais
    else:
        motivo, ref = _motivo_sem_par(k, itu)
        sit = "SÓ NO RJ"
    return {"descricao_rj": desc_rj, "estoque": estoque, "chave": k.texto, "kg_rj": round(kg, 3),
            "kg_rj_geral": None if kg_geral is None else round(kg_geral, 3),
            "diferenca_kg": None if kg_geral is None else round(kg - kg_geral, 3),
            "item_mp": item_rj, "situacao": sit, "motivo": motivo,
            "itu": [{"codigo": g.codigo, "descricao": g.descricao, "kg": g.estoque_mega} for g in ref],
            "cm": ref[0].codigo if (ref and sit == "MESMA LINHA") else None, "origem": origem}


def _paridade(pl: Plano, estoque: list[P.LinhaEstoque2026], geral: list[P.LinhaGeral]) -> None:
    """Relatório de paridade RJ × Itu (spec v3.7 §1.4, P28; R049). Não liga nada a código: só classifica.
    RJ no Rio: um registro por material da ESTOQUE 2026 (liga × bitola), com a diferença de kg contra a coluna
    "RJ no Rio" do Estoque Geral (§10.2). RJ em Itu: um registro por linha do Estoque Geral com saldo RJ em Itu."""
    itu = _itu_por_chave(geral)
    geral_rio: dict[ChaveMaterial, float] = defaultdict(float)
    for g in geral:
        if g.rj_no_rio:
            geral_rio[chave_mat(g.descricao, g.comprimento_fixado)] += g.rj_no_rio
    rj: dict[ChaveMaterial, dict[str, Any]] = {}
    for e in estoque:
        k = chave_mat(e.material)
        a = rj.setdefault(k, {"descricoes": Counter(), "kg": 0.0, "origem": e.origem})
        a["descricoes"][e.material] += 1
        a["kg"] += e.total_estoque
    itens_rj = {it.chave: it for it in pl.itens.values() if it.chave[0] == "RJ"}
    for k, a in rj.items():
        desc_rj = a["descricoes"].most_common(1)[0][0]
        ch = next((c for c, it in itens_rj.items() if chave_mat(it.descricao, it.comprimento_fixado) == k), None)
        p = _linha_paridade(desc_rj, "RJ_NO_RIO", k, a["kg"], geral_rio.get(k, 0.0), itu, ch, a["origem"])
        p["descricoes_rj"] = sorted(a["descricoes"])
        pl.paridades.append(p)
        if p["situacao"] != "MESMA LINHA" and a["kg"] > 0:
            pl.pend("PARIDADE_SO_NO_RJ", "INFO", f"Material RJ \"{desc_rj}\" ({a['kg']:.1f} kg): {p['motivo']} "
                    "(sem linha igual em Itu; fica só no RJ, sem código).", a["origem"])
        if p["diferenca_kg"] is not None and abs(p["diferenca_kg"]) > TOL_KG:
            pl.pend("PARIDADE_TOTAL_DIFERENTE", "INFO",
                    f"{k.texto}: ESTOQUE 2026 soma {a['kg']:.1f} kg e o Estoque Geral (RJ no Rio) "
                    f"{p['kg_rj_geral']:.1f} kg (diferença {p['diferenca_kg']:+.1f} kg). Vale a ESTOQUE 2026 (§10.7).",
                    a["origem"])
    for g in geral:
        if g.rj_em_itu and g.rj_em_itu > 0:
            k = chave_mat(g.descricao, g.comprimento_fixado)
            pl.paridades.append(_linha_paridade(g.descricao, "RJ_EM_ITU", k, g.rj_em_itu, None, itu, None, g.origem))
    for k, kg in geral_rio.items():
        if k not in rj and kg > TOL_KG:
            gs = [g for g in geral if g.rj_no_rio and chave_mat(g.descricao, g.comprimento_fixado) == k]
            pl.pend("CM_SEM_MATERIAL_RJ", "INFO", f"{k.texto}: {kg:.1f} kg em \"RJ no Rio\" no Estoque Geral, sem "
                    "material igual na ESTOQUE 2026.", gs[0].origem if gs else None)


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
        if h["descricao"].strip() in ("?", ""):
            pl.pend("HISTORICO_SEM_DESCRICAO", "INFO", f"HISTORICO linha {h['linha']} ({h['conteiner']}) sem "
                    "descrição do material: não entra.", h["origem"])
            continue
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


def _rj_em_itu(pl: Plano, ctx: Contexto, geral: list[P.LinhaGeral]) -> None:
    """RJ em Itu. Linha RETO entra como tipo RETO (auditoria 06/11, B02). Se a célula tem comentário com as parcelas
    de sobra ("381kg de sobra (MEDIDA ORIGINAL IMP-D2 25X610MM)"), vira um sub-lote RETO por parcela, com a medida
    de origem guardada em origem_ref["bitola_origem"] (sem lote-pai: ver _ligar_reto_origem);
    o que sobra do saldo da célula fica num lote "sem origem". A soma dos sub-lotes é sempre o saldo da célula."""
    for g in geral:
        if g.rj_em_itu and g.rj_em_itu > 0:
            ch = _item_rj(pl, ctx, g.descricao, g.origem, g.comprimento_fixado)      # sem código (v3.7)
            reto = pl.itens[ch].formato == "RETO"
            tipo = "RETO" if reto else "ORIGINAL"
            parcelas = list(g.parcelas_itu) if reto else []
            if parcelas and sum(k for k, _ in parcelas) > g.rj_em_itu + 0.0005:
                pl.pend("RETO_PARCELAS_MAIORES_QUE_SALDO", "REVISAR", f"{g.descricao}: o comentário da célula soma "
                        f"{sum(k for k, _ in parcelas):.1f} kg, mais que o saldo ({g.rj_em_itu:.1f} kg). Entra um lote "
                        "só, sem origem.", g.origem, "Conferir o comentário com o Fabiano")
                parcelas = []
            fatias: list[tuple[float, str | None]] = [(k, d) for k, d in parcelas]
            resto = round(g.rj_em_itu - sum(k for k, _ in parcelas), 3)
            if resto > 0.0005 or not fatias:
                fatias.append((resto if fatias else g.rj_em_itu, None))
            for kg, desc_origem in fatias:
                origem = dict(g.origem or {})
                if desc_origem:
                    origem["bitola_origem"] = desc_origem
                lote = LoteP(ch, "RJ", "ITU", None, kg, tipo=tipo, origem_identificada=False, conferencia_kg=kg,
                             origem=origem, estoque="RJ_EM_ITU")
                lote.movimentos.append(MovP("SALDO_INICIAL", kg, documento="Carga Estoque Geral (RJ em Itu)",
                                            origem=origem))
                if desc_origem:
                    lote.notas.append(f"Parcela de sobra anotada no Estoque Geral: {kg:g} kg, medida original "
                                      f"{desc_origem}.")
                elif parcelas:
                    lote.notas.append("Saldo da célula RJ em Itu sem origem anotada no comentário (parcelas "
                                      f"anotadas: {sum(k for k, _ in parcelas):g} kg de {g.rj_em_itu:g} kg).")
                if g.obs_itu:
                    lote.notas.append(f"Observação do Estoque Geral (RJ em Itu): {g.obs_itu}")
                pl.lotes.append(lote)
            if parcelas:
                pl.pend("RETO_EM_ITU_POR_ORIGEM", "INFO", f"{g.descricao}: {g.rj_em_itu:.1f} kg em {len(parcelas)} "
                        f"parcela(s) com medida de origem + {max(resto, 0):.1f} kg sem origem.", g.origem)
                ligas = {chave_familia(d)[0] for _, d in parcelas}
                if ligas - {chave_familia(g.descricao)[0]}:
                    pl.pend("RETO_ORIGEM_DE_OUTRA_LIGA", "REVISAR", f"{g.descricao}: parcela com medida de origem de "
                            "outra liga (" + "; ".join(f"{k:g} kg {d}" for k, d in parcelas
                                                       if chave_familia(d)[0] != chave_familia(g.descricao)[0]) +
                            "). Registrada como veio na planilha.", g.origem, "Perguntar ao Fabiano: erro ou mistura?")
            else:
                pl.pend("RJ_EM_ITU_SEM_ORIGEM", "INFO", f"{g.descricao}: {g.rj_em_itu:.1f} kg RJ em Itu entram com "
                        "origem não identificada [P07].", g.origem, "Atribuir origem (T05) quando souber o contêiner")


def _ligar_reto_origem(pl: Plano) -> None:
    """Sub-lote RETO do RJ em Itu com bitola_origem NÃO ganha lote-pai por "candidato único" (decisão do Fabiano,
    2026-11-10, spec v3.5 §10.8): existir um só lote com a mesma liga e bitola não prova a origem (ex.: 11 kg de
    D2 45x300 com o mesmo peso de um lote que está em "RJ no Rio"). Fica sem pai, com a bitola do comentário em
    origem_ref (classe "só a bitola"); o pai só vem por regra explícita ("Atribuir origem" na T05)."""
    for lote in pl.lotes:
        desc = (lote.origem or {}).get("bitola_origem")
        if lote.tipo != "RETO" or not desc:
            continue
        m = medida(desc)
        if "~" in desc or m.formato not in ("RETANGULAR", "REDONDO"):
            pl.pend("RETO_ORIGEM_SEM_LOTE", "INFO", f"RETO {lote.saldo:g} kg, origem \"{desc}\": medida ambígua, "
                    "fica sem lote de origem (a medida está na nota).", lote.origem)
            continue
        pl.pend("RETO_ORIGEM_SO_BITOLA", "INFO", f"RETO {lote.saldo:g} kg, origem \"{desc}\": fica sem lote-pai, com a "
                "bitola do comentário (não se liga por candidato único).", lote.origem,
                "\"Atribuir origem\" na T05 quando souber o contêiner")


def _estoque_mega(pl: Plano, ctx: Contexto, geral: list[P.LinhaGeral]) -> None:
    if not ctx.mega_saldo:
        pl.pend("SEM_SALDO_MEGA", "BLOQUEIA", "Sem saldo do Mega (sincronização não rodou): os lotes do Estoque "
                "Mega não podem ser criados.", None, "Rodar \"Sincronizar agora\" antes da carga")
        return
    # §10.7 item 4 (decisão do Fabiano, 04/11): código do Mega fora do Estoque Geral entra se teve movimento no
    # kardex nos últimos 2 anos (qualquer grupo: aço, inox, não ferrosos, metal duro, peças…); o resto fica fora.
    fora_geral = [c for c, s in ctx.mega_saldo.items()
                  if ("CM", c) not in pl.itens and float(s["saldo_kg"] or 0) > 0.0005]
    com_mov = ctx.kardex(sorted(fora_geral)) if fora_geral else set()
    if com_mov is None:
        pl.pend("SEM_KARDEX", "BLOQUEIA", "Não deu para consultar o kardex do Mega: os códigos fora do Estoque Geral "
                "não podem ser classificados.", None, "Rodar a carga com o Mega no ar")
        com_mov = set()
    conhecidas = set(ctx.ligas) | {it.liga for it in pl.itens.values() if it.codigo_mega} | set(DENSIDADES_REVISADAS)
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
            desc = s.get("descricao") or f"Código {cod}"
            if cod not in com_mov:
                fora.append((cod, desc, kg))
                continue
            m = medida(desc)
            up = desc.upper()
            liga = next((lg for txt, lg in LIGAS_POR_TEXTO if txt in up), None)
            if liga is None:
                liga = ALIAS_LIGA.get(m.liga, m.liga) if m.liga and ALIAS_LIGA.get(m.liga, m.liga) in conhecidas \
                    else "NAO-INFORMADA"
            liga = _liga(pl, ctx, liga, None, s.get("peso_especifico"))
            pl.itens[ch] = ItemP(ch, desc[:200], liga, _formato_valido(m), m.espessura, m.largura, m.diametro, cod)
            dens = ctx.ligas.get(liga) or pl.ligas_novas.get(liga) or 7.85
            pl.kardex_entraram.append({"codigo": cod, "descricao": desc, "liga": liga, "densidade": dens, "kg": kg})
        it = pl.itens[ch]
        lote = LoteP(ch, "ITU", "ITU", None, kg, tipo="RETO" if it.formato == "RETO" else "ORIGINAL",
                     origem_identificada=False, conferencia_kg=kg, estoque="ESTOQUE_MEGA",
                     origem={"arquivo": "Mega (mega_saldo)", "aba": ctx.data_mega, "linha": cod})
        lote.movimentos.append(MovP("SALDO_INICIAL", kg, documento=f"Carga saldo Mega {ctx.data_mega or ''}".strip(),
                                    origem=lote.origem))   # com origem: movimento da carga, não estornável
        pl.lotes.append(lote)
    pl.contagens["mega_codigos_kardex_2_anos"] = len(pl.kardex_entraram)
    pl.contagens["mega_codigos_fora"] = len(fora)
    pl.contagens["mega_kg_fora"] = round(sum(k for _, _, k in fora), 3)
    for cod, desc, kg in fora:
        pl.pend("CM_FORA_SEM_MOVIMENTO", "INFO", f"Código {cod} \"{desc}\": {kg:.1f} kg no Mega, fora do Estoque "
                "Geral e sem movimento no kardex nos últimos 2 anos. Não entra (§10.7).", None)


def _restricoes_e_avisos(pl: Plano, geral: list[P.LinhaGeral]) -> None:
    por_chave: dict[tuple, list[LoteP]] = defaultdict(list)       # (chave P28, estoque) → lotes RJ (sem código)
    for l in pl.lotes:
        if l.item[0] == "RJ":
            it = pl.itens[l.item]
            por_chave[(chave_mat(it.descricao, it.comprimento_fixado), l.estoque)].append(l)
    for g in geral:
        ch = ("CM", g.codigo) if g.codigo else None
        for texto, estoque in ((g.obs_rj, "RJ_NO_RIO"), (g.obs_itu, "RJ_EM_ITU")):
            if not texto:
                continue
            up = texto.upper()
            sub = re.search(r"SUBSTITU[IÍ]DO POR (.+)", texto, re.I)
            if sub and ch not in pl.itens:
                continue
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
                # observação das colunas RJ vale só para os lotes RJ (sem código) do mesmo material e estoque
                # (a linha do Estoque Geral é de um código de Itu; se ela tem comprimento/múltiplo e o RJ não, vale a
                # mesma liga e seção sem o comprimento: a observação é do material RJ anotado nessa linha)
                k = chave_mat(g.descricao, g.comprimento_fixado)
                alvos = (por_chave.get((k, estoque)) or
                         por_chave.get((ChaveMaterial(k.liga, k.formato, k.espessura, k.largura, k.diametro, None,
                                                      False), estoque), []))
                for l in alvos:
                    l.destinacoes.append(("RESTRICAO", texto[:300]))
                pl.pend("RESTRICAO_A_REVISAR", "INFO", f"{g.descricao}: \"{texto}\" vira restrição em "
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
        if c.op in SITUACAO_REVISADA and sit in ("ENVIADA", "CORTADA", "CORTADA_PARCIAL", "MATERIAL_INSUFICIENTE"):
            sit = SITUACAO_REVISADA[c.op]          # revisão do Fabiano (§10.7)
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
    add("(a) Total Estoque Mega × saldo do Mega (filial 3)", None if not mega else
        round(sum(l.conferencia_kg or 0 for l in mega), 3), round(sum(l.saldo for l in mega), 3),
        obs=(f"Saldo do Mega de {pl.data_mega}. Fora (sem movimento no kardex em 2 anos): "
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
