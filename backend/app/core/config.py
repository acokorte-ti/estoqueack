"""Configuração central, lida de variáveis de ambiente (.env)."""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "dev"
    app_domain: str = "localhost"
    app_secret_key: str = "dev-inseguro"

    database_url: str = "sqlite:///./estoqueack_dev.db"

    admin_login: str = "admin"
    admin_nome: str = "Administrador"
    admin_senha_inicial: str = ""

    tolerancia_excesso_pct: float = 5.0
    tolerancia_falta_pct: float = 20.0
    tolerancia_sobremetal_pct: float = 20.0
    espessura_serra_mm: float = 3.0
    densidade_padrao: float = 7.85

    login_max_tentativas: int = 5
    login_bloqueio_minutos: int = 15
    sessao_horas: int = 10
    senha_tamanho_minimo: int = Field(default=10, ge=8)

    mega_habilitado: bool = False
    mega_dsn: str = ""
    mega_usuario: str = ""
    mega_senha: str = ""
    mega_escrita_habilitada: bool = False
    # Pasta do Oracle Instant Client 19 (o banco exige Native Network Encryption → modo thick)
    mega_instant_client: str = ""

    @property
    def producao(self) -> bool:
        return self.app_env in ("prod", "homolog")


@lru_cache
def get_config() -> Config:
    cfg = Config()
    if cfg.producao and cfg.app_secret_key in ("", "dev-inseguro", "troque-esta-chave"):
        raise RuntimeError("APP_SECRET_KEY precisa ser definida em homologação/produção.")
    return cfg
