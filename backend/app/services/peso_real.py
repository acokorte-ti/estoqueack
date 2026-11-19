"""Pendência "Informar o peso real" da peça inteira do RJ e bloqueio `PESO_REAL_PENDENTE` (spec v3.11 §2.2 passo 7,
T07, §9, T23; R058; contrato §16.2).

A pendência é a solicitação `AGUARDANDO_CORTE_ITU` (peça inteira recebida no COP, T12) que ainda não teve a T13 e
não foi encerrada. Ela conta do recebimento do COP (`cop_item.recebido_em`) [proposta, P33(b)]. Passou de
`PENDENCIA_PESO_REAL_DIAS` (T23, 14) → bloqueia "Enviar ao RJ" para todos, sem liberação do Admin [proposta, P33(a)
e (c)]; antes, só aviso. O SA da peça inteira não é corrigido (fica com o previsto, como a NF).
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.validacao import Nivel, Resultado
from app.models import CopItem, LiberacaoCorte, Lote, SolicitacaoCorte, Usuario

from . import auditoria
from .base import ErroNegocio, NaoEncontrado, agora, hoje, parametro

CODIGO_BLOQUEIO = "PESO_REAL_PENDENTE"
CODIGO_AVISO = "PESO_REAL_AGUARDANDO"


def _bitola(item) -> str:
    if item.formato == "REDONDO" and item.diametro:
        return f"Ø{item.diametro:g}"
    if item.espessura and item.largura:
        return f"{item.espessura:g}X{item.largura:g}"
    return item.formato


def itens(db: Session) -> list[dict[str, Any]]:
    """Pendências abertas, da mais antiga para a mais nova."""
    limite = int(parametro(db, "PENDENCIA_PESO_REAL_DIAS"))
    q = (select(SolicitacaoCorte, CopItem)
         .join(LiberacaoCorte, LiberacaoCorte.solicitacao_id == SolicitacaoCorte.id)
         .join(CopItem, CopItem.liberacao_id == LiberacaoCorte.id)
         .where(SolicitacaoCorte.situacao == "AGUARDANDO_CORTE_ITU",
                SolicitacaoCorte.peso_real_encerrada_em.is_(None), CopItem.recebido_em.is_not(None)))
    por_sol: dict[int, tuple[SolicitacaoCorte, CopItem]] = {}
    for sol, ci in db.execute(q):
        atual = por_sol.get(sol.id)
        if atual is None or ci.recebido_em < atual[1].recebido_em:
            por_sol[sol.id] = (sol, ci)
    out = []
    for sol, ci in por_sol.values():
        rec = ci.recebido_em.date()
        dias = (hoje() - rec).days
        lote = sol.lote
        lote_itu = db.get(Lote, ci.lote_itu_id) if ci.lote_itu_id else None
        out.append({"pendencia_id": sol.id, "solicitacao_id": sol.id, "op": sol.op,
                    "lote_id": ci.lote_itu_id, "lote_itu_id": ci.lote_itu_id,
                    "lote": lote_itu.codigo if lote_itu else None,
                    "material": f"{lote.item.liga.codigo} {_bitola(lote.item)}",
                    "conteiner": lote.conteiner.codigo if lote.conteiner else None,
                    "cop": ci.cop.numero if ci.cop else None, "recebido_em": rec.isoformat(), "dias": dias,
                    "vence_em": (rec + timedelta(days=limite)).isoformat(), "vencida": dias > limite})
    return sorted(out, key=lambda x: (x["recebido_em"], x["solicitacao_id"]))


def link_t13(x: dict[str, Any]) -> str:
    """Link da T13 com a peça sugerida (formato da tela, R060)."""
    return f"/corte-itu?op={x['op']}&lote_id={x['lote_id']}&peso_real=1"


def situacao(db: Session) -> dict[str, Any]:
    limite = int(parametro(db, "PENDENCIA_PESO_REAL_DIAS"))
    xs = itens(db)
    venc = [x for x in xs if x["vencida"]]
    mensagem = aviso = None
    if venc:
        ex = venc[0]
        mensagem = (f"Há {len(venc)} peça(s) inteira(s) do RJ sem peso real há mais de {limite} dias (ex.: OP "
                    f"{ex['op']}, {ex['material']}, recebida em {date.fromisoformat(ex['recebido_em']):%d/%m}). "
                    "Informe o peso real em Registrar corte em Itu para voltar a enviar solicitações.")
    elif xs:
        aviso = (f"{len(xs)} peça(s) inteira(s) do RJ aguardando peso real; a partir de "
                 f"{date.fromisoformat(xs[0]['vence_em']) + timedelta(days=1):%d/%m}, novas solicitações ficam "
                 "bloqueadas.")
    a_partir = (date.fromisoformat(xs[0]["vence_em"]) + timedelta(days=1)).isoformat() if xs else None
    return {"dias_limite": limite, "bloqueado": bool(venc), "quantidade": len(xs), "vencidas": len(venc),
            "bloqueia_a_partir_de": a_partir, "mensagem": mensagem, "aviso": aviso, "itens": xs}


def validar_envio(db: Session, enviar: bool = True) -> Resultado:
    """T07 "Enviar ao RJ": ERRO (ninguém libera) com pendência vencida; ALERTA antes do prazo e no rascunho (R060)."""
    r = Resultado()
    s = situacao(db)
    if s["bloqueado"] and not enviar:
        r.adicionar(CODIGO_AVISO, Nivel.ALERTA, s["mensagem"], quantidade=s["vencidas"])
    elif s["bloqueado"]:
        ex = next(x for x in s["itens"] if x["vencida"])
        r.adicionar(CODIGO_BLOQUEIO, Nivel.ERRO, s["mensagem"], quantidade=s["vencidas"],
                    solicitacao_id=ex["solicitacao_id"], op=ex["op"], lote_itu_id=ex["lote_itu_id"])
    elif s["aviso"]:
        r.adicionar(CODIGO_AVISO, Nivel.ALERTA, s["aviso"], quantidade=s["quantidade"])
    return r


def encerrar(db: Session, sol_id: int, justificativa: str, *, usuario: Usuario, ip: str | None) -> dict[str, Any]:
    """"Encerrar pendência" (peça que não vai mais ser cortada, ex.: OP cancelada) [proposta, P33(e)]."""
    sol = db.scalar(select(SolicitacaoCorte).where(SolicitacaoCorte.id == sol_id).with_for_update())
    if sol is None:
        raise NaoEncontrado("Solicitação não encontrada.")
    texto = (justificativa or "").strip()
    if not texto:   # sem mínimo de caracteres (spec v3.14 §9, Eduardo, 2026-11-17)
        raise ErroNegocio("Escreva a justificativa.")
    if sol.situacao != "AGUARDANDO_CORTE_ITU" or sol.peso_real_encerrada_em is not None:
        raise ErroNegocio("Esta solicitação não está aguardando o peso real.")
    sol.peso_real_encerrada_em = agora()
    sol.peso_real_encerrada_por_id = usuario.id
    sol.peso_real_justificativa = texto[:500]
    auditoria.registrar(db, "PESO_REAL_PENDENCIA_ENCERRADA", usuario_id=usuario.id, entidade="solicitacao",
                        entidade_id=sol.id, depois={"op": sol.op, "justificativa": sol.peso_real_justificativa},
                        ip=ip)
    db.commit()
    return {"solicitacao_id": sol.id, "encerrada_em": sol.peso_real_encerrada_em.isoformat(),
            "encerrada_por": usuario.nome, "justificativa": sol.peso_real_justificativa}
