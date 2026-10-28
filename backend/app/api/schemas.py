from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PerfilTipo = Literal["ADMIN", "ESTOQUE", "OPERACAO_RJ", "ANALISE"]
PlantaTipo = Literal["ITU", "RJ"]


class LoginEntrada(BaseModel):
    login: str = Field(min_length=1, max_length=60)
    senha: str = Field(min_length=1, max_length=200)


class UsuarioSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    login: str
    nome: str
    email: str | None
    perfil: str
    planta: str
    ativo: bool
    trocar_senha: bool
    ultimo_login: datetime | None


class SessaoSaida(BaseModel):
    usuario: UsuarioSaida
    csrf: str
    expira_em: datetime


class TrocaSenhaEntrada(BaseModel):
    senha_atual: str = Field(min_length=1, max_length=200)
    nova_senha: str = Field(min_length=1, max_length=200)


class UsuarioCriar(BaseModel):
    login: str = Field(min_length=3, max_length=60, pattern=r"^[a-zA-Z0-9._-]+$")
    nome: str = Field(min_length=2, max_length=120)
    email: str | None = Field(default=None, max_length=160)
    perfil: PerfilTipo
    planta: PlantaTipo = "ITU"


class UsuarioAtualizar(BaseModel):
    nome: str | None = Field(default=None, min_length=2, max_length=120)
    email: str | None = Field(default=None, max_length=160)
    perfil: PerfilTipo | None = None
    planta: PlantaTipo | None = None
    ativo: bool | None = None


class UsuarioCriadoSaida(BaseModel):
    usuario: UsuarioSaida
    senha_temporaria: str


class LigaSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    codigo: str
    nome: str
    apelidos: list[str]
    densidade: float
    ativo: bool


class LigaAtualizar(BaseModel):
    nome: str | None = Field(default=None, max_length=120)
    densidade: float | None = Field(default=None, gt=6, lt=10)
    apelidos: list[str] | None = None
    ativo: bool | None = None


class CalculoPesoEntrada(BaseModel):
    formato: Literal["RETANGULAR", "REDONDO", "ANEL"]
    liga: str | None = None
    densidade: float | None = Field(default=None, gt=6, lt=10)
    espessura: float | None = Field(default=None, gt=0)
    largura: float | None = Field(default=None, gt=0)
    diametro: float | None = Field(default=None, gt=0)
    diametro_interno: float | None = Field(default=None, ge=0)
    comprimento: float = Field(gt=0)
    quantidade: int = Field(default=1, ge=1, le=100000)


class CalculoPesoSaida(BaseModel):
    densidade: float
    peso_unitario_kg: float
    peso_total_kg: float


class ValidarPesoEntrada(BaseModel):
    previsto_kg: float = Field(gt=0)
    real_kg: float = Field(gt=0)


class LigaCriar(BaseModel):
    codigo: str = Field(min_length=1, max_length=30)
    nome: str = Field(min_length=1, max_length=120)
    densidade: float = Field(gt=6, lt=10)
    apelidos: list[str] = []
