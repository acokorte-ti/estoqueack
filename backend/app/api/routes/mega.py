"""Consultas ao Mega usadas pelas telas (somente leitura). Contrato: docs/api/01_contrato_api.md §5."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.api import deps
from app.domain.medidas import interpretar
from app.integrations.mega import fabrica
from app.models import Usuario

router = APIRouter(prefix="/mega", tags=["mega"])

# Códigos de situação de PRO_ORDENS confirmados até agora (docs/integracao_mega.md)
SITUACAO = {"AB": ("Aberta", True)}


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
    return {"numero": op.numero, "item_codigo": op.item_codigo, "item_descricao": op.item_descricao,
            "cliente": op.cliente, "situacao": op.situacao, "situacao_descricao": desc, "aberta": aberta,
            "quantidade": op.quantidade,
            "data_recebimento": op.data_recebimento.isoformat() if op.data_recebimento else None,
            "medida_sugerida": medida, "historico": {"solicitacoes": [], "sas": []}, "fonte": "MEGA"}
