"""T13 Corte em Itu: consumo da OP, sobra e perda de corte, em lote RJ em Itu ou Estoque Mega. Lote fiscal RJ gera
a linha de SA (caminho B2), exceto o 1º corte da peça inteira para a própria OP, que já teve SA no COP.

Sobra (spec v3.13, regra do RETO, Eduardo, 2026-11-17; detalhes pelas propostas padrão da P35 até a resposta):
- mantém a bitola → fica no lote (nada muda);
- não mantém, placa/blooming (formato RETANGULAR ou RETO) → o operador informa E × L da sobra; E ≤ RETO_ESP_LIMITE e
  L < RETO_LARG_MAX_ATE_LIMITE, ou E > RETO_ESP_LIMITE e L < RETO_LARG_MAX_ACIMA → lote RETO filho (GERA_RETO);
  senão → lote novo (tipo SOBRA) com a medida E × L, filho do de origem (GERA_SOBRA), no mesmo estoque [P35(c)];
- redondo → a sobra sempre fica no lote: o corte é perpendicular e não muda o Ø (Eduardo, 2026-11-19, pendências 2);
- "Conferi a regra do RETO" é obrigatório na placa [P35(b)].
No Estoque Mega, o lote novo não tem transferência no "Fazer no Mega": o kg continua no código do lote de origem
(`estoque.codigo_mega_do_lote`)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Config
from app.domain import regras
from app.domain.formato import kg_br, numero_br, pct_br
from app.domain.validacao import Nivel, Resultado
from app.models import CopItem, CorteItu, ItemMP, Lote, SolicitacaoCorte, Usuario

from . import auditoria, movimentos, ops, sas
from .base import Previa, exigir_sem_pendencias, hoje, parametro
from .estoque import bitola, chave_lote, codigo_mega_do_lote
from .fluxo import recalcular_solicitacao


@dataclass
class CorteItuEntrada:
    op: int
    lote_id: int
    consumo_kg: float
    sobra_kg: float = 0.0
    sobra_na_bitola: bool = True
    pecas: int | None = None
    peso_usado_kg: float | None = None     # peso do material antes do corte; padrão = saldo do lote
    previsto_kg: float | None = None       # vem do T07 "Registrar corte em Itu agora"
    data_corte: date | None = None
    observacao: str | None = None
    op_manual: dict | None = None
    consumo_misto: bool = False            # parte de Itu de uma OP com consumo Itu + RJ (P26, opção A)
    # spec v3.13 (regra do RETO, P35): medida da sobra fora da bitola e confirmação do operador
    sobra_espessura_mm: float | None = None
    sobra_largura_mm: float | None = None
    sobra_diametro_mm: float | None = None   # redondo que não vai para RETO
    sobra_vai_para_reto: bool | None = None  # redondo: escolha do operador (placa: a regra decide)
    conferi_regra_reto: bool = False
    confirmacoes: dict[str, str] = field(default_factory=dict)


def _solicitacao_da_peca_inteira(db: Session, lote: Lote, op: int) -> SolicitacaoCorte | None:
    item = db.scalar(select(CopItem).where(CopItem.lote_itu_id == lote.id))
    if item is None:
        return None
    sol = item.liberacao.solicitacao
    return sol if sol.op == op and sol.situacao == "AGUARDANDO_CORTE_ITU" else None


def _destino_sobra(db: Session, lote: Lote, e: CorteItuEntrada) -> tuple[dict | None, Resultado]:
    """Regra do RETO (T13, spec v3.13). Devolve o bloco `regra_reto` da prévia (None = sem sobra fora da bitola)."""
    r = Resultado()
    if not (e.sobra_kg > 0 and not e.sobra_na_bitola):
        return None, r
    redondo = lote.item.formato == "REDONDO"
    lim = {"esp_limite_mm": parametro(db, "RETO_ESP_LIMITE"),
           "larg_max_ate_limite_mm": parametro(db, "RETO_LARG_MAX_ATE_LIMITE"),
           "larg_max_acima_mm": parametro(db, "RETO_LARG_MAX_ACIMA")}
    bloco: dict = {"aplicavel": not redondo, "formato": "REDONDO" if redondo else "PLACA", "limites": lim,
                   "espessura_mm": e.sobra_espessura_mm, "largura_mm": e.sobra_largura_mm,
                   "diametro_mm": e.sobra_diametro_mm, "destino": None, "vai_para_reto": None,
                   "texto_regra": None, "texto_resultado": None, "conferida": bool(e.conferi_regra_reto)}
    if redondo:
        # Eduardo, 2026-11-19 (pendências item 2): o redondo é cortado na perpendicular ("como calabresa") e nunca
        # perde o diâmetro: a sobra continua no lote, nunca vai para RETO nem vira lote novo.
        bloco["texto_regra"] = "Redondo: a sobra continua no lote (o corte não muda o diâmetro)."
        r.adicionar("SOBRA_REDONDO_NA_BITOLA", Nivel.ERRO,
                    "Redondo não muda de medida no corte: a sobra continua no lote. Marque \"Sim, fica no lote\".")
        return bloco, r
    else:
        esp, larg = e.sobra_espessura_mm, e.sobra_largura_mm
        _, bloco["texto_regra"], _ = regras.regra_reto(1, 1, lim["esp_limite_mm"], lim["larg_max_ate_limite_mm"],
                                                        lim["larg_max_acima_mm"])
        if not esp or not larg or esp <= 0 or larg <= 0:
            r.adicionar("MEDIDA_SOBRA_OBRIGATORIA", Nivel.ERRO,
                        "Sobra fora da bitola: informe a espessura (E) e a largura (L) da sobra, em mm.")
        else:
            vai, _, bloco["texto_resultado"] = regras.regra_reto(esp, larg, lim["esp_limite_mm"],
                                                                 lim["larg_max_ate_limite_mm"],
                                                                 lim["larg_max_acima_mm"])
            bloco.update(destino="RETO" if vai else "LOTE_NOVO", vai_para_reto=vai)
            if esp > larg:
                r.adicionar("MEDIDA_SOBRA_INVERTIDA", Nivel.ALERTA,
                            f"A espessura informada ({esp:g} mm) é maior que a largura ({larg:g} mm). "
                            "Confira: a regra usa E e L como digitados.")
            r.adicionar("REGRA_RETO", Nivel.ALERTA, f"{bloco['texto_regra']} {bloco['texto_resultado']}",
                        destino=bloco["destino"])
    if not e.conferi_regra_reto:
        r.adicionar("REGRA_RETO_NAO_CONFERIDA", Nivel.ERRO, "Marque \"Conferi a regra do RETO\" para confirmar.")
    return bloco, r


def _medida_sobra(lote: Lote, e: CorteItuEntrada) -> str:
    if lote.item.formato == "REDONDO":
        return f"Ø{e.sobra_diametro_mm:g}"
    return f"{e.sobra_espessura_mm:g}X{e.sobra_largura_mm:g}"


def item_da_sobra(db: Session, lote: Lote, e: CorteItuEntrada) -> ItemMP:
    """Item do lote novo com a medida da sobra [P35(c)]: mesma liga, sem código do Mega (o kg do Estoque Mega fica
    no código do lote de origem, `estoque.codigo_mega_do_lote`), sem comprimento e sem múltiplo. Cria se não existir."""
    it = lote.item
    redondo = it.formato == "REDONDO"
    q = select(ItemMP).where(ItemMP.liga_id == it.liga_id, ItemMP.codigo_mega.is_(None), ItemMP.ativo.is_(True),
                             ItemMP.formato == ("REDONDO" if redondo else "RETANGULAR"))
    q = (q.where(ItemMP.diametro == e.sobra_diametro_mm) if redondo else
         q.where(ItemMP.espessura == e.sobra_espessura_mm, ItemMP.largura == e.sobra_largura_mm))
    for x in db.scalars(q.order_by(ItemMP.id)):
        k = chave_lote(x)
        if k.comprimento is None and not k.multiplo:
            return x
    novo = ItemMP(descricao=f"{it.liga.codigo} {_medida_sobra(lote, e)}", liga_id=it.liga_id,
                  formato="REDONDO" if redondo else "RETANGULAR",
                  espessura=None if redondo else e.sobra_espessura_mm, largura=None if redondo else e.sobra_largura_mm,
                  diametro=e.sobra_diametro_mm if redondo else None)
    db.add(novo)
    db.flush()
    return novo


def validar(db: Session, cfg: Config, e: CorteItuEntrada) -> tuple[Previa, ops.DadosOp, Lote, SolicitacaoCorte | None]:
    lote = movimentos.lote_ou_404(db, e.lote_id)
    p = Previa()
    r = p.resultado
    dados = ops.consultar(db, e.op)
    if not dados.confirmada_mega and e.op_manual:
        dados.item_codigo = e.op_manual.get("item_codigo") or dados.item_codigo
        dados.cliente = e.op_manual.get("cliente") or dados.cliente
    if not dados.encontrada:
        r.adicionar("OP_INEXISTENTE", Nivel.ERRO, "OP não encontrada no Mega.")
    elif dados.aberta is False:
        r.adicionar("OP_ENCERRADA", Nivel.ERRO, f"A OP está {dados.situacao_descricao} no Mega.")
    if not dados.confirmada_mega:
        r.adicionar("OP_NAO_CONFIRMADA", Nivel.ALERTA, "Dado não confirmado no Mega (Mega fora do ar).")
    if lote.local_fisico != "ITU":
        r.adicionar("LOTE_FORA_DE_ITU", Nivel.ERRO, "O lote está no RJ: o corte é feito pela solicitação ao RJ.")
    if e.consumo_kg <= 0 or e.sobra_kg < 0:
        r.adicionar("PESO_INVALIDO", Nivel.ERRO, "Consumo deve ser maior que zero e a sobra não pode ser negativa.")
    saldo = float(lote.saldo_kg)
    usado = e.peso_usado_kg if e.peso_usado_kg is not None else saldo
    if usado > saldo + 1e-6:
        r.adicionar("SALDO_INSUFICIENTE", Nivel.ERRO,
                    f"O material usado ({kg_br(usado)}) é maior que o saldo do lote ({kg_br(saldo)}).")
    sol = _solicitacao_da_peca_inteira(db, lote, e.op)
    previsto = e.previsto_kg or (float(sol.peso_previsto_kg) if sol else None)
    # P22(a) (spec v3.5): 8 % para material inteiro do RJ (lote fiscal RJ em Itu, inclusive a peça inteira recebida
    # e o RETO RJ em Itu); 5 % para lote do Estoque Mega. A mensagem diz qual limite foi usado.
    material_rj = lote.planta_fiscal == "RJ"
    limite_pct = (parametro(db, "TOLERANCIA_EXCESSO_RJ_INTEIRO_PCT") if material_rj
                  else parametro(db, "TOLERANCIA_EXCESSO_PCT", cfg))
    if previsto and e.consumo_kg > 0:
        r.juntar(regras.validar_peso_real(previsto, e.consumo_kg, limite_pct,
                                          parametro(db, "TOLERANCIA_FALTA_PCT", cfg),
                                          limite_de="material do RJ" if material_rj else "lote do Estoque Mega"))
    it = lote.item
    max_pct = parametro(db, "PERDA_CORTE_MAX_PCT")
    if e.consumo_kg > 0 and e.sobra_kg >= 0:
        r.juntar(regras.validar_perda_corte(usado, e.consumo_kg, e.sobra_kg, max_pct))
    outros = movimentos.reservado(db, [lote.id], exceto_solicitacao=sol.id if sol else None).get(lote.id, 0.0)
    if e.consumo_kg > 0 and e.consumo_kg <= saldo:
        r.juntar(regras.validar_saldo(saldo, outros, e.consumo_kg))
    r.juntar(regras.validar_destinacoes([regras.Destinacao(d.tipo, d.descricao, d.validade)
                                         for d in movimentos.destinacoes_vigentes(db, lote.id)]))
    d = e.data_corte or hoje()
    dias = int(parametro(db, "CORTE_DIAS_RETROATIVOS"))
    if d > hoje() or d < hoje() - timedelta(days=dias):
        r.adicionar("DATA_CORTE_INVALIDA", Nivel.ERRO, f"A data do corte deve ser de hoje até {dias} dias atrás.")
    perda = round(max(usado - e.consumo_kg - e.sobra_kg, 0), 3)
    regra, r_regra = _destino_sobra(db, lote, e)
    r.juntar(r_regra)
    destino = regra["destino"] if regra else None
    fora = e.sobra_kg > 0 and not e.sobra_na_bitola           # a sobra sai do lote (RETO ou lote novo)
    reto = destino == "RETO"
    depois = round(saldo - e.consumo_kg - perda - (e.sobra_kg if fora else 0), 3)
    ct = lote.conteiner.codigo if lote.conteiner else "sem contêiner"
    p.frase = (f"Lote {lote.codigo} passa de {kg_br(saldo)} para {kg_br(max(depois, 0))}."
               + (f" Novo lote RETO com {kg_br(e.sobra_kg)}, origem {it.liga.codigo} {bitola(it)} / {ct}."
                  if reto else "")
               + (f" Novo lote {it.liga.codigo} {_medida_sobra(lote, e)} com {kg_br(e.sobra_kg)} (sobra fora da "
                  f"regra do RETO), origem {it.liga.codigo} {bitola(it)} / {ct}." if destino == "LOTE_NOVO" else "")
               + (f" Perda de corte {kg_br(perda)} ({pct_br(perda / usado * 100, 1)} do material usado)."
                  if perda > 0 and usado > 0 else ""))
    p.efeitos = [{"lote": lote.codigo, "antes_kg": round(saldo, 3), "depois_kg": max(depois, 0)}]
    if reto:
        p.efeitos.append({"lote": "(novo RETO)", "antes_kg": 0.0, "depois_kg": round(e.sobra_kg, 3)})
    elif destino == "LOTE_NOVO":
        p.efeitos.append({"lote": f"(novo lote {it.liga.codigo} {_medida_sobra(lote, e)})", "antes_kg": 0.0,
                          "depois_kg": round(e.sobra_kg, 3)})
    gera_sa = lote.planta_fiscal == "RJ" and sol is None
    p.extra.update({"perda_kg": perda, "perda_pct": round(perda / usado * 100, 2) if usado > 0 else 0.0,
                    "perda_max_pct": max_pct, "perda_max_kg": round(usado * max_pct / 100, 3),
                    "peso_usado_kg": round(usado, 3), "previsto_kg": previsto,
                    "tolerancia_excesso_pct": limite_pct, "consumo_misto": e.consumo_misto,
                    "gera_sa": gera_sa, "liga_solicitacao_id": sol.id if sol else None, "regra_reto": regra,
                    "instrucao_mega": instrucao_mega(lote, e.op, e.consumo_kg + perda, e.sobra_kg if reto else 0, db)
                    if lote.planta_fiscal == "ITU" else None})
    return p, dados, lote, sol


def instrucao_mega(lote: Lote, op: int, baixa_kg: float, reto_kg: float, db: Session) -> str | None:
    """Caminho C: o que o Fabiano faz no Mega depois de confirmar (baixa na OP e transferência para RETO)."""
    cod = codigo_mega_do_lote(lote)
    if not cod:
        return None
    t = f"Baixar {numero_br(baixa_kg, 1)} kg do código {cod} na OP {op}."
    if reto_kg > 0:
        r = movimentos.item_reto(db, lote.item.liga_id)
        destino = f"o código {r.codigo_mega} ({r.descricao})" if r.codigo_mega else f"o RETO de {lote.item.liga.codigo}"
        t += f" Transferir {numero_br(reto_kg, 1)} kg do código {cod} para {destino}."
    return t


def registrar(db: Session, cfg: Config, e: CorteItuEntrada, *, usuario: Usuario, ip: str | None) -> CorteItu:
    # trava ANTES de validar: perda e "material usado" saem do mesmo saldo (revisão de 2026-11-18)
    movimentos.travar_lotes(db, [e.lote_id])
    previa, dados, lote, sol = validar(db, cfg, e)
    conf = exigir_sem_pendencias(previa, e.confirmacoes)
    lote = movimentos.lote_ou_404(db, lote.id, travar=True)
    perda = previa.extra["perda_kg"]
    usado = e.peso_usado_kg if e.peso_usado_kg is not None else float(lote.saldo_kg)
    regra = previa.extra["regra_reto"]
    destino = regra["destino"] if regra else None
    reto = destino == "RETO"
    placa = bool(regra) and regra["formato"] == "PLACA"
    c = CorteItu(op=e.op, item_codigo=dados.item_codigo, cliente=dados.cliente, lote_id=lote.id,
                 solicitacao_id=sol.id if sol else None, pecas=e.pecas, peso_usado_kg=round(usado, 3),
                 consumo_kg=round(e.consumo_kg, 3), sobra_kg=round(e.sobra_kg, 3), sobra_na_bitola=e.sobra_na_bitola,
                 perda_kg=perda, previsto_kg=previa.extra["previsto_kg"], observacao=e.observacao,
                 confirmacoes=conf or None, data_corte=e.data_corte or hoje(), usuario_id=usuario.id,
                 instrucao_mega=previa.extra["instrucao_mega"], consumo_misto=e.consumo_misto,
                 sobra_destino=destino, regra_reto=regra,
                 sobra_espessura_mm=e.sobra_espessura_mm if placa else None,
                 sobra_largura_mm=e.sobra_largura_mm if placa else None,
                 sobra_diametro_mm=e.sobra_diametro_mm if destino == "LOTE_NOVO" and not placa else None)
    db.add(c)
    db.flush()
    just = "; ".join(conf.values()) or None
    comum = {"usuario_id": usuario.id, "op": e.op, "corte_itu_id": c.id, "data_referencia": c.data_corte,
             "solicitacao_id": c.solicitacao_id}
    movimentos.lancar(db, lote, "CONSUMO_OP", -e.consumo_kg, pecas=e.pecas, justificativa=just,
                      confirmacoes=conf or None, **comum)
    if perda > 0:
        movimentos.lancar(db, lote, "PERDA_CORTE", -perda, **comum)
    if reto:
        movimentos.lancar(db, lote, "GERA_RETO", -e.sobra_kg, **comum)
        novo = movimentos.criar_lote(db, item=movimentos.item_reto(db, lote.item.liga_id,
                                                                     com_codigo=lote.planta_fiscal == "ITU"),
                                     planta_fiscal=lote.planta_fiscal, local_fisico=lote.local_fisico, tipo="RETO",
                                     pai=lote, peso_inicial_kg=e.sobra_kg, usuario_id=usuario.id)
        movimentos.lancar(db, novo, "GERA_RETO", e.sobra_kg, **comum)
        c.lote_reto_id = novo.id
    elif destino == "LOTE_NOVO":
        # P35(c) [proposta]: lote novo com a medida da sobra, filho do de origem, no mesmo estoque
        movimentos.lancar(db, lote, "GERA_SOBRA", -e.sobra_kg, **comum)
        novo = movimentos.criar_lote(db, item=item_da_sobra(db, lote, e), planta_fiscal=lote.planta_fiscal,
                                     local_fisico=lote.local_fisico, tipo="SOBRA", pai=lote,
                                     peso_inicial_kg=e.sobra_kg, usuario_id=usuario.id)
        movimentos.lancar(db, novo, "GERA_SOBRA", e.sobra_kg, **comum)
        c.lote_sobra_id = novo.id
    if sol is not None:
        recalcular_solicitacao(db, sol)
    elif lote.planta_fiscal == "RJ":
        sas.criar_linha(db, origem="CORTE_ITU", lote=lote, op=e.op, item_codigo=dados.item_codigo,
                        item_descricao=dados.item_descricao, cliente=dados.cliente, pedido=dados.pedido,
                        quantidade=e.pecas, peso_kg=e.consumo_kg, corte_itu_id=c.id)
    auditoria.registrar(db, "CORTE_ITU_REGISTRADO", usuario_id=usuario.id, entidade="corte_itu", entidade_id=c.id,
                        depois={"op": e.op, "lote": lote.codigo, "consumo_kg": e.consumo_kg, "sobra_kg": e.sobra_kg,
                                "reto": reto, "sobra_destino": destino, "perda_kg": perda,
                                "regra_reto_conferida": bool(regra and e.conferi_regra_reto),
                                "confirmacoes": conf}, ip=ip)
    db.commit()
    return c


def para_dict(db: Session, c: CorteItu) -> dict:
    reto = db.get(Lote, c.lote_reto_id) if c.lote_reto_id else None
    sobra = db.get(Lote, c.lote_sobra_id) if c.lote_sobra_id else None
    from app.models import CadastroSa
    sa = db.scalar(select(CadastroSa).where(CadastroSa.corte_itu_id == c.id))
    return {"id": c.id, "op": c.op, "item_codigo": c.item_codigo, "cliente": c.cliente, "lote_id": c.lote_id,
            "lote": c.lote.codigo, "solicitacao_id": c.solicitacao_id, "pecas": c.pecas,
            "peso_usado_kg": c.peso_usado_kg,
            "consumo_kg": c.consumo_kg, "sobra_kg": c.sobra_kg, "sobra_na_bitola": c.sobra_na_bitola,
            "perda_kg": c.perda_kg, "previsto_kg": c.previsto_kg, "consumo_misto": c.consumo_misto,
            "lote_reto": {"id": reto.id, "codigo": reto.codigo} if reto else None,
            "lote_sobra": {"id": sobra.id, "codigo": sobra.codigo, "bitola": bitola(sobra.item)} if sobra else None,
            "sobra_destino": c.sobra_destino, "sobra_espessura_mm": c.sobra_espessura_mm,
            "sobra_largura_mm": c.sobra_largura_mm, "sobra_diametro_mm": c.sobra_diametro_mm,
            "sa_id": sa.id if sa else None, "instrucao_mega": c.instrucao_mega,
            # R058/R060: o corte foi da peça inteira do RJ recebida → a pendência do peso real saiu do Painel
            "pendencia_peso_real_resolvida": c.solicitacao_id is not None,
            "data_corte": c.data_corte.isoformat()}


def lote_sugerido(db: Session, op: int) -> Lote | None:
    """Peça inteira recebida para a OP e ainda aguardando corte em Itu."""
    sol = db.scalar(select(SolicitacaoCorte).where(SolicitacaoCorte.op == op,
                                                   SolicitacaoCorte.situacao == "AGUARDANDO_CORTE_ITU"))
    if sol is None:
        return None
    for lib in sol.liberacoes:
        if lib.cop_item and lib.cop_item.lote_itu_id:
            return db.get(Lote, lib.cop_item.lote_itu_id)
    return None
