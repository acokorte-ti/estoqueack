"""T06 Entrada por NF (RJ), T17 Reservas e restrições, T18 Ajuste de inventário e estorno, T05 Atribuir origem."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain import peso as dpeso
from app.domain.formato import kg_br, pct_br
from app.domain.validacao import Nivel
from app.models import (Conteiner, CopItem, Destinacao, EntradaNf, EntradaNfItem, ItemMP, LiberacaoCorte, Liga, Lote,
                        Movimento, SolicitacaoCorte, Usuario)

from . import auditoria, movimentos
from .base import ErroNegocio, NaoEncontrado, Previa, exigir_sem_pendencias, so_rj_no_rio
from .fluxo import recalcular_solicitacao

# ---------------- T06 ----------------


@dataclass
class ItemNf:
    liga: str
    formato: str
    peso_kg: float
    espessura: float | None = None
    largura: float | None = None
    diametro: float | None = None
    descricao_nf: str | None = None
    pecas: int | None = None
    comprimento: str | None = None
    custo_kg: float | None = None


@dataclass
class EntradaNfDados:
    numero: str
    data: date
    fornecedor: str
    conteiner: str
    itens: list[ItemNf]
    confirmacoes: dict[str, str] = field(default_factory=dict)


def _comprimento_medio(txt: str | None) -> float | None:
    nums = [float(n.replace(",", ".")) for n in re.findall(r"\d+(?:[.,]\d+)?", txt or "")]
    return sum(nums) / len(nums) if nums else None


def _item(db: Session, i: ItemNf, *, criar: bool) -> tuple[ItemMP | None, Liga | None]:
    liga = db.scalar(select(Liga).where(Liga.codigo == i.liga.strip().upper()))
    if liga is None:
        return None, None
    q = select(ItemMP).where(ItemMP.liga_id == liga.id, ItemMP.formato == i.formato, ItemMP.ativo.is_(True))
    q = q.where(ItemMP.diametro == i.diametro) if i.formato == "REDONDO" else q.where(
        ItemMP.espessura == i.espessura, ItemMP.largura == i.largura)
    item = db.scalar(q.order_by(ItemMP.codigo_mega.is_(None), ItemMP.id))
    if item is None and criar:
        med = f"Ø{i.diametro:g}" if i.formato == "REDONDO" else f"{i.espessura:g}X{i.largura:g}"
        item = ItemMP(descricao=f"{liga.codigo} {med}", liga_id=liga.id, formato=i.formato, espessura=i.espessura,
                      largura=i.largura, diametro=i.diametro)
        db.add(item)
        db.flush()
    return item, liga


def validar_entrada(db: Session, e: EntradaNfDados) -> Previa:
    p = Previa()
    r = p.resultado
    if db.scalar(select(EntradaNf.id).where(EntradaNf.numero == e.numero.strip(),
                                            EntradaNf.fornecedor == e.fornecedor.strip())):
        r.adicionar("NF_DUPLICADA", Nivel.ERRO, f"A NF {e.numero} de {e.fornecedor} já foi lançada.")
    if not e.itens:
        r.adicionar("SEM_ITENS", Nivel.ERRO, "Adicione pelo menos um item.")
    total = 0.0
    for n, i in enumerate(e.itens, start=1):
        _, liga = _item(db, i, criar=False)
        if liga is None:
            r.adicionar(f"LIGA_DESCONHECIDA#{n}", Nivel.ERRO, f"Item {n}: liga {i.liga} não está no catálogo.")
            continue
        incompleto = (not i.diametro) if i.formato == "REDONDO" else not (i.espessura and i.largura)
        if incompleto:
            r.adicionar(f"BITOLA_INCOMPLETA#{n}", Nivel.ERRO, f"Item {n}: informe a bitola completa.")
            continue
        comp = _comprimento_medio(i.comprimento)
        if comp and i.pecas:
            teo = (dpeso.peso_redondo(i.diametro, comp, float(liga.densidade), i.pecas) if i.formato == "REDONDO"
                   else dpeso.peso_reto(i.espessura, i.largura, comp, float(liga.densidade), i.pecas))
            if teo and abs(i.peso_kg - teo) / teo * 100 > 20:
                r.adicionar(f"PESO_TEORICO_DIFERENTE#{n}", Nivel.ALERTA,
                            f"Item {n}: peso informado {kg_br(i.peso_kg)} difere do teórico {kg_br(teo)} "
                            f"({pct_br((i.peso_kg - teo) / teo * 100, 1)}). Confira a digitação.")
        total += i.peso_kg
    p.frase = f"{len(e.itens)} lote(s) RJ no Rio no contêiner {e.conteiner.strip().upper()}, total {kg_br(total)}."
    return p


def registrar_entrada(db: Session, e: EntradaNfDados, *, usuario: Usuario, ip: str | None) -> EntradaNf:
    exigir_sem_pendencias(validar_entrada(db, e), e.confirmacoes)
    cod = e.conteiner.strip().upper()
    ct = db.scalar(select(Conteiner).where(Conteiner.codigo == cod))
    if ct is None:
        ct = Conteiner(codigo=cod, data_entrada=e.data)
        db.add(ct)
        db.flush()
    nf = EntradaNf(numero=e.numero.strip(), fornecedor=e.fornecedor.strip(), data=e.data, conteiner_id=ct.id,
                   usuario_id=usuario.id)
    db.add(nf)
    db.flush()
    for i in e.itens:
        item, _ = _item(db, i, criar=True)
        lote = movimentos.criar_lote(db, item=item, planta_fiscal="RJ", local_fisico="RJ", conteiner_id=ct.id,
                                     peso_inicial_kg=i.peso_kg, pecas=i.pecas, documento=f"NF {nf.numero}",
                                     custo_kg=i.custo_kg, usuario_id=usuario.id)
        movimentos.lancar(db, lote, "ENTRADA", i.peso_kg, usuario_id=usuario.id, pecas=i.pecas,
                          documento=f"NF {nf.numero} {nf.fornecedor}", data_referencia=e.data)
        db.add(EntradaNfItem(entrada_id=nf.id, lote_id=lote.id, descricao_nf=i.descricao_nf, pecas=i.pecas,
                             peso_kg=i.peso_kg, comprimento=i.comprimento, custo_kg=i.custo_kg))
    db.flush()
    auditoria.registrar(db, "ENTRADA_NF", usuario_id=usuario.id, entidade="entrada_nf", entidade_id=nf.id,
                        depois={"nf": nf.numero, "fornecedor": nf.fornecedor, "conteiner": cod,
                                "itens": len(e.itens)}, ip=ip)
    db.commit()
    return nf


def entrada_dict(db: Session, nf: EntradaNf) -> dict:
    ct = db.get(Conteiner, nf.conteiner_id)
    return {"id": nf.id, "numero": nf.numero, "fornecedor": nf.fornecedor, "data": nf.data.isoformat(),
            "conteiner": ct.codigo if ct else None,
            "itens": [{"lote_id": i.lote_id, "descricao_nf": i.descricao_nf, "pecas": i.pecas, "peso_kg": i.peso_kg,
                       "comprimento": i.comprimento} for i in nf.itens]}


# ---------------- T17 ----------------

def criar_destinacao(db: Session, lote_id: int, tipo: str, descricao: str, kg: float | None, validade: date | None,
                     *, usuario: Usuario, ip: str | None) -> Destinacao:
    lote = movimentos.lote_ou_404(db, lote_id)
    if tipo == "RESERVA" and kg is not None and kg > float(lote.saldo_kg) + 1e-6:
        raise ErroNegocio(f"A reserva ({kg_br(kg)}) é maior que o saldo do lote ({kg_br(float(lote.saldo_kg))}).")
    d = Destinacao(lote_id=lote.id, tipo=tipo, descricao=descricao.strip(), kg=kg if tipo == "RESERVA" else None,
                   validade=validade, criado_por_id=usuario.id)
    db.add(d)
    db.flush()
    auditoria.registrar(db, "DESTINACAO_CRIADA", usuario_id=usuario.id, entidade="lote", entidade_id=lote.id,
                        depois={"id": d.id, "tipo": tipo, "descricao": d.descricao, "kg": d.kg}, ip=ip)
    db.commit()
    return d


def encerrar_destinacao(db: Session, dest_id: int, *, usuario: Usuario, ip: str | None) -> Destinacao:
    d = db.get(Destinacao, dest_id)
    if d is None:
        raise NaoEncontrado("Reserva ou restrição não encontrada.")
    d.ativa = False
    auditoria.registrar(db, "DESTINACAO_ENCERRADA", usuario_id=usuario.id, entidade="lote", entidade_id=d.lote_id,
                        depois={"id": d.id}, ip=ip)
    db.commit()
    return d


# ---------------- T18 ----------------

def validar_ajuste(db: Session, lote_id: int, saldo_contado: float) -> Previa:
    lote = movimentos.lote_ou_404(db, lote_id)
    p = Previa()
    dif = round(saldo_contado - float(lote.saldo_kg), 3)
    if saldo_contado < 0:
        p.resultado.adicionar("PESO_INVALIDO", Nivel.ERRO, "O saldo contado não pode ser negativo.")
    if abs(dif) < 1e-6:
        p.resultado.adicionar("SEM_DIFERENCA", Nivel.ERRO, "O saldo contado é igual ao saldo do sistema.")
    p.frase = f"Lote {lote.codigo} passa de {kg_br(float(lote.saldo_kg))} para {kg_br(saldo_contado)} " \
              f"(diferença {'+' if dif > 0 else ''}{kg_br(dif)})."
    p.efeitos = [{"lote": lote.codigo, "antes_kg": round(float(lote.saldo_kg), 3), "depois_kg": saldo_contado}]
    p.extra["diferenca_kg"] = dif
    return p


def ajustar(db: Session, lote_id: int, saldo_contado: float, justificativa: str, *, usuario: Usuario,
            ip: str | None) -> Movimento:
    if len((justificativa or "").strip()) < 10:
        raise ErroNegocio("A justificativa precisa ter pelo menos 10 caracteres.")
    previa = validar_ajuste(db, lote_id, saldo_contado)
    exigir_sem_pendencias(previa, {})
    lote = movimentos.lote_ou_404(db, lote_id, travar=True)
    m = movimentos.lancar(db, lote, "AJUSTE_INVENTARIO", previa.extra["diferenca_kg"], usuario_id=usuario.id,
                          justificativa=justificativa.strip())
    auditoria.registrar(db, "AJUSTE_INVENTARIO", usuario_id=usuario.id, entidade="lote", entidade_id=lote.id,
                        depois={"diferenca_kg": m.kg, "justificativa": m.justificativa}, ip=ip)
    db.commit()
    return m


def estornar(db: Session, mov_id: int, justificativa: str, *, usuario: Usuario, ip: str | None) -> Movimento:
    """Cria o movimento inverso ligado ao original. Corte RJ só antes do COP fechado (§8, T18)."""
    if len((justificativa or "").strip()) < 10:
        raise ErroNegocio("A justificativa precisa ter pelo menos 10 caracteres.")
    m = db.get(Movimento, mov_id)
    if m is None:
        raise NaoEncontrado("Movimento não encontrado.")
    if m.tipo == "ESTORNO" or m.estorno_de_id:
        raise ErroNegocio("Um estorno não pode ser estornado.")
    if db.scalar(select(Movimento.id).where(Movimento.estorno_de_id == m.id)):
        raise ErroNegocio("Este movimento já foi estornado.")
    if so_rj_no_rio(usuario) and m.usuario_id != usuario.id:
        raise ErroNegocio("O RJ só pode estornar os próprios lançamentos.")
    lib = db.get(LiberacaoCorte, m.liberacao_id) if m.liberacao_id and m.tipo == "SAIDA_CORTE_RJ" else None
    if lib is not None:
        item = db.scalar(select(CopItem).where(CopItem.liberacao_id == lib.id))
        if item is not None:
            raise ErroNegocio("O corte já está num COP. Remova do COP aberto antes de estornar; com o COP fechado, "
                              "use \"Reabrir COP\".")
    elif so_rj_no_rio(usuario):
        raise ErroNegocio("O RJ só pode estornar o próprio corte, antes do COP fechado.")
    lote = movimentos.lote_ou_404(db, m.lote_id, travar=True)
    inv = movimentos.lancar(db, lote, "ESTORNO", -float(m.kg), usuario_id=usuario.id, estorno_de_id=m.id, op=m.op,
                            cop_numero=m.cop_numero, solicitacao_id=m.solicitacao_id, liberacao_id=m.liberacao_id,
                            corte_itu_id=m.corte_itu_id, justificativa=justificativa.strip())
    if lib is not None:
        lib.estornada = True
        db.flush()
        recalcular_solicitacao(db, db.get(SolicitacaoCorte, lib.solicitacao_id))
    auditoria.registrar(db, "ESTORNO", usuario_id=usuario.id, entidade="movimento", entidade_id=m.id,
                        depois={"estorno_id": inv.id, "kg": inv.kg, "justificativa": inv.justificativa}, ip=ip)
    db.commit()
    return inv


# ---------------- T05 Atribuir origem [P07] ----------------

def atribuir_origem(db: Session, lote_id: int, conteiner: str, lote_pai_id: int | None, justificativa: str, *,
                    usuario: Usuario, ip: str | None) -> Lote:
    if len((justificativa or "").strip()) < 10:
        raise ErroNegocio("A justificativa precisa ter pelo menos 10 caracteres.")
    lote = movimentos.lote_ou_404(db, lote_id, travar=True)
    if lote.origem_identificada:
        raise ErroNegocio("O lote já tem origem identificada.")
    ct = db.scalar(select(Conteiner).where(Conteiner.codigo == conteiner.strip().upper()))
    if ct is None:
        raise ErroNegocio("Contêiner não encontrado.")
    antes = {"conteiner_id": lote.conteiner_id, "lote_pai_id": lote.lote_pai_id}
    if lote_pai_id is not None:
        pai = movimentos.lote_ou_404(db, lote_pai_id)
        if pai.id == lote.id:
            raise ErroNegocio("O lote não pode ser pai dele mesmo.")
        lote.lote_pai_id = pai.id
    lote.conteiner_id, lote.origem_identificada = ct.id, True
    auditoria.registrar(db, "ORIGEM_ATRIBUIDA", usuario_id=usuario.id, entidade="lote", entidade_id=lote.id,
                        antes=antes, depois={"conteiner": ct.codigo, "lote_pai_id": lote_pai_id,
                                             "justificativa": justificativa.strip()}, ip=ip)
    db.commit()
    return lote
