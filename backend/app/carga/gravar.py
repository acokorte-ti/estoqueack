"""Grava o plano da carga inicial. Re-executável: `limpar` apaga os dados operacionais e a carga recria tudo.

Fica fora da limpeza: usuários, sessões, auditoria, ligas, equivalências, parâmetros e o cache do Mega
(saldo, movimentos e sincronizações). Tudo roda numa transação só: se der erro, nada muda.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timezone
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.models import (CadastroSa, Conteiner, Cop, CopItem, Destinacao, ItemMP, LiberacaoCorte, Liga, Lote,
                        MegaSaldo, Movimento, NfTransferencia, Nota, ParidadeRj, SolicitacaoCorte)
from app.services import auditoria

from .plano import LibP, Plano

# ordem de dependência (filhos primeiro)
TABELAS_OPERACIONAIS = ("notificacao", "divergencia_recebimento", "cadastro_sa", "cop_item", "cop",
                        "nf_transferencia", "corte_itu", "liberacao_corte", "solicitacao_corte", "entrada_nf_item",
                        "entrada_nf", "movimento", "destinacao", "nota", "pendencia_mega", "paridade_rj",
                        "pedido_a_chegar", "lote", "conteiner", "item_mp")


# A planilha de SA não diz qual das duas empresas do RJ emitiu a NF (Fio Certo ou Médio Vale)
EMITENTE_CARGA = "FIO_CERTO/MEDIO_VALE (planilha)"


class CargaRecusada(Exception):
    pass


def base_vazia(db: Session) -> bool:
    return not db.scalar(select(func.count(Lote.id))) and not db.scalar(select(func.count(SolicitacaoCorte.id)))


def limpar(db: Session) -> None:
    if db.get_bind().dialect.name == "postgresql":
        # TRUNCATE não dispara o trigger de imutabilidade (que é por linha, em UPDATE/DELETE): é o único jeito de
        # zerar `movimento`. Só a carga faz isso, e só fora de produção ou com confirmação explícita.
        db.execute(text("TRUNCATE " + ", ".join(TABELAS_OPERACIONAIS) + " RESTART IDENTITY CASCADE"))
    else:
        for t in TABELAS_OPERACIONAIS:
            db.execute(text(f"DELETE FROM {t}"))  # noqa: S608 — nomes fixos da lista acima
    db.flush()


def _ts(d: date | None) -> datetime | None:
    return datetime.combine(d, time(12, 0), tzinfo=timezone.utc) if d else None


def gravar(db: Session, pl: Plano, *, usuario_id: int | None, arquivos: dict[str, str]) -> dict[str, Any]:
    bloqueios = [p for p in pl.pendencias if p.gravidade == "BLOQUEIA" and p.tipo in ("SEM_SALDO_MEGA",
                                                                                      "SALDO_NEGATIVO")]
    if bloqueios:
        raise CargaRecusada("; ".join(p.descricao for p in bloqueios))

    # ligas novas
    ligas = {l.codigo: l for l in db.scalars(select(Liga))}
    for cod, dens in pl.ligas_novas.items():
        if cod not in ligas:
            ligas[cod] = Liga(codigo=cod[:30], nome=f"{cod} (criada na carga)"[:120], apelidos=[], densidade=dens)
            db.add(ligas[cod])
    db.flush()

    # itens
    itens: dict[tuple, ItemMP] = {}
    for ch, it in pl.itens.items():
        itens[ch] = ItemMP(codigo_mega=it.codigo_mega, descricao=it.descricao, liga_id=ligas[it.liga].id,
                           formato=it.formato, espessura=it.espessura, largura=it.largura, diametro=it.diametro,
                           comprimento_fixado=(it.comprimento_fixado or None) and str(it.comprimento_fixado)[:120],
                           observacao_uso=it.observacao_uso)
        db.add(itens[ch])
    db.flush()
    for ch, it in pl.itens.items():
        if it.substituido_por in itens:
            itens[ch].substituido_por_id = itens[it.substituido_por].id

    # contêineres e lotes (saldo entra pelos movimentos)
    cts: dict[str, Conteiner] = {}
    lotes: dict[int, Lote] = {}
    for n, lp in enumerate(pl.lotes, start=1):
        ct = None
        if lp.conteiner:
            ct = cts.get(lp.conteiner)
            if ct is None:
                ct = cts[lp.conteiner] = Conteiner(codigo=lp.conteiner[:30])
                db.add(ct)
                db.flush()
        lote = Lote(codigo=f"L-{n:06d}", conteiner_id=ct.id if ct else None, item_mp_id=itens[lp.item].id,
                    planta_fiscal=lp.planta, local_fisico=lp.local, tipo=lp.tipo,
                    origem_identificada=lp.origem_identificada, peso_inicial_kg=round(lp.peso_inicial, 3),
                    pecas_iniciais=lp.pecas, saldo_kg=0.0, custo_kg=lp.custo_kg, documento_entrada=lp.documento,
                    status="ATIVO", criado_por_id=usuario_id, origem_ref=lp.origem)
        db.add(lote)
        lotes[id(lp)] = lote
    db.flush()

    # COPs, solicitações e cortes
    cops: dict[int, Cop] = {}
    for num, c in pl.cops.items():
        dt = max(c["datas"]) if c["datas"] else None
        cops[num] = Cop(numero=num, situacao="RECEBIDO" if c["recebidos"] == c["itens"] else "ENVIADO",
                        criado_em=_ts(min(c["datas"])) if c["datas"] else datetime.now(timezone.utc),
                        fechado_em=_ts(dt),
                        enviado_em=_ts(dt), recebido_em=_ts(dt) if c["recebidos"] == c["itens"] else None,
                        origem_ref={"arquivo": "CONTROLE DE CORTE - RIO DE JANEIRO.xlsx"},
                        observacao="Importado do Controle de Corte")
        db.add(cops[num])
    db.flush()
    libs: dict[int, LiberacaoCorte] = {}
    sols: dict[int, SolicitacaoCorte] = {}
    for sp in pl.solicitacoes:
        lote = lotes[id(sp.lote)]
        e, l, c = sp.acabada
        s = SolicitacaoCorte(op=sp.op, item_codigo=sp.item_codigo, cliente=sp.cliente, op_confirmada_mega=True,
                             lote_id=lote.id, modo=sp.modo, quantidade=sp.quantidade, formato=sp.formato,
                             acabada_espessura=e if sp.formato != "REDONDO" else None,
                             acabada_largura=l if sp.formato != "REDONDO" else None,
                             acabada_diametro=e if sp.formato == "REDONDO" else None, acabada_comprimento=c,
                             peso_previsto_kg=sp.peso_previsto, instrucao=sp.instrucao,
                             instrucao_processo=sp.instrucao_processo, observacao=sp.observacao, prazo=sp.prazo,
                             situacao=sp.situacao, enviada_em=_ts(sp.data), criado_em=_ts(sp.data) or None,
                             origem_ref=sp.origem)
        if s.criado_em is None:
            s.criado_em = datetime.now(timezone.utc)
        db.add(s)
        sols[id(sp)] = s
    db.flush()
    for sp in pl.solicitacoes:
        for lp in sp.liberacoes:
            lib = LiberacaoCorte(solicitacao_id=sols[id(sp)].id, lote_id=lotes[id(lp.lote)].id, pecas=lp.pecas,
                                 peso_real_kg=lp.peso_kg, data_corte=lp.data, origem_ref=lp.origem,
                                 observacao="Importado do Controle de Corte")
            db.add(lib)
            libs[id(lp)] = lib
    db.flush()
    itens_cop: dict[int, CopItem] = {}
    for sp in pl.solicitacoes:
        for lp in sp.liberacoes:
            if lp.cop and lp.situacao_item:
                itens_cop[id(lp)] = CopItem(cop_id=cops[lp.cop].id, liberacao_id=libs[id(lp)].id,
                                            situacao=lp.situacao_item,
                                            recebido_em=_ts(lp.data) if lp.situacao_item == "RECEBIDO" else None)
                db.add(itens_cop[id(lp)])
    db.flush()

    # movimentos (imutáveis) e saldo
    saldo: dict[int, float] = defaultdict(float)
    n_mov = 0
    for lp in pl.lotes:
        lote = lotes[id(lp)]
        for m in lp.movimentos:
            lib: LibP | None = m.liberacao
            dblib = libs.get(id(lib)) if lib is not None else None
            db.add(Movimento(lote_id=lote.id, tipo=m.tipo, kg=round(m.kg, 3), op=m.op, documento=m.documento,
                             data_referencia=m.data, justificativa=m.justificativa, usuario_id=usuario_id,
                             liberacao_id=dblib.id if dblib else None,
                             solicitacao_id=dblib.solicitacao_id if dblib else None, origem_ref=m.origem))
            saldo[lote.id] += m.kg
            n_mov += 1
    for lote in lotes.values():
        s = round(saldo.get(lote.id, 0.0), 3)
        if s < -0.001:
            raise CargaRecusada(f"Lote {lote.codigo} ficaria negativo ({s}).")
        lote.saldo_kg = max(s, 0.0)
        lote.status = "ATIVO" if lote.saldo_kg > 0.0005 else "ESGOTADO"

    # notas, restrições, paridade
    for lp in pl.lotes:
        lote = lotes[id(lp)]
        if lp.notas:
            db.add(Nota(entidade="LOTE", entidade_id=lote.id, texto="\n".join(lp.notas)[:2000], usuario_id=usuario_id))
        for tipo, desc in lp.destinacoes:
            db.add(Destinacao(lote_id=lote.id, tipo=tipo, descricao=desc, criado_por_id=usuario_id))
    vistas = set()
    for p in pl.paridades:
        d = p["descricao_rj"][:200]
        if d in vistas:
            continue
        vistas.add(d)
        db.add(ParidadeRj(descricao_rj=d, item_mp_id=itens[p["item_mp"]].id if p["item_mp"] in itens else None,
                          confirmada=False))

    # SAs históricos. R036 (4): a NF de transferência da planilha de SA vai para o SA e, quando o SA é da mesma
    # OP + contêiner de um corte com COP, também para o item do COP (e o SA fica ligado a esse item).
    nfs: dict[str, NfTransferencia] = {}
    usados: set[int] = set()

    def _nf(extras: dict) -> NfTransferencia | None:
        for k, v in extras.items():
            ku = str(k).upper()
            if ("FIOCERTO" in ku or "MEDIO VALE" in ku) and "TRANSF" not in ku and v not in (None, "", "-"):
                num = str(int(v)) if isinstance(v, int | float) else str(v).strip()[:20]
                if num not in nfs:
                    nfs[num] = NfTransferencia(numero=num, emitente=EMITENTE_CARGA)
                    db.add(nfs[num])
                return nfs[num]
        return None
    for sp in pl.sas:
        x = sp.linha
        dt = x.data if x.data and x.data.year >= 2010 else date(int(x.origem["aba"]), 1, 1)
        extra = {"valor_precificador": x.valor_precificador, **x.extras}
        if x.sa_codigo_texto and not x.sa_codigo_texto.isdigit():
            extra["sa_codigo_texto"] = x.sa_codigo_texto
            if "INAT" in x.sa_codigo_texto.upper():
                extra["inativo_na_planilha"] = True
        nf = _nf(x.extras)
        item_cop = None
        if sp.solicitacao is not None:
            cand = [itens_cop[id(lp)] for lp in sp.solicitacao.liberacoes if id(lp) in itens_cop]
            if len(cand) == 1 and id(cand[0]) not in usados:
                item_cop = cand[0]
                usados.add(id(item_cop))
        if nf is not None:
            db.flush()
            if item_cop is not None and item_cop.nf_id is None:
                item_cop.nf_id = nf.id
        db.add(CadastroSa(origem="CARGA", situacao="CONFIRMADO", data=dt, op=x.op, item_codigo=x.item,
                          nf_id=nf.id if nf is not None else None,
                          cop_item_id=item_cop.id if item_cop is not None else None,
                          cliente=x.cliente, pedido=(x.pedido or None) and str(x.pedido)[:40],
                          material=(x.material or "")[:60] or None, dimensao=(x.dimensao or "")[:60] or None,
                          conteiner=(x.origem_ct or "")[:30] or None, quantidade=x.qtde, peso_kg=x.peso,
                          sa_codigo=x.sa_codigo, sa_descricao=(x.descricao or "")[:200] or None,
                          ncm=(x.ncm or "")[:15] or None, icms=(x.icms or "")[:10] or None,
                          ipi=(x.ipi or "")[:10] or None, confirmado_em=_ts(dt),
                          solicitacao_id=sols[id(sp.solicitacao)].id if sp.solicitacao else None,
                          lote_id=lotes[id(sp.lote)].id if sp.lote else None,
                          dados_extra={k: v for k, v in extra.items() if v is not None} or None, origem_ref=x.origem))
    db.flush()
    resumo = {"itens": len(itens), "lotes": len(lotes), "movimentos": n_mov, "solicitacoes": len(sols),
              "cortes": len(libs), "cops": len(cops), "sas": len(pl.sas), "ligas_novas": len(pl.ligas_novas),
              "arquivos": arquivos, "saldo_mega_de": pl.data_mega}
    auditoria.registrar(db, "CARGA_INICIAL", usuario_id=usuario_id, entidade="carga", entidade_id="T25",
                        depois=resumo)
    return resumo


def conferencia_banco(db: Session) -> list[dict[str, Any]]:
    """Conferência feita no banco depois de gravar (o que o sistema mostra de verdade)."""
    out = []

    def add(nome, planilha, sistema, tol=5.0, obs=None):
        dif = None if planilha is None or sistema is None else round(sistema - planilha, 3)
        out.append({"conferencia": nome, "planilha": planilha, "sistema": sistema, "diferenca": dif,
                    "tolerancia": tol, "resultado": "OK" if dif is not None and abs(dif) <= tol else "DIFERENTE",
                    "observacao": obs})
    por_cod = dict(db.execute(select(ItemMP.codigo_mega, func.sum(Lote.saldo_kg)).join(Lote, Lote.item_mp_id ==
                                                                                       ItemMP.id)
                              .where(Lote.planta_fiscal == "ITU", Lote.local_fisico == "ITU",
                                     ItemMP.codigo_mega.is_not(None)).group_by(ItemMP.codigo_mega)).all())
    # só os códigos do catálogo (item_mp); os de fora (não aço) estão nas pendências CM_FORA_DO_CATALOGO
    catalogo = set(db.scalars(select(ItemMP.codigo_mega).where(ItemMP.codigo_mega.is_not(None))))
    mega = {c: float(s) for c, s in db.execute(select(MegaSaldo.codigo, MegaSaldo.saldo_kg)) if c in catalogo}
    difs = [(c, mega.get(c, 0.0), float(por_cod.get(c) or 0)) for c in set(mega) | set(por_cod)
            if abs(float(por_cod.get(c) or 0) - max(mega.get(c, 0.0), 0.0)) > 5.0]
    add("(a) Códigos Mega com soma dos lotes ≠ saldo Mega (> 5 kg)", 0, len(difs), 0,
        obs="; ".join(f"{c}: Mega {m:.1f} × lotes {l:.1f}" for c, m, l in sorted(difs)[:30]) or None)
    tot = lambda pf, lf: float(db.scalar(select(func.coalesce(func.sum(Lote.saldo_kg), 0)).where(  # noqa: E731
        Lote.planta_fiscal == pf, Lote.local_fisico == lf)) or 0)
    out.append({"conferencia": "Saldos no banco por estoque", "planilha": None, "sistema": None, "diferenca": None,
                "tolerancia": None, "resultado": "INFO",
                "observacao": f"Estoque Mega {tot('ITU', 'ITU'):.1f} kg · RJ no Rio {tot('RJ', 'RJ'):.1f} kg · "
                              f"RJ em Itu {tot('RJ', 'ITU'):.1f} kg"})
    return out
