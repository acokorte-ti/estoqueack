from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import deps
from app.api.schemas import CalculoPesoEntrada, CalculoPesoSaida, ValidarPesoEntrada
from app.core.config import Config
from app.core.db import get_db
from app.domain import peso, regras
from app.models import Liga, Usuario

router = APIRouter(prefix="/calculadora", tags=["calculadora"])


@router.post("/peso", response_model=CalculoPesoSaida)
def calcular_peso(d: CalculoPesoEntrada, db: Session = Depends(get_db), cfg: Config = Depends(deps.config),
                  _: Usuario = Depends(deps.usuario_liberado)):
    dens = d.densidade
    if dens is None:
        tabela = {l.codigo: l.densidade for l in db.scalars(select(Liga).where(Liga.ativo.is_(True)))}
        dens = peso.densidade_da_liga(d.liga, tabela, cfg.densidade_padrao)
    try:
        if d.formato == "RETANGULAR":
            unit = peso.peso_reto(d.espessura, d.largura, d.comprimento, dens)
        elif d.formato == "REDONDO":
            unit = peso.peso_redondo(d.diametro, d.comprimento, dens)
        else:
            unit = peso.peso_anel(d.diametro, d.diametro_interno or 0, d.comprimento, dens)
    except (ValueError, TypeError) as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Medidas inválidas: {e}") from None
    return CalculoPesoSaida(densidade=dens, peso_unitario_kg=unit, peso_total_kg=round(unit * d.quantidade, 3))


@router.post("/validar-peso-real")
def validar_peso_real(d: ValidarPesoEntrada, cfg: Config = Depends(deps.config),
                      _: Usuario = Depends(deps.usuario_liberado)) -> dict:
    """Pré-visualiza a regra de tolerância (5 % de excedente) (mesma regra usada nas movimentações)."""
    r = regras.validar_peso_real(d.previsto_kg, d.real_kg, cfg.tolerancia_excesso_pct, cfg.tolerancia_falta_pct)
    return r.como_dict()
