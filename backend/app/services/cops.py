"""T11 COP (montar, fechar → gera SAs, NF, enviar, reabrir) e T12 Receber COP (conferência, divergência,
lote RJ em Itu da peça inteira). Especificação v3 §3.2 e [P13]: corte → COP fechado → SA → NF → envio."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.formato import kg_br, pct_br
from app.domain.validacao import Nivel
from app.models import CadastroSa, Cop, CopItem, DivergenciaRecebimento, LiberacaoCorte, SolicitacaoCorte, Usuario

from . import auditoria, movimentos, sas
from .base import ErroNegocio, NaoEncontrado, Previa, agora, exigir_sem_pendencias, notificar, parametro
from .estoque import bitola
from .fluxo import material_texto, recalcular_solicitacao

ESTOQUE_ITU = ("ESTOQUE",)


def obter(db: Session, cop_id: int, *, travar: bool = False) -> Cop:
    q = select(Cop).where(Cop.id == cop_id)
    if travar:
        q = q.with_for_update()
    cop = db.scalar(q)
    if cop is None:
        raise NaoEncontrado("COP não encontrado.")
    return cop


def proximo_numero(db: Session) -> int:
    return int(db.scalar(select(func.max(Cop.numero))) or 0) + 1


def _sa_do_item(db: Session, item: CopItem) -> CadastroSa | None:
    return db.scalar(select(CadastroSa).where(CadastroSa.cop_item_id == item.id))


def situacao_exibida(db: Session, cop: Cop) -> str:
    """'AGUARDANDO_NF' é derivada: COP fechado com todos os SAs confirmados (§3.2)."""
    if cop.situacao == "FECHADO" and cop.itens and all(
            (s := _sa_do_item(db, i)) is not None and s.situacao == "CONFIRMADO" for i in cop.itens):
        return "AGUARDANDO_NF"
    return cop.situacao


def _recalcular(db: Session, cop: Cop) -> None:
    for sol_id in {i.liberacao.solicitacao_id for i in cop.itens}:
        recalcular_solicitacao(db, db.get(SolicitacaoCorte, sol_id))


def criar(db: Session, numero: int | None, observacao: str | None, *, usuario: Usuario, ip: str | None) -> Cop:
    numero = numero or proximo_numero(db)
    if db.scalar(select(Cop.id).where(Cop.numero == numero)):
        raise ErroNegocio(f"Já existe o COP {numero}.")
    cop = Cop(numero=numero, observacao=observacao, criado_por_id=usuario.id)
    db.add(cop)
    db.flush()
    auditoria.registrar(db, "COP_CRIADO", usuario_id=usuario.id, entidade="cop", entidade_id=cop.id,
                        depois={"numero": numero}, ip=ip)
    db.commit()
    return cop


def cortes_prontos(db: Session) -> list[LiberacaoCorte]:
    """Cortes (e peças inteiras separadas) ainda fora de COP."""
    q = (select(LiberacaoCorte).outerjoin(CopItem, CopItem.liberacao_id == LiberacaoCorte.id)
         .join(SolicitacaoCorte, LiberacaoCorte.solicitacao_id == SolicitacaoCorte.id)
         .where(CopItem.id.is_(None), LiberacaoCorte.estornada.is_(False), SolicitacaoCorte.situacao != "CANCELADA")
         .order_by(LiberacaoCorte.data_corte, LiberacaoCorte.id))
    return list(db.scalars(q))


def adicionar_itens(db: Session, cop_id: int, liberacao_ids: list[int], *, usuario: Usuario, ip: str | None) -> Cop:
    cop = obter(db, cop_id, travar=True)
    if cop.situacao != "ABERTO":
        raise ErroNegocio("COP fechado não aceita mais itens. Use \"Reabrir COP\".")
    prontos = {l.id for l in cortes_prontos(db)}
    for lid in liberacao_ids:
        if lid not in prontos:
            raise ErroNegocio("Corte já está em outro COP, foi estornado ou não existe.")
        db.add(CopItem(cop_id=cop.id, liberacao_id=lid))
    db.flush()
    db.refresh(cop, ["itens"])
    auditoria.registrar(db, "COP_ITENS_ADICIONADOS", usuario_id=usuario.id, entidade="cop", entidade_id=cop.id,
                        depois={"liberacoes": liberacao_ids}, ip=ip)
    db.commit()
    return cop


def remover_item(db: Session, cop_id: int, item_id: int, *, usuario: Usuario, ip: str | None) -> Cop:
    cop = obter(db, cop_id, travar=True)
    if cop.situacao != "ABERTO":
        raise ErroNegocio("Só é possível remover itens de COP aberto.")
    item = db.get(CopItem, item_id)
    if item is None or item.cop_id != cop.id:
        raise NaoEncontrado("Item não encontrado neste COP.")
    db.delete(item)
    db.flush()
    db.refresh(cop, ["itens"])
    auditoria.registrar(db, "COP_ITEM_REMOVIDO", usuario_id=usuario.id, entidade="cop", entidade_id=cop.id,
                        depois={"item": item_id}, ip=ip)
    db.commit()
    return cop


def fechar(db: Session, cop_id: int, *, usuario: Usuario, ip: str | None) -> Cop:
    """Fecha a lista e cria uma linha de SA por item (peso real no corte; peso previsto na peça inteira [P03])."""
    cop = obter(db, cop_id, travar=True)
    if cop.situacao != "ABERTO":
        raise ErroNegocio("O COP já está fechado.")
    if not cop.itens:
        raise ErroNegocio("Inclua pelo menos um corte pronto antes de fechar.")
    for item in cop.itens:
        lib, sol = item.liberacao, item.liberacao.solicitacao
        if sol.modo == "TRAZER_INTEIRA":
            peso = float(sol.peso_previsto_kg) * lib.pecas / sol.quantidade if sol.quantidade else lib.peso_real_kg
        else:
            peso = float(lib.peso_real_kg)
        sas.criar_linha(db, origem="COP", lote=lib.lote, op=sol.op, item_codigo=sol.item_codigo,
                        item_descricao=sol.item_descricao, cliente=sol.cliente, pedido=sol.pedido,
                        quantidade=lib.pecas, peso_kg=peso, solicitacao_id=sol.id, cop_item_id=item.id)
    cop.situacao, cop.fechado_em = "FECHADO", agora()
    db.flush()
    _recalcular(db, cop)
    notificar(db, perfis=ESTOQUE_ITU, tipo="COP_FECHADO",
              texto=f"COP {cop.numero} fechado pelo RJ com {len(cop.itens)} item(ns): SA a fazer.",
              link=f"/sa?cop={cop.numero}")
    auditoria.registrar(db, "COP_FECHADO", usuario_id=usuario.id, entidade="cop", entidade_id=cop.id,
                        depois={"itens": len(cop.itens)}, ip=ip)
    db.commit()
    return cop


def reabrir(db: Session, cop_id: int, justificativa: str, *, usuario: Usuario, ip: str | None) -> Cop:
    cop = obter(db, cop_id, travar=True)
    if cop.situacao != "FECHADO":
        raise ErroNegocio("Só um COP fechado (ainda não enviado) pode ser reaberto.")
    if len((justificativa or "").strip()) < 10:
        raise ErroNegocio("A justificativa precisa ter pelo menos 10 caracteres.")
    linhas = [s for i in cop.itens if (s := _sa_do_item(db, i)) is not None]
    if any(s.situacao == "CONFIRMADO" for s in linhas):
        raise ErroNegocio("Há SA confirmado neste COP: não é possível reabrir.")
    for s in linhas:
        db.delete(s)
    cop.situacao, cop.fechado_em = "ABERTO", None
    db.flush()
    _recalcular(db, cop)
    notificar(db, perfis=ESTOQUE_ITU, tipo="COP_REABERTO", texto=f"COP {cop.numero} reaberto pelo RJ: {justificativa}",
              link=f"/cops/{cop.id}")
    auditoria.registrar(db, "COP_REABERTO", usuario_id=usuario.id, entidade="cop", entidade_id=cop.id,
                        depois={"justificativa": justificativa.strip(), "sas_removidos": len(linhas)}, ip=ip)
    db.commit()
    return cop


def informar_nf(db: Session, cop_id: int, numero: str, emitente: str, data, item_ids: list[int] | None, *,
                usuario: Usuario, ip: str | None) -> Cop:
    """NF digitada uma vez no COP e copiada para os itens (ou só para os selecionados) e suas linhas de SA."""
    cop = obter(db, cop_id, travar=True)
    if cop.situacao != "FECHADO":
        raise ErroNegocio("A NF é informada com o COP fechado, antes do envio.")
    nf = sas.obter_nf(db, numero, emitente, data)
    alvo = [i for i in cop.itens if item_ids is None or i.id in item_ids]
    if item_ids is not None and len(alvo) != len(set(item_ids)):
        raise ErroNegocio("Algum item informado não é deste COP.")
    for i in alvo:
        i.nf_id = nf.id
        s = _sa_do_item(db, i)
        if s is not None:
            s.nf_id = nf.id
    auditoria.registrar(db, "COP_NF_INFORMADA", usuario_id=usuario.id, entidade="cop", entidade_id=cop.id,
                        depois={"nf": nf.numero, "emitente": nf.emitente, "itens": [i.id for i in alvo]}, ip=ip)
    db.commit()
    return cop


def validar_envio(db: Session, cop: Cop) -> Previa:
    p = Previa()
    r = p.resultado
    if cop.situacao != "FECHADO":
        r.adicionar("COP_NAO_FECHADO", Nivel.ERRO, "Feche o COP antes de enviar.")
    sem_sa = [i for i in cop.itens if (s := _sa_do_item(db, i)) is None or s.situacao != "CONFIRMADO"]
    if sem_sa:
        r.adicionar("SA_PENDENTE", Nivel.ERRO, f"{len(sem_sa)} item(ns) ainda sem SA confirmado em Itu.",
                    itens=[i.id for i in sem_sa])
    sem_nf = [i for i in cop.itens if i.nf_id is None]
    if sem_nf:
        r.adicionar("NF_PENDENTE", Nivel.ERRO, f"{len(sem_nf)} item(ns) sem NF de transferência.",
                    itens=[i.id for i in sem_nf])
    total = sum(float(i.liberacao.peso_real_kg) for i in cop.itens)
    p.frase = f"COP {cop.numero}: {len(cop.itens)} item(ns), {kg_br(total)}, ficam Em trânsito para Itu."
    return p


def enviar(db: Session, cop_id: int, *, usuario: Usuario, ip: str | None) -> Cop:
    cop = obter(db, cop_id, travar=True)
    exigir_sem_pendencias(validar_envio(db, cop), {})
    for i in cop.itens:
        i.situacao = "EM_TRANSITO"
    cop.situacao, cop.enviado_em = "ENVIADO", agora()
    db.flush()
    _recalcular(db, cop)
    notificar(db, perfis=ESTOQUE_ITU, tipo="COP_ENVIADO", texto=f"COP {cop.numero} enviado: em trânsito para Itu.",
              link=f"/recebimentos/{cop.id}")
    auditoria.registrar(db, "COP_ENVIADO", usuario_id=usuario.id, entidade="cop", entidade_id=cop.id, ip=ip)
    db.commit()
    return cop


# ---------------- T12 ----------------

@dataclass
class ItemRecebido:
    cop_item_id: int
    peso_conferido_kg: float | None = None


@dataclass
class RecebimentoEntrada:
    itens: list[ItemRecebido]
    confirmacoes: dict[str, str] = field(default_factory=dict)


def validar_recebimento(db: Session, cop: Cop, e: RecebimentoEntrada) -> Previa:
    p = Previa()
    r = p.resultado
    if cop.situacao not in ("ENVIADO", "RECEBIDO_PARCIAL"):
        r.adicionar("COP_NAO_ENVIADO", Nivel.ERRO, "Este COP não está em trânsito.")
    limite = parametro(db, "DIVERGENCIA_TRANSPORTE_PCT")
    por_id = {i.id: i for i in cop.itens}
    for x in e.itens:
        item = por_id.get(x.cop_item_id)
        if item is None:
            r.adicionar("ITEM_INVALIDO", Nivel.ERRO, "Item não pertence a este COP.")
            continue
        if item.situacao != "EM_TRANSITO":
            r.adicionar("ITEM_JA_RECEBIDO", Nivel.ERRO,
                        f"O item da OP {item.liberacao.solicitacao.op} já foi recebido.")
            continue
        enviado = float(item.liberacao.peso_real_kg)
        if x.peso_conferido_kg is not None and enviado > 0:
            desvio = (x.peso_conferido_kg - enviado) / enviado * 100
            if abs(desvio) > limite + 1e-9:
                r.adicionar(f"DIVERGENCIA_TRANSPORTE_{item.id}", Nivel.CIENCIA,
                            f"OP {item.liberacao.solicitacao.op}: conferido {kg_br(x.peso_conferido_kg)} × enviado "
                            f"{kg_br(enviado)} ({pct_br(desvio, 1)}). Limite: {pct_br(limite)}. Justifique.",
                            enviado_kg=enviado, conferido_kg=x.peso_conferido_kg, cop_item_id=item.id)
        sol = item.liberacao.solicitacao
        p.efeitos.append({"cop_item_id": item.id, "op": sol.op, "modo": sol.modo,
                          "efeito": "LOTE_RJ_EM_ITU" if sol.modo == "TRAZER_INTEIRA" else "CONCLUIDA",
                          "peso_kg": x.peso_conferido_kg or enviado})
    faltam = len([i for i in cop.itens if i.situacao == "EM_TRANSITO"]) - len(e.itens)
    p.frase = f"{len(e.itens)} item(ns) recebido(s)" + (f"; {faltam} continuam em trânsito (Recebido parcial)."
                                                         if faltam > 0 else "; COP Recebido.")
    return p


def receber(db: Session, cop_id: int, e: RecebimentoEntrada, *, usuario: Usuario, ip: str | None) -> Cop:
    cop = obter(db, cop_id, travar=True)
    conf = exigir_sem_pendencias(validar_recebimento(db, cop, e), e.confirmacoes)
    por_id = {i.id: i for i in cop.itens}
    for x in e.itens:
        item = por_id[x.cop_item_id]
        lib, sol = item.liberacao, item.liberacao.solicitacao
        item.situacao, item.recebido_em, item.recebido_por_id = "RECEBIDO", agora(), usuario.id
        item.peso_conferido_kg = x.peso_conferido_kg
        cc = {k: v for k, v in conf.items() if k == f"DIVERGENCIA_TRANSPORTE_{item.id}"}
        item.confirmacoes = cc or None
        if sol.modo == "TRAZER_INTEIRA":
            origem = lib.lote
            peso = x.peso_conferido_kg or float(lib.peso_real_kg)
            novo = movimentos.criar_lote(db, item=origem.item, planta_fiscal="RJ", local_fisico="ITU", pai=origem,
                                         peso_inicial_kg=peso, pecas=lib.pecas, usuario_id=usuario.id)
            movimentos.lancar(db, novo, "RECEBIMENTO_ITU", peso, usuario_id=usuario.id, op=sol.op, pecas=lib.pecas,
                              cop_numero=cop.numero, solicitacao_id=sol.id, liberacao_id=lib.id,
                              justificativa="; ".join(cc.values()) or None, confirmacoes=cc or None)
            item.lote_itu_id = novo.id
    db.flush()
    pend = [i for i in cop.itens if i.situacao == "EM_TRANSITO"]
    cop.situacao = "RECEBIDO_PARCIAL" if pend else "RECEBIDO"
    if not pend:
        cop.recebido_em = agora()
    _recalcular(db, cop)
    auditoria.registrar(db, "COP_RECEBIDO", usuario_id=usuario.id, entidade="cop", entidade_id=cop.id,
                        depois={"itens": [x.__dict__ for x in e.itens], "confirmacoes": conf,
                                "situacao": cop.situacao}, ip=ip)
    db.commit()
    return cop


def registrar_divergencia(db: Session, cop_id: int, item_id: int, tipo: str, pecas: int | None, kg: float | None,
                          observacao: str, *, usuario: Usuario, ip: str | None) -> DivergenciaRecebimento:
    cop = obter(db, cop_id)
    item = db.get(CopItem, item_id)
    if item is None or item.cop_id != cop.id:
        raise NaoEncontrado("Item não encontrado neste COP.")
    if cop.situacao not in ("ENVIADO", "RECEBIDO_PARCIAL", "RECEBIDO"):
        raise ErroNegocio("Divergência só depois do envio do COP.")
    d = DivergenciaRecebimento(cop_item_id=item.id, tipo=tipo, pecas=pecas, kg=kg, observacao=observacao.strip(),
                               usuario_id=usuario.id)
    db.add(d)
    db.flush()
    notificar(db, perfis=("OPERACAO_RJ", "ADMIN"), tipo="DIVERGENCIA_RECEBIMENTO",
              texto=f"Divergência no COP {cop.numero}, OP {item.liberacao.solicitacao.op}: {tipo.lower()} — "
                    f"{observacao.strip()}", link=f"/cops/{cop.id}", exceto_id=usuario.id)
    auditoria.registrar(db, "DIVERGENCIA_RECEBIMENTO", usuario_id=usuario.id, entidade="cop", entidade_id=cop.id,
                        depois={"item": item.id, "tipo": tipo, "pecas": pecas, "kg": kg}, ip=ip)
    db.commit()
    return d


# ---------------- leitura ----------------

def item_dict(db: Session, i: CopItem) -> dict[str, Any]:
    lib, sol = i.liberacao, i.liberacao.solicitacao
    s = _sa_do_item(db, i)
    return {"id": i.id, "liberacao_id": lib.id, "solicitacao_id": sol.id, "op": sol.op, "item_codigo": sol.item_codigo,
            "cliente": sol.cliente, "material": f"{lib.lote.item.liga.codigo} {bitola(lib.lote.item)}",
            "conteiner": lib.lote.conteiner.codigo if lib.lote.conteiner else None, "lote": lib.lote.codigo,
            "modo": sol.modo, "pecas": lib.pecas, "peso_kg": lib.peso_real_kg, "situacao": i.situacao,
            "sa": {"id": s.id, "situacao": s.situacao, "sa_codigo": s.sa_codigo} if s else None,
            "nf": {"numero": i.nf.numero, "emitente": i.nf.emitente} if i.nf else None,
            "peso_conferido_kg": i.peso_conferido_kg, "lote_itu_id": i.lote_itu_id,
            "divergencias": [{"tipo": d.tipo, "pecas": d.pecas, "kg": d.kg, "observacao": d.observacao}
                             for d in db.scalars(select(DivergenciaRecebimento)
                                                 .where(DivergenciaRecebimento.cop_item_id == i.id))]}


def cop_dict(db: Session, cop: Cop, *, com_itens: bool = True) -> dict[str, Any]:
    nfs = sorted({f"{i.nf.numero} ({i.nf.emitente})" for i in cop.itens if i.nf})
    d = {"id": cop.id, "numero": cop.numero, "situacao": situacao_exibida(db, cop), "data": cop.criado_em.isoformat(),
         "fechado_em": cop.fechado_em.isoformat() if cop.fechado_em else None,
         "enviado_em": cop.enviado_em.isoformat() if cop.enviado_em else None,
         "qtd_itens": len(cop.itens),
         "peso_total_kg": round(sum(float(i.liberacao.peso_real_kg) for i in cop.itens), 3),
         "nfs": nfs, "observacao": cop.observacao}
    if com_itens:
        d["itens"] = [item_dict(db, i) for i in cop.itens]
    return d


def pronto_dict(lib: LiberacaoCorte) -> dict[str, Any]:
    sol = lib.solicitacao
    return {"liberacao_id": lib.id, "solicitacao_id": sol.id, "op": sol.op, "cliente": sol.cliente,
            "material": material_texto(sol), "lote": lib.lote.codigo, "modo": sol.modo, "pecas": lib.pecas,
            "peso_kg": lib.peso_real_kg, "data_corte": lib.data_corte.isoformat()}


def listar(db: Session, situacoes: list[str] | None) -> list[Cop]:
    q = select(Cop)
    if situacoes:
        q = q.where(Cop.situacao.in_(situacoes))
    return list(db.scalars(q.order_by(Cop.numero.desc())))
