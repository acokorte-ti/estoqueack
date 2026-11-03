"""EstoqueACK — API de controle de matéria-prima AçoKorte."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes import (auth, calculadora, ligas, lotes, mega, notificacoes, painel, saude, solicitacoes,
                            usuarios)
from app.core.config import get_config
from app.core.db import SessionLocal
from app.services.auth import garantir_admin_inicial
from app.services.base import ErroNegocio, NaoEncontrado, PendenciasValidacao

logging.basicConfig(level=logging.INFO, format='{"t":"%(asctime)s","lvl":"%(levelname)s","msg":"%(message)s"}')


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    cfg = get_config()
    with SessionLocal() as db:
        garantir_admin_inicial(db, cfg)
    yield


def criar_app() -> FastAPI:
    cfg = get_config()
    app = FastAPI(
        title="EstoqueACK",
        version="0.1.0",
        description="Controle de matéria-prima AçoKorte (Itu + Barra Mansa)",
        lifespan=ciclo_de_vida,
        docs_url=None if cfg.app_env == "prod" else "/api/docs",
        redoc_url=None,
        openapi_url=None if cfg.app_env == "prod" else "/api/openapi.json",
    )
    for r in (saude.router, auth.router, usuarios.router, ligas.router, calculadora.router, painel.router,
              lotes.router, mega.router, solicitacoes.router, notificacoes.router):
        app.include_router(r, prefix="/api")

    @app.exception_handler(ErroNegocio)
    async def _erro_negocio(_: Request, e: ErroNegocio):
        return JSONResponse(status_code=400, content={"detail": str(e)})

    @app.exception_handler(NaoEncontrado)
    async def _nao_encontrado(_: Request, e: NaoEncontrado):
        return JSONResponse(status_code=404, content={"detail": str(e)})

    @app.exception_handler(PendenciasValidacao)
    async def _pendencias(_: Request, e: PendenciasValidacao):
        return JSONResponse(status_code=409, content=e.previa.como_dict())

    return app


app = criar_app()
