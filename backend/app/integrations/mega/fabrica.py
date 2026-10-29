"""Fornece o gateway do Mega para a API (um pool por processo). Testes podem trocar via `definir`."""
from __future__ import annotations

import threading

from app.core.config import get_config

from .gateway import MegaGateway, OracleMegaGateway

_lock = threading.Lock()
_gateway: MegaGateway | None = None


class MegaIndisponivel(RuntimeError):
    pass


def obter() -> MegaGateway:
    global _gateway
    if _gateway is not None:
        return _gateway
    cfg = get_config()
    if not cfg.mega_habilitado:
        raise MegaIndisponivel("Integração com o Mega desligada neste ambiente.")
    with _lock:
        if _gateway is None:
            try:
                _gateway = OracleMegaGateway(cfg)
            except Exception as e:  # noqa: BLE001 — falha de rede/credencial não pode derrubar a API
                raise MegaIndisponivel(f"Não foi possível conectar ao Mega: {type(e).__name__}") from e
    return _gateway


def definir(g: MegaGateway | None) -> None:
    """Usado nos testes (MegaFalso)."""
    global _gateway
    _gateway = g
