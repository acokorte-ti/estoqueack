"""Correções respondidas pelos usuários que a planilha não vai receber (spec v3.11 §10.9; decisões de 2026-11-17).

Vêm do arquivo `--correcoes` (JSON FORA do repositório: tem dados reais). Formato em
`docs/tecnico/04_carga_inicial.md` §5. Tipos tratados aqui (o `origem_reto` continua em `plano._corrigir_parcelas`):

- `leitura`: troca a liga, a descrição inteira ou o contêiner de linhas da ESTOQUE 2026, do HISTORICO, do Controle
  de Corte (coluna MP) ou da planilha de SA (coluna MATERIAL) (ex.: CH35SH "1.2746" → "H13", como no HISTORICO;
  HISTORICO linha "?" → a descrição certa). Filtros: `linhas`, `conteiner`, `descricao_planilha` (texto inteiro) e
  `contem` (expressão regular; no SA, sobre MATERIAL + DIMENSÃO); `esperado` = quantas linhas têm de casar.
- `consumo_sem_op`: célula de consumo da ESTOQUE 2026 cuja OP não existe → entra como consumo sem OP (pendência).
- `paridade_manual`: material do RJ no Rio que o usuário confirmou ser o mesmo de um código de Itu, apesar da medida
  escrita diferente (spec §1.4 item 8, P34(a)): o item do RJ mantém a própria medida e fica na mesma linha do código
  de Itu na T04/T07 (item_mp.paridade_item_id), sem receber o código.
- `avisos`: marca no relatório (e na nota do lote) uma linha com pergunta em aberto, sem mudar nada.
- `corte_planilha1` (spec v3.13 §10.9 A.7, [proposta, P37(a)]): linha que só existe na aba "Planilha1" do Controle
  de Corte e tem cadastro de SA → entra como solicitação CONCLUÍDA (corte no RJ, recebido), ligada ao SA da mesma OP
  e contêiner. Não mexe em saldo (a liberação não tem movimento; o kg já está nas saídas anteriores a 2026).
  `[{linha, op, conteiner?, fonte}]`; `__main__` lê só essas linhas da Planilha1 (`linhas_planilha1`).

Correção que não casa com a planilha → pendência `CORRECAO_NAO_APLICADA` (BLOQUEIA: a gravação é recusada, R053(4)).
Aviso que não casa → `AVISO_NAO_APLICADO` (REVISAR). A planilha nunca é alterada: o valor original vai para a nota.
"""
from __future__ import annotations

import dataclasses
import re
import unicodedata
from typing import Any

from app.domain.medidas import normalizar_liga

from . import planilhas as P

ABAS_LEITURA = ("ESTOQUE 2026", "HISTORICO", "CONTROLE DE CORTE", "SA")


def norm(t: Any) -> str:
    """Comparação de textos da planilha: sem acento, maiúsculas, sem espaços."""
    s = unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", "", s).upper()


def _linhas(spec: Any) -> set[int] | None:
    """`linhas`: lista de números e/ou faixas "252-269". None = qualquer linha."""
    if spec is None:
        return None
    out: set[int] = set()
    for x in spec if isinstance(spec, list) else [spec]:
        if isinstance(x, int):
            out.add(x)
        else:
            a, _, b = str(x).partition("-")
            out.update(range(int(a), int(b or a) + 1))
    return out


def _lista(v: Any) -> set[str] | None:
    if v is None:
        return None
    return {norm(x) for x in (v if isinstance(v, list) else [v])}


def _re_token(token: str) -> re.Pattern:
    corpo = r"\s*".join(re.escape(p) for p in token.split())
    return re.compile(rf"(?<![\w.,]){corpo}(?![\w.,])", re.I)


def _nao_aplicada(pl, tipo: str, n: int, c: dict, motivo: str) -> None:
    fonte = c.get("fonte") or "s/ fonte"
    pl.pend("CORRECAO_NAO_APLICADA", "BLOQUEIA", f"Correção não aplicada ({tipo} nº {n + 1}, {fonte}): {motivo}.",
            None, "Conferir o arquivo de correções e a planilha")


def _registrar(pl, tipo: str, n: int, onde: str, kg, antes, depois, fonte: str, chave_nota=None) -> None:
    pl.correcoes_aplicadas.append({"tipo": tipo, "linha": onde, "kg": kg, "antes": antes, "depois": depois,
                                   "fonte": fonte, "regra": (tipo, n)})
    pl.pend("CORRECAO_APLICADA", "INFO", f"{onde}: \"{antes}\" → \"{depois}\" ({fonte}).",
            None if chave_nota is None else {"aba": chave_nota[0], "linha": chave_nota[1]})
    if chave_nota is not None:
        pl.notas_origem[chave_nota].append(f"Correção da carga ({fonte}): na planilha \"{antes}\"; vale \"{depois}\".")


# ---------------- leitura (liga / descrição / contêiner) ----------------

def aplicar_leitura(pl, correcoes: dict, est: list[P.LinhaEstoque2026], hist: list[dict], corte: list[P.LinhaCorte],
                    sas: list[P.LinhaSa]
                    ) -> tuple[list[P.LinhaEstoque2026], list[dict], list[P.LinhaCorte], list[P.LinhaSa]]:
    regras = correcoes.get("leitura") or []
    if not regras:
        return est, hist, corte, sas
    est, hist, corte, sas = list(est), [dict(h) for h in hist], list(corte), list(sas)
    for n, c in enumerate(regras):
        aba = c.get("aba")
        if aba not in ABAS_LEITURA:
            _nao_aplicada(pl, "leitura", n, c, f"aba \"{aba}\" desconhecida (use {', '.join(ABAS_LEITURA)})")
            continue
        linhas, cts = _linhas(c.get("linhas")), _lista(c.get("conteiner"))
        desc_pl = norm(c["descricao_planilha"]) if c.get("descricao_planilha") is not None else None
        tok = _re_token(c["liga_planilha"]) if c.get("liga_planilha") else None
        contem = re.compile(c["contem"], re.I) if c.get("contem") else None
        if not any(c.get(k) for k in ("liga_correta", "descricao_correta", "conteiner_correto")):
            _nao_aplicada(pl, "leitura", n, c, "sem liga_correta, descricao_correta nem conteiner_correto")
            continue
        if c.get("liga_correta") and not tok:
            _nao_aplicada(pl, "leitura", n, c, "liga_correta exige liga_planilha")
            continue
        fonte = c.get("fonte") or "arquivo de correções"
        casou = []
        if aba == "ESTOQUE 2026":
            alvos = [(i, e.linha, e.material, e.conteiner, e.total_estoque, e.material) for i, e in enumerate(est)]
        elif aba == "HISTORICO":
            alvos = [(i, h["linha"], h["descricao"], h["conteiner"], h["entrada"], h["descricao"])
                     for i, h in enumerate(hist)]
        elif aba == "CONTROLE DE CORTE":
            alvos = [(i, x.linha, x.mp or "", x.conteiner, x.peso, x.mp or "") for i, x in enumerate(corte)]
        else:
            alvos = [(i, x.origem.get("linha"), x.material or "", x.origem_ct, x.peso,
                      f"{x.material or ''} {x.dimensao or ''}") for i, x in enumerate(sas)]
        for i, linha, desc, ct, kg, texto in alvos:
            if linhas is not None and linha not in linhas:
                continue
            if cts is not None and norm(ct) not in cts:
                continue
            if desc_pl is not None and norm(desc) != desc_pl:
                continue
            if tok and not tok.search(desc or ""):
                continue
            if contem and not contem.search(texto or ""):
                continue
            casou.append((i, linha, desc, ct, kg))
        esperado = c.get("esperado")
        if not casou or (esperado is not None and len(casou) != int(esperado)):
            _nao_aplicada(pl, "leitura", n, c, f"{aba}: {len(casou)} linha(s) casaram"
                          + (f", esperado {esperado}" if esperado is not None else ""))
            continue
        erro = None
        trocas = []
        for i, linha, desc, ct, kg in casou:
            novo_desc = desc
            if c.get("descricao_correta"):
                novo_desc = c["descricao_correta"]
            elif c.get("liga_correta"):
                novo_desc = re.sub(r"\s+", " ", tok.sub(c["liga_correta"], desc, count=1)).strip()
                if normalizar_liga(novo_desc) != normalizar_liga(c["liga_correta"]):
                    erro = f"\"{novo_desc}\" não é lida como {c['liga_correta']}"
                    break
            novo_ct = c.get("conteiner_correto") or ct
            trocas.append((i, linha, desc, ct, kg, novo_desc, novo_ct.strip().upper() if novo_ct else novo_ct))
        if erro:
            _nao_aplicada(pl, "leitura", n, c, erro)
            continue
        for i, linha, desc, ct, kg, novo_desc, novo_ct in trocas:
            if aba == "ESTOQUE 2026":
                est[i] = dataclasses.replace(est[i], material=novo_desc, conteiner=novo_ct)
                onde = f"ESTOQUE 2026 linha {linha}"
            elif aba == "HISTORICO":
                hist[i]["descricao"], hist[i]["conteiner"] = novo_desc, novo_ct
                onde = f"HISTORICO linha {linha}"
            elif aba == "CONTROLE DE CORTE":
                corte[i] = dataclasses.replace(corte[i], mp=novo_desc, conteiner=novo_ct)
                onde = f"Controle de Corte linha {linha} (OP {corte[i].op})"
            else:
                x = sas[i]
                sas[i] = dataclasses.replace(x, material=novo_desc, origem_ct=novo_ct,
                                             extras={**x.extras, "material_na_planilha": desc})
                onde = f"SA {x.origem.get('aba')} linha {linha}"
            antes = desc if novo_ct == ct else f"{ct} {desc}"
            depois = novo_desc if novo_ct == ct else f"{novo_ct} {novo_desc}"
            nota = (aba, linha) if aba in ("ESTOQUE 2026", "HISTORICO") else None
            _registrar(pl, "leitura", n, onde, kg, antes, depois, fonte, nota)
            if c.get("nota") and nota:
                pl.notas_origem[nota].append(f"{c['nota']} ({fonte}).")
    return est, hist, corte, sas


# ---------------- consumo sem OP ----------------

def aplicar_consumo_sem_op(pl, correcoes: dict, est: list[P.LinhaEstoque2026]) -> list[P.LinhaEstoque2026]:
    """`consumo_sem_op`: [{celula, op_planilha (null = célula já sem número), fonte}] → consumo sem OP."""
    regras = correcoes.get("consumo_sem_op") or []
    if not regras:
        return est
    est = list(est)
    for n, c in enumerate(regras):
        cel, op = norm(c.get("celula")), c.get("op_planilha")
        fonte = c.get("fonte") or "arquivo de correções"
        achou = False
        for i, e in enumerate(est):
            for j, cs in enumerate(e.consumos):
                if norm(cs.origem.get("celula")) != cel:
                    continue
                if (op is None and cs.ops) or (op is not None and int(op) not in cs.ops):
                    continue
                consumos = list(e.consumos)
                consumos[j] = dataclasses.replace(cs, ops=[], ops_texto=[])
                est[i] = dataclasses.replace(e, consumos=consumos)
                achou = True
                txt = f"OP {op}" if op is not None else "sem número de OP"
                pl.consumo_corrigido[cs.origem.get("celula")] = (
                    f"Comentário da planilha com {txt}, OP que não existe: consumo sem OP ({fonte}).")
                _registrar(pl, "consumo_sem_op", n, f"ESTOQUE 2026 célula {cs.origem.get('celula')}", cs.kg,
                           f"{e.conteiner} {e.material}: {txt}", "consumo sem OP (pendência)", fonte,
                           ("ESTOQUE 2026", e.linha))
                break
            if achou:
                break
        if not achou:
            _nao_aplicada(pl, "consumo_sem_op", n, c, f"célula {c.get('celula')} sem consumo com "
                          + (f"OP {op}" if op is not None else "consumo sem número de OP"))
    return est


# ---------------- paridade manual ----------------

def preparar_paridade_manual(pl, correcoes: dict, est: list[P.LinhaEstoque2026], geral: list[P.LinhaGeral],
                             chave_mat) -> None:
    """`paridade_manual`: [{descricao_rj, codigo_itu, descricao_itu?, fonte}]. Vale só para o material RJ no Rio
    (ESTOQUE 2026) com a mesma liga × bitola (chave) de `descricao_rj`."""
    for n, c in enumerate(correcoes.get("paridade_manual") or []):
        k_rj = chave_mat(c.get("descricao_rj") or "")
        g = next((x for x in geral if x.codigo and x.codigo == c.get("codigo_itu")), None)
        if g is None:
            _nao_aplicada(pl, "paridade_manual", n, c, f"código {c.get('codigo_itu')} não está no Estoque Geral")
            continue
        if c.get("descricao_itu") and norm(c["descricao_itu"]) != norm(g.descricao):
            _nao_aplicada(pl, "paridade_manual", n, c, f"código {g.codigo} está como \"{g.descricao}\" no Estoque "
                          f"Geral, não \"{c['descricao_itu']}\"")
            continue
        linhas = [e for e in est if chave_mat(e.material) == k_rj]
        if not linhas:
            _nao_aplicada(pl, "paridade_manual", n, c, f"nenhuma linha da ESTOQUE 2026 com {k_rj.texto}")
            continue
        fonte = c.get("fonte") or "arquivo de correções"
        k_itu = chave_mat(g.descricao, g.comprimento_fixado)
        pl.paridade_manual[k_rj] = {"g": g, "chave_itu": k_itu, "fonte": fonte, "regra": n,
                                    "descricao_rj": c.get("descricao_rj")}
        kg = round(sum(e.total_estoque for e in linhas), 3)
        _registrar(pl, "paridade_manual", n, "ESTOQUE 2026 linha(s) " + ", ".join(str(e.linha) for e in linhas), kg,
                   "; ".join(sorted({e.material for e in linhas})), f"{g.codigo} {g.descricao.strip()} (mesma linha)",
                   fonte)
        for e in linhas:
            pl.notas_origem[("ESTOQUE 2026", e.linha)].append(
                f"Paridade manual ({fonte}): mesmo material que {g.codigo} {g.descricao.strip()}; fica na mesma linha "
                f"de Itu ({k_itu.texto}) por exceção, com a própria medida.")


# ---------------- corte da Planilha1 ----------------

def linhas_planilha1(correcoes: dict) -> set[int]:
    return {int(c["linha"]) for c in correcoes.get("corte_planilha1") or [] if c.get("linha")}


def aplicar_corte_planilha1(pl, correcoes: dict, corte: list[P.LinhaCorte]) -> list[P.LinhaCorte]:
    regras = correcoes.get("corte_planilha1") or []
    da_p1 = [x for x in corte if x.origem.get("aba") == P.ABA_PLANILHA1]
    if not regras:
        return [x for x in corte if x.origem.get("aba") != P.ABA_PLANILHA1]
    usadas: set[int] = set()
    out = [x for x in corte if x.origem.get("aba") != P.ABA_PLANILHA1]
    for n, c in enumerate(regras):
        fonte = c.get("fonte") or "arquivo de correções"
        x = next((y for y in da_p1 if y.linha == c.get("linha")), None)
        if x is None or x.op != c.get("op") or (c.get("conteiner") and norm(x.conteiner) != norm(c["conteiner"])):
            _nao_aplicada(pl, "corte_planilha1", n, c, f"Planilha1 linha {c.get('linha')}: "
                          + ("linha vazia ou fora da aba" if x is None else f"OP {x.op} / {x.conteiner}, esperado "
                             f"OP {c.get('op')}" + (f" / {c['conteiner']}" if c.get("conteiner") else "")))
            continue
        usadas.add(x.linha)
        # P37(a): o corte aconteceu (tem cadastro de SA) → concluída, como as outras linhas de 2025 do contêiner
        y = dataclasses.replace(x, liberacao_feita=True, recebido=True,
                                pecas_cortadas=x.pecas_cortadas or x.qtd, status=None)
        out.append(y)
        _registrar(pl, "corte_planilha1", n, f"Planilha1 linha {x.linha} (OP {x.op})", x.peso2 or x.peso,
                   f"{x.conteiner} {x.mp}: só na Planilha1 (não importada)",
                   "solicitação concluída, corte no RJ, ligada ao SA da mesma OP", fonte)
    return out


# ---------------- avisos ----------------

def aplicar_avisos(pl, correcoes: dict, geral: list[P.LinhaGeral], est: list[P.LinhaEstoque2026]) -> None:
    """`avisos`: [{aba ("Estoque Geral" | "ESTOQUE 2026"), linha, descricao_planilha?, texto, fonte}]."""
    for n, c in enumerate(correcoes.get("avisos") or []):
        aba, linha = c.get("aba"), c.get("linha")
        fonte = c.get("fonte") or "arquivo de correções"
        linhas = geral if aba == "Estoque Geral" else est if aba == "ESTOQUE 2026" else []
        alvo = next((x for x in linhas if x.linha == linha), None)
        desc = None if alvo is None else (alvo.descricao if aba == "Estoque Geral" else alvo.material)
        if alvo is None or (c.get("descricao_planilha") and norm(c["descricao_planilha"]) != norm(desc)):
            pl.pend("AVISO_NAO_APLICADO", "REVISAR", f"Aviso nº {n + 1} ({fonte}) não casou com {aba} linha "
                    f"{linha}" + (f" (está \"{desc}\")" if desc else "") + ".", None)
            continue
        pl.pend("PENDENTE_USUARIO", "INFO", f"{aba} linha {linha} \"{desc}\": {c.get('texto')} ({fonte}).",
                alvo.origem, "Entra como está na planilha até a resposta")
        pl.notas_origem[(aba, linha)].append(f"Em aberto ({fonte}): {c.get('texto')}")
        pl.avisos.append({"aba": aba, "linha": linha, "descricao": desc, "texto": c.get("texto"), "fonte": fonte})
