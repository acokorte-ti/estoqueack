"""Consultas ao Mega usadas pelas telas (somente leitura). Contrato: docs/api/01_contrato_api.md §5."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import deps
from app.core.db import get_db
from app.domain.medidas import interpretar
from app.integrations.mega import fabrica
from app.integrations.mega.consultas import SITUACOES_OP
from app.models import SyncMega, Usuario
from app.services import sync_mega

router = APIRouter(prefix="/mega", tags=["mega"])

SITUACAO = SITUACOES_OP


@router.post("/sincronizar")
def sincronizar_agora(db: Session = Depends(get_db),
                      usuario: Usuario = Depends(deps.exigir_perfil("ESTOQUE", "ANALISE"))):
    """'Sincronizar agora' (P04): saldo, preço médio e movimentos; depois verifica os SAs aguardando."""
    s = sync_mega.sincronizar_estoque(db, gatilho="MANUAL", usuario_id=usuario.id)
    if s.situacao == "OCUPADO":
        return JSONResponse(status_code=409, content={"detail": "Já existe uma sincronização rodando. Aguarde."})
    out = {"estoque": sync_mega.para_dict(s)}
    if s.situacao == "OK":
        out["sa"] = sync_mega.para_dict(sync_mega.verificar_sas(db, gatilho="MANUAL", usuario_id=usuario.id))
    return out


@router.get("/sincronizacoes")
def sincronizacoes(limite: int = 20, db: Session = Depends(get_db), _: Usuario = Depends(deps.usuario_liberado)):
    """Histórico da sincronização (T03/T16: 'Mega atualizado em …')."""
    q = select(SyncMega).order_by(SyncMega.iniciado_em.desc(), SyncMega.id.desc()).limit(min(max(limite, 1), 100))
    ult = sync_mega.ultima(db, "ESTOQUE")
    return {"ultima_ok": sync_mega.para_dict(ult) if ult else None,
            "itens": [sync_mega.para_dict(s) for s in db.scalars(q)]}


@router.get("/op/{numero}")
def ordem_producao(numero: int, _: Usuario = Depends(deps.usuario_liberado)):
    try:
        op = fabrica.obter().ordem_producao(numero)
    except fabrica.MegaIndisponivel as e:
        return JSONResponse(status_code=503, content={"detail": f"Mega indisponível: {e}", "pode_digitar": True})
    except Exception as e:  # noqa: BLE001
        return JSONResponse(status_code=503, content={"detail": f"Erro ao consultar o Mega ({type(e).__name__}).",
                                                      "pode_digitar": True})
    if op is None:
        return JSONResponse(status_code=404, content={"detail": "OP não encontrada no Mega."})
    desc, aberta = SITUACAO.get(op.situacao or "", (op.situacao, None))
    medida = None
    if op.item_descricao:
        m = interpretar(op.item_descricao)
        if m.formato in ("RETANGULAR", "REDONDO"):
            medida = {"formato": m.formato, "espessura": m.espessura, "largura": m.largura,
                      "diametro": m.diametro, "comprimento": m.comprimento}
    try:
        estrutura = [{"codigo": c.codigo, "descricao": c.descricao, "tipo": c.tipo, "um": c.um,
                      "qtd_necessaria": c.qtd_necessaria, "qtd_unitaria": c.qtd_unitaria,
                      "qtd_requisitada": c.qtd_requisitada} for c in fabrica.obter().estrutura_op(numero)]
    except Exception:  # noqa: BLE001 — estrutura é informativa (T07); falha não derruba a consulta da OP
        estrutura = None
    return {"numero": op.numero, "item_codigo": op.item_codigo, "item_descricao": op.item_descricao,
            "estrutura": estrutura,
            "cliente": op.cliente, "cliente_codigo": op.cliente_codigo, "pedido": op.pedido, "tipo": op.tipo,
            "situacao": op.situacao, "situacao_descricao": desc, "aberta": aberta,
            "quantidade": op.quantidade,
            "data_recebimento": op.data_recebimento.isoformat() if op.data_recebimento else None,
            "medida_sugerida": medida, "historico": {"solicitacoes": [], "sas": []}, "fonte": "MEGA"}
