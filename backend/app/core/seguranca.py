"""Senhas (Argon2id), tokens de sessão e CSRF."""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_ph = PasswordHasher()  # Argon2id com parâmetros recomendados pela biblioteca
_HASH_FALSO = _ph.hash("senha-falsa-para-tempo-constante")


def gerar_hash_senha(senha: str) -> str:
    return _ph.hash(senha)


def verificar_senha(senha: str, hash_: str | None) -> bool:
    """Compara senha e hash. Sem hash, executa verificação falsa (evita descobrir logins pelo tempo)."""
    try:
        return _ph.verify(hash_ or _HASH_FALSO, senha) and hash_ is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def precisa_rehash(hash_: str) -> bool:
    return _ph.check_needs_rehash(hash_)


def problemas_senha(senha: str, login: str, tamanho_minimo: int) -> list[str]:
    erros = []
    if len(senha) < tamanho_minimo:
        erros.append(f"A senha deve ter pelo menos {tamanho_minimo} caracteres.")
    # Decisão do Eduardo (2026-10-30): só o tamanho mínimo; pode ser só números. A proteção contra força bruta
    # fica no bloqueio por tentativas e na restrição de IP.
    return erros


def gerar_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Guardamos só o hash do token de sessão; o valor real fica apenas no cookie do usuário."""
    return hashlib.sha256(token.encode()).hexdigest()


def comparar(a: str | None, b: str | None) -> bool:
    return bool(a) and bool(b) and hmac.compare_digest(a, b)


def gerar_senha_temporaria() -> str:
    alfabeto = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"
    while True:
        s = "".join(secrets.choice(alfabeto) for _ in range(12))
        if re.search(r"\d", s) and re.search(r"[A-Za-z]", s):
            return s
