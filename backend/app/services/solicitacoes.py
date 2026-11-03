"""T07 Nova solicitação, T08 lista e ações, T09 Fila RJ e T10 Registrar corte (especificação v3).

Toda ação que grava tem a prévia (`validar_*`) e a gravação, que repete as validações (contrato §1.5).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.core.config import Config
from app.domain import corte, regras
from app.domain.formato import kg_br, pct_br
from app.domain.validacao import Nivel, Ocorrencia, Resultado
from app.integrations.mega.consultas import SITUACOES_OP
from app.models import (CadastroSa, Conteiner, ItemMP, LiberacaoCorte, Liga, LigaEquivalente, Lote,
                        SolicitacaoCorte, Usuario)

from . import auditoria, movimentos, ops
from .base import (ErroNegocio, NaoEncontrado, Previa, agora, exigir_sem_pendencias, hoje, notificar, parametro,
                   so_rj_no_rio)
from .estoque import BALDE, bitola
from .fluxo import ATIVAS_RJ, material_texto, recalcular_solicitacao

ESTOQUE_ITU = ("ESTOQUE",)


# ---------------- entrada ----------------

@dataclass
class ItemEntrada:
    lote_id: int
    modo: str
    quantidade: int
    sobremetal_comprimento_mm: float | None = None
    sobremetal_largura_mm: float | None = None
    bruto: dict[str, float | None] | None = None
    comprimento_barra_mm: float | None = None
    instrucao: str | None = None
    instrucao_processo: str | None = None


@dataclass
class SolicitacaoEntrada:
    op: int
    medida: dict[str, Any]
    itens: list[ItemEntrada]
    liga: str | None = None
    prazo: date | None = None
    observacao: str | None = None
    op_manual: dict[str, Any] | None = None
    confirmacoes: dict[str, str] = field(default_factory=dict)


def _sufixo(r: Resultado, i: int) -> Resultado:
    """Ocorrências do 2º lote em diante ganham sufixo '#2', '#3'… para a confirmação não colidir."""
    if i == 0:
        return r
    return Resultado([Ocorrencia(f"{o.codigo}#{i + 1}", o.nivel, o.mensagem, {**o.dados, "item": i + 1})
                      for o in r.ocorrencias])


def _dims(d: dict | None, formato: str) -> corte.Dimensoes | None:
    if not d:
        return None
    return corte.Dimensoes(formato, d.get("espessura"), d.get("largura"), d.get("diametro"), d.get("comprimento"))


def _bitola_lote(lote: Lote) -> corte.Dimensoes | None:
    it = lote.item
    if it.formato == "RETO":
        return None
    return corte.Dimensoes(it.formato, it.espessura, it.largura, it.diametro)


def ligas_equivalentes(db: Session, liga_id: int) -> set[int]:
    pares = db.execute(select(LigaEquivalente.liga_a_id, LigaEquivalente.liga_b_id).where(
        or_(LigaEquivalente.liga_a_id == liga_id, LigaEquivalente.liga_b_id == liga_id))).all()
    return {a if b == liga_id else b for a, b in pares}


def _validar_liga(db: Session, liga_pedida: str | None, lote: Lote) -> Resultado:
    r = Resultado()
    if not liga_pedida:
        return r
    alvo = db.scalar(select(Liga).where(Liga.codigo == liga_pedida.strip().upper()))
    if alvo is None or alvo.id == lote.item.liga_id:
        return r
    if lote.item.liga_id in ligas_equivalentes(db, alvo.id):
        r.adicionar("LIGA_EQUIVALENTE", Nivel.CIENCIA,
                    f"O lote é de {lote.item.liga.codigo}, equivalente a {alvo.codigo}. Confirme que pode ser usado "
                    "nesta OP.", liga_lote=lote.item.liga.codigo, liga_pedida=alvo.codigo)
    else:
        r.adicionar("LIGA_DIFERENTE", Nivel.CIENCIA,
                    f"O lote é de {lote.item.liga.codigo}, diferente da liga pedida ({alvo.codigo}), e não está "
                    "cadastrada como equivalente. Justifique o uso.", liga_lote=lote.item.liga.codigo,
                    liga_pedida=alvo.codigo)
    return r


def _validar_op(db: Session, dados: ops.DadosOp, ignorar_solicitacao: int | None = None) -> Resultado:
    r = Resultado()
    if not dados.encontrada:
        return r.adicionar("OP_INEXISTENTE", Nivel.ERRO, "OP não encontrada no Mega.")
    if dados.aberta is False:
        r.adicionar("OP_ENCERRADA", Nivel.ERRO,
                    f"A OP está {dados.situacao_descricao or dados.situacao} no Mega.", situacao=dados.situacao)
    elif dados.aberta is None and dados.situacao in SITUACOES_OP:
        r.adicionar("OP_NAO_ABERTA", Nivel.ALERTA,
                    f"A OP está {dados.situacao_descricao} no Mega (ainda não aberta). Confira antes de cortar.",
                    situacao=dados.situacao)
    elif dados.aberta is None and dados.situacao:
        r.adicionar("OP_SITUACAO_DESCONHECIDA", Nivel.ALERTA,
                    f"Situação da OP no Mega desconhecida ({dados.situacao}). Confira se ela está aberta.")
    if not dados.confirmada_mega:
        r.adicionar("OP_NAO_CONFIRMADA", Nivel.ALERTA,
                    "Dado não confirmado no Mega (Mega fora do ar). A confirmação acontece depois.")
    q = select(SolicitacaoCorte.id).where(SolicitacaoCorte.op == dados.numero,
                                          SolicitacaoCorte.situacao != "CANCELADA")
    if ignorar_solicitacao:
        q = q.where(SolicitacaoCorte.id != ignorar_solicitacao)
    ja = db.scalar(q.limit(1)) or db.scalar(select(CadastroSa.id).where(CadastroSa.op == dados.numero).limit(1))
    if ja:
        r.adicionar("OP_DUPLICADA", Nivel.CIENCIA,
                    "Já existe solicitação ou SA para esta OP. Confirme que é uma nova necessidade.")
    return r


@dataclass
class ItemCalculado:
    lote: Lote
    entrada: ItemEntrada
    calc: corte.CalculoCorte
    instrucao: str
    resultado: Resultado


def _calcular_item(db: Session, cfg: Config, e: SolicitacaoEntrada, it: ItemEntrada,
                   ignorar_solicitacao: int | None) -> ItemCalculado:
    lote = movimentos.lote_ou_404(db, it.lote_id)
    r = Resultado()
    if it.modo not in ("CORTAR_RJ", "TRAZER_INTEIRA"):
        r.adicionar("MODO_INVALIDO", Nivel.ERRO, "Modo inválido. Para lote em Itu, use \"Registrar corte em Itu\".")
    if lote.local_fisico != "RJ":
        r.adicionar("MODO_INCOMPATIVEL", Nivel.ERRO,
                    "O lote está em Itu: não há solicitação ao RJ. Use \"Registrar corte em Itu agora\" (T13).")
    if lote.status != "ATIVO" or lote.saldo_kg <= 0:
        r.adicionar("LOTE_SEM_SALDO", Nivel.ERRO, f"O lote {lote.codigo} não tem saldo.")
    formato = (e.medida.get("formato") or lote.item.formato).upper()
    if formato == "RETO":
        formato = "RETANGULAR"
    acabada = _dims(e.medida, formato)
    sm_comp = it.sobremetal_comprimento_mm
    if sm_comp is None:
        sm_comp = parametro(db, "SOBREMETAL_COMPRIMENTO_MM")
    calc = corte.calcular(bitola=_bitola_lote(lote), acabada=acabada, quantidade=it.quantidade,
                          densidade=float(lote.item.liga.densidade), sobremetal_comprimento_mm=sm_comp,
                          sobremetal_largura_mm=it.sobremetal_largura_mm,
                          sobremetal_largura_padrao_mm=parametro(db, "SOBREMETAL_LARGURA_MM"),
                          bruto_informado=_dims(it.bruto, formato))
    if calc.peso_previsto_kg is None:
        r.adicionar("DIMENSOES_INCOMPLETAS", Nivel.ERRO,
                    "Informe a medida acabada (ou as dimensões brutas de corte) completa para calcular o "
                    "peso previsto.")
    b = _bitola_lote(lote)
    if b is not None and acabada is not None:
        r.juntar(regras.validar_bitola(b.espessura, b.largura, b.diametro, acabada.espessura, acabada.largura,
                                       acabada.diametro))
    if calc.peso_previsto_kg and calc.peso_peca_kg:
        r.juntar(regras.validar_sobremetal(calc.peso_previsto_kg, calc.peso_peca_kg,
                                           parametro(db, "TOLERANCIA_SOBREMETAL_PCT", cfg)))
    if calc.peso_previsto_kg:
        outros = movimentos.reservado(db, [lote.id], exceto_solicitacao=ignorar_solicitacao).get(lote.id, 0.0)
        r.juntar(regras.validar_saldo(float(lote.saldo_kg), outros, calc.peso_previsto_kg))
    r.juntar(regras.validar_destinacoes([regras.Destinacao(d.tipo, d.descricao, d.validade)
                                         for d in movimentos.destinacoes_vigentes(db, lote.id)]))
    r.juntar(_validar_liga(db, e.liga, lote))
    if lote.item.substituido_por_id:
        sub = db.get(ItemMP, lote.item.substituido_por_id)
        r.adicionar("ITEM_SUBSTITUIDO", Nivel.ALERTA, f"Este item foi substituído por {sub.descricao}.",
                    substituto_id=sub.id)
    instrucao = it.instrucao or corte.instrucao_padrao(it.modo, it.quantidade, calc.bruto.comprimento,
                                                       lote.item.liga.codigo, bitola(lote.item),
                                                       it.comprimento_barra_mm)
    return ItemCalculado(lote, it, calc, instrucao, r)


def validar(db: Session, cfg: Config, e: SolicitacaoEntrada, *, ignorar_solicitacao: int | None = None
            ) -> tuple[Previa, ops.DadosOp, list[ItemCalculado]]:
    if not e.itens:
        raise ErroNegocio("Escolha pelo menos um lote.")
    dados = ops.consultar(db, e.op)
    if not dados.confirmada_mega and e.op_manual:
        dados.item_codigo = e.op_manual.get("item_codigo") or dados.item_codigo
        dados.item_descricao = e.op_manual.get("item_descricao") or dados.item_descricao
        dados.cliente = e.op_manual.get("cliente") or dados.cliente
    previa = Previa()
    previa.resultado.juntar(_validar_op(db, dados, ignorar_solicitacao))
    itens = [_calcular_item(db, cfg, e, it, ignorar_solicitacao) for it in e.itens]
    frases = []
    for i, ic in enumerate(itens):
        previa.resultado.juntar(_sufixo(ic.resultado, i))
        c = ic.calc
        previa.efeitos.append({
            "lote": ic.lote.codigo, "lote_id": ic.lote.id, "material": f"{ic.lote.item.liga.codigo} "
            f"{bitola(ic.lote.item)}", "conteiner": ic.lote.conteiner.codigo if ic.lote.conteiner else None,
            "modo": ic.entrada.modo, "quantidade": ic.entrada.quantidade,
            "bruto": {"espessura": c.bruto.espessura, "largura": c.bruto.largura, "diametro": c.bruto.diametro,
                      "comprimento": c.bruto.comprimento},
            "sobremetal_largura_mm": c.sobremetal_largura_mm, "usa_largura_inteira": c.usa_largura_inteira,
            "comprimento_corte_mm": c.bruto.comprimento, "peso_peca_kg": c.peso_peca_kg,
            "peso_previsto_kg": c.peso_previsto_kg, "sobremetal_pct": c.sobremetal_pct, "instrucao": ic.instrucao,
            "saldo_kg": round(float(ic.lote.saldo_kg), 3)})
        if c.peso_previsto_kg:
            frases.append(f"{ic.entrada.quantidade} peça(s), {kg_br(c.peso_previsto_kg)} previstos do lote "
                          f"{ic.lote.codigo} ({material_texto_lote(ic.lote)})"
                          + (f", sobremetal {pct_br(c.sobremetal_pct, 1)}" if c.sobremetal_pct is not None else ""))
    previa.frase = f"OP {e.op}: " + "; ".join(frases) + ". O peso previsto fica reservado no lote." if frases else None
    previa.extra["op"] = {"numero": dados.numero, "item_codigo": dados.item_codigo,
                          "item_descricao": dados.item_descricao, "cliente": dados.cliente, "pedido": dados.pedido,
                          "situacao": dados.situacao, "confirmada_mega": dados.confirmada_mega}
    return previa, dados, itens


def material_texto_lote(lote: Lote) -> str:
    ct = lote.conteiner.codigo if lote.conteiner else "sem contêiner"
    return f"{lote.item.liga.codigo} {bitola(lote.item)} / {ct}"


def _preencher(sol: SolicitacaoCorte, e: SolicitacaoEntrada, dados: ops.DadosOp, ic: ItemCalculado) -> None:
    c = ic.calc
    sol.op, sol.item_codigo, sol.item_descricao = e.op, dados.item_codigo, dados.item_descricao
    sol.cliente, sol.pedido, sol.op_confirmada_mega = dados.cliente, dados.pedido, dados.confirmada_mega
    sol.lote, sol.modo, sol.quantidade = ic.lote, ic.entrada.modo, ic.entrada.quantidade
    m = e.medida
    sol.formato = c.bruto.formato
    sol.acabada_espessura, sol.acabada_largura = m.get("espessura"), m.get("largura")
    sol.acabada_diametro, sol.acabada_comprimento = m.get("diametro"), m.get("comprimento")
    sol.sobremetal_comprimento_mm = (ic.entrada.sobremetal_comprimento_mm
                                     if ic.entrada.sobremetal_comprimento_mm is not None
                                     else (c.bruto.comprimento or 0) - (m.get("comprimento") or 0))
    sol.sobremetal_largura_mm = c.sobremetal_largura_mm
    sol.bruto_espessura, sol.bruto_largura = c.bruto.espessura, c.bruto.largura
    sol.bruto_diametro, sol.bruto_comprimento = c.bruto.diametro, c.bruto.comprimento
    sol.peso_peca_kg, sol.peso_previsto_kg, sol.sobremetal_pct = c.peso_peca_kg, c.peso_previsto_kg or 0, \
        c.sobremetal_pct
    sol.comprimento_barra_mm = ic.entrada.comprimento_barra_mm
    sol.instrucao, sol.instrucao_processo = ic.instrucao, ic.entrada.instrucao_processo
    sol.prazo = e.prazo or dados.data_entrega
    sol.observacao = e.observacao


def criar(db: Session, cfg: Config, e: SolicitacaoEntrada, *, enviar: bool, usuario: Usuario,
          ip: str | None) -> list[SolicitacaoCorte]:
    previa, dados, itens = validar(db, cfg, e)
    conf = exigir_sem_pendencias(previa, e.confirmacoes) if enviar else {}
    if not enviar and any(o.codigo.startswith(("MODO_", "LOTE_SEM_SALDO", "DIMENSOES")) for o in
                          previa.resultado.erros):
        raise ErroNegocio(previa.resultado.erros[0].mensagem)
    criadas = []
    for ic in itens:
        sol = SolicitacaoCorte(criado_por_id=usuario.id, situacao="RASCUNHO")
        _preencher(sol, e, dados, ic)
        sol.confirmacoes = conf or None
        db.add(sol)
        db.flush()
        if enviar:
            _enviar(db, sol, usuario)
        auditoria.registrar(db, "SOLICITACAO_CRIADA", usuario_id=usuario.id, entidade="solicitacao",
                            entidade_id=sol.id, depois={"op": sol.op, "lote": ic.lote.codigo, "situacao": sol.situacao,
                                                        "previsto_kg": sol.peso_previsto_kg, "confirmacoes": conf},
                            ip=ip)
        criadas.append(sol)
    db.commit()
    return criadas


def _enviar(db: Session, sol: SolicitacaoCorte, usuario: Usuario) -> None:
    sol.situacao = "ENVIADA"
    sol.enviada_em = agora()
    notificar(db, perfis=("OPERACAO_RJ",), tipo="SOLICITACAO_ENVIADA",
              texto=f"Nova solicitação de corte: OP {sol.op}, {sol.quantidade} peça(s), {material_texto(sol)}.",
              link=f"/fila-rj?solicitacao={sol.id}", exceto_id=usuario.id)


def obter(db: Session, sol_id: int, usuario: Usuario | None = None, *, travar: bool = False) -> SolicitacaoCorte:
    q = select(SolicitacaoCorte).where(SolicitacaoCorte.id == sol_id)
    if travar:
        q = q.with_for_update().execution_options(populate_existing=True)
    sol = db.scalar(q)
    if sol is None or (usuario is not None and so_rj_no_rio(usuario) and sol.situacao == "RASCUNHO"):
        raise NaoEncontrado("Solicitação não encontrada.")
    return sol


def atualizar_rascunho(db: Session, cfg: Config, sol_id: int, e: SolicitacaoEntrada, *, enviar: bool,
                       usuario: Usuario, ip: str | None) -> SolicitacaoCorte:
    sol = obter(db, sol_id, travar=True)
    if sol.situacao != "RASCUNHO":
        raise ErroNegocio("Só um rascunho pode ser editado.")
    if len(e.itens) != 1:
        raise ErroNegocio("Um rascunho tem exatamente um lote.")
    previa, dados, itens = validar(db, cfg, e, ignorar_solicitacao=sol.id)
    conf = exigir_sem_pendencias(previa, e.confirmacoes) if enviar else {}
    _preencher(sol, e, dados, itens[0])
    sol.confirmacoes = conf or None
    if enviar:
        _enviar(db, sol, usuario)
    auditoria.registrar(db, "SOLICITACAO_ALTERADA", usuario_id=usuario.id, entidade="solicitacao", entidade_id=sol.id,
                        depois={"situacao": sol.situacao, "confirmacoes": conf}, ip=ip)
    db.commit()
    return sol


def enviar_rascunho(db: Session, cfg: Config, sol_id: int, confirmacoes: dict[str, str], *, usuario: Usuario,
                    ip: str | None) -> SolicitacaoCorte:
    sol = obter(db, sol_id)
    e = entrada_de(sol)
    e.confirmacoes = confirmacoes
    return atualizar_rascunho(db, cfg, sol_id, e, enviar=True, usuario=usuario, ip=ip)


def entrada_de(sol: SolicitacaoCorte, *, lote_id: int | None = None) -> SolicitacaoEntrada:
    """Reconstrói a entrada a partir da solicitação (para reenviar, trocar lote ou duplicar)."""
    medida = {"formato": sol.formato, "espessura": sol.acabada_espessura, "largura": sol.acabada_largura,
              "diametro": sol.acabada_diametro, "comprimento": sol.acabada_comprimento}
    trocou = lote_id is not None and lote_id != sol.lote_id
    it = ItemEntrada(lote_id=lote_id or sol.lote_id, modo=sol.modo, quantidade=sol.quantidade,
                     sobremetal_comprimento_mm=sol.sobremetal_comprimento_mm,
                     sobremetal_largura_mm=None if trocou else sol.sobremetal_largura_mm,
                     bruto=None if trocou else {"espessura": sol.bruto_espessura, "largura": sol.bruto_largura,
                                                "diametro": sol.bruto_diametro, "comprimento": sol.bruto_comprimento},
                     comprimento_barra_mm=sol.comprimento_barra_mm, instrucao=None if trocou else sol.instrucao,
                     instrucao_processo=sol.instrucao_processo)
    manual = None if sol.op_confirmada_mega else {"item_codigo": sol.item_codigo, "item_descricao": sol.item_descricao,
                                                  "cliente": sol.cliente}
    return SolicitacaoEntrada(op=sol.op, medida=medida, itens=[it], prazo=sol.prazo, observacao=sol.observacao,
                              op_manual=manual, liga=sol.lote.item.liga.codigo)


# ---------------- ações da lista (T08) ----------------

def _justificativa(texto: str | None, campo: str = "justificativa") -> str:
    t = (texto or "").strip()
    if len(t) < 10:
        raise ErroNegocio(f"A {campo} precisa ter pelo menos 10 caracteres.")
    return t


def cancelar(db: Session, sol_id: int, motivo: str | None, *, usuario: Usuario, ip: str | None) -> SolicitacaoCorte:
    sol = obter(db, sol_id, travar=True)
    if sol.situacao not in ("RASCUNHO", "ENVIADA", "MATERIAL_INSUFICIENTE"):
        raise ErroNegocio("Só é possível cancelar antes do corte. Depois do corte, use o estorno.")
    if movimentos.liberacoes_ativas(db, sol.id):
        raise ErroNegocio("A solicitação já tem corte registrado. Use o estorno do corte.")
    era = sol.situacao
    sol.situacao, sol.motivo = "CANCELADA", (motivo or "").strip() or None
    if era != "RASCUNHO":
        notificar(db, perfis=("OPERACAO_RJ",), tipo="SOLICITACAO_CANCELADA",
                  texto=f"Solicitação da OP {sol.op} cancelada ({material_texto(sol)}).",
                  link=f"/solicitacoes/{sol.id}")
    auditoria.registrar(db, "SOLICITACAO_CANCELADA", usuario_id=usuario.id, entidade="solicitacao",
                        entidade_id=sol.id, antes={"situacao": era}, depois={"motivo": sol.motivo}, ip=ip)
    db.commit()
    return sol


def material_insuficiente(db: Session, sol_id: int, observacao: str, *, usuario: Usuario,
                          ip: str | None) -> SolicitacaoCorte:
    sol = obter(db, sol_id, travar=True)
    if sol.situacao not in ATIVAS_RJ:
        raise ErroNegocio("Só uma solicitação enviada ou parcial pode ser marcada como material insuficiente.")
    obs = _justificativa(observacao, "observação")
    era = sol.situacao
    sol.situacao, sol.motivo = "MATERIAL_INSUFICIENTE", obs
    notificar(db, perfis=ESTOQUE_ITU, tipo="MATERIAL_INSUFICIENTE",
              texto=f"Material insuficiente na OP {sol.op} ({material_texto(sol)}): {obs}",
              link=f"/solicitacoes/{sol.id}")
    auditoria.registrar(db, "SOLICITACAO_MATERIAL_INSUFICIENTE", usuario_id=usuario.id, entidade="solicitacao",
                        entidade_id=sol.id, antes={"situacao": era}, depois={"observacao": obs}, ip=ip)
    db.commit()
    return sol


def validar_troca_lote(db: Session, cfg: Config, sol_id: int, lote_id: int) -> Previa:
    sol = obter(db, sol_id)
    e = entrada_de(sol, lote_id=lote_id)
    return validar(db, cfg, e, ignorar_solicitacao=sol.id)[0]


def trocar_lote(db: Session, cfg: Config, sol_id: int, lote_id: int, confirmacoes: dict[str, str], *,
                usuario: Usuario, ip: str | None) -> SolicitacaoCorte:
    """[R003] Material insuficiente → a mesma solicitação volta para Enviada com o novo lote e nova reserva."""
    sol = obter(db, sol_id, travar=True)
    if sol.situacao != "MATERIAL_INSUFICIENTE":
        raise ErroNegocio("\"Trocar lote\" vale para solicitação em Material insuficiente.")
    if movimentos.liberacoes_ativas(db, sol.id):
        raise ErroNegocio("A solicitação já tem corte; crie outra solicitação para o restante.")
    e = entrada_de(sol, lote_id=lote_id)
    e.confirmacoes = confirmacoes
    previa, dados, itens = validar(db, cfg, e, ignorar_solicitacao=sol.id)
    conf = exigir_sem_pendencias(previa, confirmacoes)
    antigo = sol.lote.codigo
    _preencher(sol, e, dados, itens[0])
    sol.confirmacoes = {**(sol.confirmacoes or {}), **conf} or None
    _enviar(db, sol, usuario)            # volta para Enviada com a nova reserva e avisa o RJ
    auditoria.registrar(db, "SOLICITACAO_LOTE_TROCADO", usuario_id=usuario.id, entidade="solicitacao",
                        entidade_id=sol.id, antes={"lote": antigo}, depois={"lote": itens[0].lote.codigo,
                                                                            "confirmacoes": conf}, ip=ip)
    db.commit()
    return sol


def encerrar_saldo_pendente(db: Session, sol_id: int, justificativa: str, *, usuario: Usuario,
                            ip: str | None) -> SolicitacaoCorte:
    """[R004] Parcial: libera a reserva do restante; o que foi cortado segue para COP."""
    sol = obter(db, sol_id, travar=True)
    if sol.situacao != "CORTADA_PARCIAL":
        raise ErroNegocio("\"Encerrar com saldo pendente\" vale só para solicitação parcial.")
    j = _justificativa(justificativa)
    sol.encerrada_saldo_pendente, sol.motivo = True, j
    recalcular_solicitacao(db, sol)
    auditoria.registrar(db, "SOLICITACAO_ENCERRADA_PENDENTE", usuario_id=usuario.id, entidade="solicitacao",
                        entidade_id=sol.id, depois={"justificativa": j, "pecas_cortadas":
                                                    movimentos.pecas_cortadas(sol)}, ip=ip)
    db.commit()
    return sol


def trocar_op(db: Session, sol_id: int, nova_op: int, justificativa: str, *, usuario: Usuario,
              ip: str | None) -> tuple[SolicitacaoCorte, list[str]]:
    """[R007] Troca OP, item e cliente da solicitação e das linhas de SA ainda não confirmadas."""
    sol = obter(db, sol_id, travar=True)
    if sol.situacao in ("RASCUNHO", "CANCELADA"):
        raise ErroNegocio("Num rascunho, basta editar a OP.")
    j = _justificativa(justificativa)
    dados = ops.consultar(db, nova_op)
    r = _validar_op(db, dados, ignorar_solicitacao=sol.id)
    if r.erros:
        raise ErroNegocio(r.erros[0].mensagem)
    avisos = []
    antes = {"op": sol.op, "item_codigo": sol.item_codigo, "cliente": sol.cliente}
    sol.op, sol.item_codigo, sol.item_descricao = nova_op, dados.item_codigo, dados.item_descricao
    sol.cliente, sol.pedido, sol.op_confirmada_mega = dados.cliente, dados.pedido, dados.confirmada_mega
    sas = db.scalars(select(CadastroSa).where(CadastroSa.solicitacao_id == sol.id)).all()
    for sa in sas:
        if sa.situacao == "CONFIRMADO":
            avisos.append(f"O SA {sa.sa_codigo} já foi confirmado no Mega: ajuste o SA no Mega.")
        sa.op, sa.item_codigo, sa.item_descricao, sa.cliente = nova_op, dados.item_codigo, dados.item_descricao, \
            dados.cliente
        sa.pedido = dados.pedido or sa.pedido
        if sa.exportado_renato_em:
            sa.alterado_apos_exportar = True
    auditoria.registrar(db, "SOLICITACAO_OP_TROCADA", usuario_id=usuario.id, entidade="solicitacao",
                        entidade_id=sol.id, antes=antes, depois={"op": nova_op, "justificativa": j, "avisos": avisos},
                        ip=ip)
    db.commit()
    return sol, avisos


def duplicar(db: Session, sol_id: int, *, usuario: Usuario, ip: str | None) -> SolicitacaoCorte:
    """Cria um rascunho parecido (útil para OPs do mesmo item). A OP é revalidada ao enviar."""
    base = obter(db, sol_id)
    nova = SolicitacaoCorte(situacao="RASCUNHO", criado_por_id=usuario.id)
    for c in ("op", "item_codigo", "item_descricao", "cliente", "pedido", "op_confirmada_mega", "lote_id", "modo",
              "quantidade", "formato", "acabada_espessura", "acabada_largura", "acabada_diametro",
              "acabada_comprimento", "sobremetal_comprimento_mm", "sobremetal_largura_mm", "bruto_espessura",
              "bruto_largura", "bruto_diametro", "bruto_comprimento", "peso_peca_kg", "peso_previsto_kg",
              "sobremetal_pct", "comprimento_barra_mm", "instrucao", "instrucao_processo", "observacao", "prazo"):
        setattr(nova, c, getattr(base, c))
    db.add(nova)
    db.flush()
    auditoria.registrar(db, "SOLICITACAO_DUPLICADA", usuario_id=usuario.id, entidade="solicitacao",
                        entidade_id=nova.id, depois={"de": base.id}, ip=ip)
    db.commit()
    return nova


# ---------------- T10 Registrar corte (RJ) ----------------

@dataclass
class LinhaCorte:
    lote_id: int
    pecas: int
    peso_real_kg: float
    comprimento_barra_mm: float | None = None


@dataclass
class CorteEntrada:
    linhas: list[LinhaCorte]
    data_corte: date | None = None
    observacao: str | None = None
    confirmacoes: dict[str, str] = field(default_factory=dict)


def validar_corte(db: Session, cfg: Config, sol: SolicitacaoCorte, e: CorteEntrada) -> Previa:
    previa = Previa()
    r = previa.resultado
    if sol.situacao not in ATIVAS_RJ:
        r.adicionar("SITUACAO_INVALIDA", Nivel.ERRO, "Só uma solicitação enviada ou parcial pode receber corte.")
    if not e.linhas:
        r.adicionar("SEM_LINHAS", Nivel.ERRO, "Informe pelo menos um lote com peças e peso.")
        return previa
    d = e.data_corte or hoje()
    dias = int(parametro(db, "CORTE_DIAS_RETROATIVOS"))
    if d > hoje() or d < hoje() - timedelta(days=dias):
        r.adicionar("DATA_CORTE_INVALIDA", Nivel.ERRO, f"A data do corte deve ser de hoje até {dias} dias atrás.")
    ja = movimentos.pecas_cortadas(sol)
    falta = max(sol.quantidade - ja, 0)
    pecas = sum(l.pecas for l in e.linhas)
    peso = round(sum(l.peso_real_kg for l in e.linhas), 3)
    if any(l.pecas < 0 or l.peso_real_kg <= 0 for l in e.linhas):
        r.adicionar("PESO_INVALIDO", Nivel.ERRO, "Peças e peso real precisam ser maiores que zero.")
    if pecas > falta:
        r.adicionar("PECAS_ACIMA_SOLICITADO", Nivel.ALERTA,
                    f"Peças cortadas ({pecas}) acima do que falta ({falta}).", pecas=pecas, falta=falta)
    original = sol.lote
    acabada = (sol.acabada_espessura, sol.acabada_largura, sol.acabada_diametro)
    for i, l in enumerate(e.linhas):
        lote = movimentos.lote_ou_404(db, l.lote_id)
        ri = Resultado()
        if (lote.planta_fiscal, lote.local_fisico) != ("RJ", "RJ"):
            ri.adicionar("LOTE_FORA_DO_RJ", Nivel.ERRO, f"O lote {lote.codigo} não está no RJ.")
        if l.peso_real_kg > float(lote.saldo_kg) + 1e-6:
            ri.adicionar("SALDO_INSUFICIENTE", Nivel.ERRO,
                         f"O peso ({kg_br(l.peso_real_kg)}) é maior que o saldo do lote {lote.codigo} "
                         f"({kg_br(float(lote.saldo_kg))}).")
        if lote.id != original.id:
            b = _bitola_lote(lote)
            if b is not None:
                ri.juntar(regras.validar_bitola(b.espessura, b.largura, b.diametro, *acabada))
            if lote.item.liga_id != original.item.liga_id and \
                    lote.item.liga_id not in ligas_equivalentes(db, original.item.liga_id):
                ri.adicionar("LIGA_DIFERENTE", Nivel.ERRO,
                             f"O lote {lote.codigo} é de outra liga ({lote.item.liga.codigo}).")
            ri.adicionar("LOTE_TROCADO", Nivel.CIENCIA,
                         f"Corte no lote {lote.codigo} ({material_texto_lote(lote)}), diferente do pedido "
                         f"({original.codigo}). Justifique; o Fabiano será avisado.", lote=lote.codigo)
            ri.juntar(regras.validar_destinacoes([regras.Destinacao(x.tipo, x.descricao, x.validade)
                                                  for x in movimentos.destinacoes_vigentes(db, lote.id)]))
        r.juntar(_sufixo(ri, i))
        previa.efeitos.append({"lote": lote.codigo, "lote_id": lote.id, "antes_kg": round(float(lote.saldo_kg), 3),
                               "depois_kg": round(float(lote.saldo_kg) - l.peso_real_kg, 3),
                               "pecas": l.pecas, "peso_real_kg": l.peso_real_kg})
    if sol.modo == "CORTAR_RJ" and pecas > 0:
        previsto = round(float(sol.peso_previsto_kg) * pecas / sol.quantidade, 3)
        r.juntar(regras.validar_peso_real(previsto, peso, parametro(db, "TOLERANCIA_EXCESSO_PCT", cfg),
                                          parametro(db, "TOLERANCIA_FALTA_PCT", cfg)))
        previa.extra["previsto_kg"] = previsto
    restante = falta - pecas
    previa.frase = (f"Corte de {pecas} peça(s), {kg_br(peso)} baixados de "
                    + ", ".join(x["lote"] for x in previa.efeitos)
                    + (f". Faltam {restante} peça(s): a solicitação fica parcial." if restante > 0
                       else ". A solicitação fica Cortada e entra em \"Adicionar cortes prontos\" no COP."))
    return previa


def registrar_corte(db: Session, cfg: Config, sol_id: int, e: CorteEntrada, *, usuario: Usuario,
                    ip: str | None) -> SolicitacaoCorte:
    sol = obter(db, sol_id, travar=True)
    previa = validar_corte(db, cfg, sol, e)
    conf = exigir_sem_pendencias(previa, e.confirmacoes)
    d = e.data_corte or hoje()
    trocados = []
    for l in e.linhas:
        lote = movimentos.lote_ou_404(db, l.lote_id, travar=True)
        lib = LiberacaoCorte(solicitacao_id=sol.id, lote_id=lote.id, pecas=l.pecas,
                             peso_real_kg=round(l.peso_real_kg, 3),
                             comprimento_barra_mm=l.comprimento_barra_mm, data_corte=d, observacao=e.observacao,
                             confirmacoes=conf or None, usuario_id=usuario.id)
        db.add(lib)
        db.flush()
        movimentos.lancar(db, lote, "SAIDA_CORTE_RJ", -l.peso_real_kg, usuario_id=usuario.id, pecas=l.pecas,
                          op=sol.op, solicitacao_id=sol.id, liberacao_id=lib.id, data_referencia=d,
                          justificativa="; ".join(conf.values()) or None, confirmacoes=conf or None)
        if lote.id != sol.lote_id:
            trocados.append(lote.codigo)
    recalcular_solicitacao(db, sol)
    notificar(db, perfis=ESTOQUE_ITU, tipo="CORTE_REGISTRADO",
              texto=f"Corte registrado no RJ: OP {sol.op}, {sum(x.pecas for x in e.linhas)} peça(s), "
                    f"{kg_br(sum(x.peso_real_kg for x in e.linhas))}.", link=f"/solicitacoes/{sol.id}")
    if trocados:
        notificar(db, perfis=ESTOQUE_ITU, tipo="LOTE_TROCADO_RJ",
                  texto=f"O RJ usou outro lote na OP {sol.op}: {', '.join(trocados)} (pedido: {sol.lote.codigo}).",
                  link=f"/solicitacoes/{sol.id}")
    auditoria.registrar(db, "CORTE_RJ_REGISTRADO", usuario_id=usuario.id, entidade="solicitacao", entidade_id=sol.id,
                        depois={"linhas": [x.__dict__ for x in e.linhas], "data": d.isoformat(), "confirmacoes": conf,
                                "situacao": sol.situacao}, ip=ip)
    db.commit()
    return sol


# ---------------- leitura (T08, T09) ----------------

def faixa_atraso(db: Session, sol: SolicitacaoCorte) -> tuple[int | None, str | None]:
    if sol.situacao not in ("ENVIADA", "CORTADA_PARCIAL", "MATERIAL_INSUFICIENTE") or sol.enviada_em is None:
        return None, None
    dias = (hoje() - sol.enviada_em.date()).days
    if dias <= parametro(db, "ATRASO_ATENCAO_DIAS"):
        return dias, "NORMAL"
    if dias <= parametro(db, "ATRASO_ATRASADO_DIAS"):
        return dias, "ATENCAO"
    return dias, "ATRASADO"


def resumo(db: Session, sol: SolicitacaoCorte) -> dict[str, Any]:
    libs = [l for l in sol.liberacoes if not l.estornada]
    dias, faixa = faixa_atraso(db, sol)
    cops = sorted({l.cop_item.cop.numero for l in libs if l.cop_item is not None})
    lote = sol.lote
    return {
        "id": sol.id, "numero": f"S-{sol.id:06d}", "data": sol.criado_em.date().isoformat(), "op": sol.op,
        "item_codigo": sol.item_codigo, "item_descricao": sol.item_descricao, "cliente": sol.cliente,
        "pedido": sol.pedido, "op_confirmada_mega": sol.op_confirmada_mega,
        "lote": {"id": lote.id, "codigo": lote.codigo, "liga": lote.item.liga.codigo, "bitola": bitola(lote.item),
                 "conteiner": lote.conteiner.codigo if lote.conteiner else None,
                 "estoque": BALDE.get((lote.planta_fiscal, lote.local_fisico))},
        "modo": sol.modo, "quantidade": sol.quantidade, "pecas_cortadas": sum(l.pecas for l in libs),
        "peso_previsto_kg": sol.peso_previsto_kg, "peso_real_kg": round(sum(l.peso_real_kg for l in libs), 3) or None,
        "reserva_kg": movimentos.reserva_da_solicitacao(sol), "prazo": sol.prazo.isoformat() if sol.prazo else None,
        "instrucao": sol.instrucao, "instrucao_processo": sol.instrucao_processo, "situacao": sol.situacao,
        "encerrada_saldo_pendente": sol.encerrada_saldo_pendente, "motivo": sol.motivo, "dias_em_aberto": dias,
        "atraso": faixa, "cops": cops,
        "enviada_em": sol.enviada_em.isoformat() if sol.enviada_em else None,
    }


def detalhe(db: Session, sol: SolicitacaoCorte) -> dict[str, Any]:
    d = resumo(db, sol)
    d.update({
        "medida_acabada": {"formato": sol.formato, "espessura": sol.acabada_espessura, "largura": sol.acabada_largura,
                           "diametro": sol.acabada_diametro, "comprimento": sol.acabada_comprimento},
        "sobremetal_comprimento_mm": sol.sobremetal_comprimento_mm, "sobremetal_largura_mm": sol.sobremetal_largura_mm,
        "bruto": {"espessura": sol.bruto_espessura, "largura": sol.bruto_largura, "diametro": sol.bruto_diametro,
                  "comprimento": sol.bruto_comprimento},
        "peso_peca_kg": sol.peso_peca_kg, "sobremetal_pct": sol.sobremetal_pct,
        "comprimento_barra_mm": sol.comprimento_barra_mm, "observacao": sol.observacao,
        "confirmacoes": sol.confirmacoes or {},
        "cortes": [{"id": l.id, "lote": l.lote.codigo, "lote_id": l.lote_id, "pecas": l.pecas,
                    "peso_real_kg": l.peso_real_kg, "comprimento_barra_mm": l.comprimento_barra_mm,
                    "data_corte": l.data_corte.isoformat(), "estornado": l.estornada,
                    "cop": l.cop_item.cop.numero if l.cop_item else None,
                    "cop_item_id": l.cop_item.id if l.cop_item else None} for l in sol.liberacoes],
        "sas": [{"id": s.id, "situacao": s.situacao, "sa_codigo": s.sa_codigo, "peso_kg": s.peso_kg}
                for s in db.scalars(select(CadastroSa).where(CadastroSa.solicitacao_id == sol.id))],
    })
    return d


def listar(db: Session, usuario: Usuario, f: dict[str, Any]) -> list[SolicitacaoCorte]:
    q = (select(SolicitacaoCorte).join(Lote, SolicitacaoCorte.lote_id == Lote.id)
         .join(ItemMP, Lote.item_mp_id == ItemMP.id).join(Liga, ItemMP.liga_id == Liga.id)
         .outerjoin(Conteiner, Lote.conteiner_id == Conteiner.id)
         .options(joinedload(SolicitacaoCorte.lote).joinedload(Lote.item).joinedload(ItemMP.liga),
                  joinedload(SolicitacaoCorte.liberacoes)))
    if so_rj_no_rio(usuario):
        q = q.where(SolicitacaoCorte.situacao != "RASCUNHO")
    if f.get("situacao"):
        q = q.where(SolicitacaoCorte.situacao.in_(f["situacao"]))
    if f.get("op"):
        q = q.where(SolicitacaoCorte.op == f["op"])
    if f.get("cliente"):
        q = q.where(SolicitacaoCorte.cliente.ilike(f"%{f['cliente'].strip()}%"))
    if f.get("liga"):
        q = q.where(Liga.codigo == f["liga"].strip().upper())
    if f.get("conteiner"):
        q = q.where(Conteiner.codigo == f["conteiner"].strip().upper())
    if f.get("de"):
        q = q.where(SolicitacaoCorte.criado_em >= f["de"])
    if f.get("ate"):
        q = q.where(SolicitacaoCorte.criado_em < f["ate"] + timedelta(days=1))
    q = q.order_by(SolicitacaoCorte.id.desc())
    sols = list(db.scalars(q).unique())
    if f.get("somente_atrasadas"):
        sols = [s for s in sols if faixa_atraso(db, s)[1] == "ATRASADO"]
    return sols


def fila_rj(db: Session) -> list[SolicitacaoCorte]:
    sols = list(db.scalars(select(SolicitacaoCorte).where(SolicitacaoCorte.situacao.in_(ATIVAS_RJ))
                           .options(joinedload(SolicitacaoCorte.liberacoes))).unique())
    return sorted(sols, key=lambda s: (s.prazo or date.max, s.enviada_em or agora(), s.id))
