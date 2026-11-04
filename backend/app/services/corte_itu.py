"""T13 Corte em Itu: consumo da OP, sobra (fica no lote se mantém a bitola; senão vira lote RETO filho) e perda de
corte, em lote RJ em Itu ou Estoque Mega. Lote fiscal RJ gera a linha de SA (caminho B2), exceto o 1º corte da
peça inteira para a própria OP, que já teve SA no COP."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Config
from app.domain import regras
from app.domain.formato import kg_br, numero_br, pct_br
from app.domain.validacao import Nivel
from app.models import CopItem, CorteItu, Lote, SolicitacaoCorte, Usuario

from . import auditoria, movimentos, ops, sas
from .base import Previa, exigir_sem_pendencias, hoje, parametro
from .estoque import bitola
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
    confirmacoes: dict[str, str] = field(default_factory=dict)


def _solicitacao_da_peca_inteira(db: Session, lote: Lote, op: int) -> SolicitacaoCorte | None:
    item = db.scalar(select(CopItem).where(CopItem.lote_itu_id == lote.id))
    if item is None:
        return None
    sol = item.liberacao.solicitacao
    return sol if sol.op == op and sol.situacao == "AGUARDANDO_CORTE_ITU" else None


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
    if previsto and e.consumo_kg > 0:
        r.juntar(regras.validar_peso_real(previsto, e.consumo_kg, parametro(db, "TOLERANCIA_EXCESSO_PCT", cfg),
                                          parametro(db, "TOLERANCIA_FALTA_PCT", cfg)))
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
    reto = e.sobra_kg > 0 and not e.sobra_na_bitola
    depois = round(saldo - e.consumo_kg - perda - (e.sobra_kg if reto else 0), 3)
    ct = lote.conteiner.codigo if lote.conteiner else "sem contêiner"
    p.frase = (f"Lote {lote.codigo} passa de {kg_br(saldo)} para {kg_br(max(depois, 0))}."
               + (f" Novo lote RETO com {kg_br(e.sobra_kg)}, origem {it.liga.codigo} {bitola(it)} / {ct}."
                  if reto else "")
               + (f" Perda de corte {kg_br(perda)} ({pct_br(perda / usado * 100, 1)} do material usado)."
                  if perda > 0 and usado > 0 else ""))
    p.efeitos = [{"lote": lote.codigo, "antes_kg": round(saldo, 3), "depois_kg": max(depois, 0)}]
    if reto:
        p.efeitos.append({"lote": "(novo RETO)", "antes_kg": 0.0, "depois_kg": round(e.sobra_kg, 3)})
    gera_sa = lote.planta_fiscal == "RJ" and sol is None
    p.extra.update({"perda_kg": perda, "perda_pct": round(perda / usado * 100, 2) if usado > 0 else 0.0,
                    "perda_max_pct": max_pct, "perda_max_kg": round(usado * max_pct / 100, 3),
                    "peso_usado_kg": round(usado, 3), "previsto_kg": previsto,
                    "gera_sa": gera_sa, "liga_solicitacao_id": sol.id if sol else None,
                    "instrucao_mega": instrucao_mega(lote, e.op, e.consumo_kg + perda, e.sobra_kg if reto else 0, db)
                    if lote.planta_fiscal == "ITU" else None})
    return p, dados, lote, sol


def instrucao_mega(lote: Lote, op: int, baixa_kg: float, reto_kg: float, db: Session) -> str | None:
    """Caminho C: o que o Fabiano faz no Mega depois de confirmar (baixa na OP e transferência para RETO)."""
    cod = lote.item.codigo_mega
    if not cod:
        return None
    t = f"Baixar {numero_br(baixa_kg, 1)} kg do código {cod} na OP {op}."
    if reto_kg > 0:
        r = movimentos.item_reto(db, lote.item.liga_id)
        destino = f"o código {r.codigo_mega} ({r.descricao})" if r.codigo_mega else f"o RETO de {lote.item.liga.codigo}"
        t += f" Transferir {numero_br(reto_kg, 1)} kg do código {cod} para {destino}."
    return t


def registrar(db: Session, cfg: Config, e: CorteItuEntrada, *, usuario: Usuario, ip: str | None) -> CorteItu:
    previa, dados, lote, sol = validar(db, cfg, e)
    conf = exigir_sem_pendencias(previa, e.confirmacoes)
    lote = movimentos.lote_ou_404(db, lote.id, travar=True)
    perda = previa.extra["perda_kg"]
    usado = e.peso_usado_kg if e.peso_usado_kg is not None else float(lote.saldo_kg)
    reto = e.sobra_kg > 0 and not e.sobra_na_bitola
    c = CorteItu(op=e.op, item_codigo=dados.item_codigo, cliente=dados.cliente, lote_id=lote.id,
                 solicitacao_id=sol.id if sol else None, pecas=e.pecas, peso_usado_kg=round(usado, 3),
                 consumo_kg=round(e.consumo_kg, 3), sobra_kg=round(e.sobra_kg, 3), sobra_na_bitola=e.sobra_na_bitola,
                 perda_kg=perda, previsto_kg=previa.extra["previsto_kg"], observacao=e.observacao,
                 confirmacoes=conf or None, data_corte=e.data_corte or hoje(), usuario_id=usuario.id,
                 instrucao_mega=previa.extra["instrucao_mega"])
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
        novo = movimentos.criar_lote(db, item=movimentos.item_reto(db, lote.item.liga_id),
                                     planta_fiscal=lote.planta_fiscal, local_fisico=lote.local_fisico, tipo="RETO",
                                     pai=lote, peso_inicial_kg=e.sobra_kg, usuario_id=usuario.id)
        movimentos.lancar(db, novo, "GERA_RETO", e.sobra_kg, **comum)
        c.lote_reto_id = novo.id
    if sol is not None:
        recalcular_solicitacao(db, sol)
    elif lote.planta_fiscal == "RJ":
        sas.criar_linha(db, origem="CORTE_ITU", lote=lote, op=e.op, item_codigo=dados.item_codigo,
                        item_descricao=dados.item_descricao, cliente=dados.cliente, pedido=dados.pedido,
                        quantidade=e.pecas, peso_kg=e.consumo_kg, corte_itu_id=c.id)
    auditoria.registrar(db, "CORTE_ITU_REGISTRADO", usuario_id=usuario.id, entidade="corte_itu", entidade_id=c.id,
                        depois={"op": e.op, "lote": lote.codigo, "consumo_kg": e.consumo_kg, "sobra_kg": e.sobra_kg,
                                "reto": reto, "perda_kg": perda, "confirmacoes": conf}, ip=ip)
    db.commit()
    return c


def para_dict(db: Session, c: CorteItu) -> dict:
    reto = db.get(Lote, c.lote_reto_id) if c.lote_reto_id else None
    from app.models import CadastroSa
    sa = db.scalar(select(CadastroSa).where(CadastroSa.corte_itu_id == c.id))
    return {"id": c.id, "op": c.op, "item_codigo": c.item_codigo, "cliente": c.cliente, "lote_id": c.lote_id,
            "lote": c.lote.codigo, "solicitacao_id": c.solicitacao_id, "pecas": c.pecas,
            "peso_usado_kg": c.peso_usado_kg,
            "consumo_kg": c.consumo_kg, "sobra_kg": c.sobra_kg, "sobra_na_bitola": c.sobra_na_bitola,
            "perda_kg": c.perda_kg, "previsto_kg": c.previsto_kg,
            "lote_reto": {"id": reto.id, "codigo": reto.codigo} if reto else None,
            "sa_id": sa.id if sa else None, "instrucao_mega": c.instrucao_mega,
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
