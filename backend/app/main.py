"""EstoqueACK — API de controle de matéria-prima AçoKorte."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import auth, calculadora, ligas, painel, saude, usuarios
from app.core.config import get_config
from app.core.db import SessionLocal
from app.services.auth import garantir_admin_inicial

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
    for r in (saude.router, auth.router, usuarios.router, ligas.router, calculadora.router, painel.router):
        app.include_router(r, prefix="/api")
    return app


app = criar_app()
