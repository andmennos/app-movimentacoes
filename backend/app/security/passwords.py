"""Hash de senha — spec.md §12.1/plan.md §4. Única camada que conhece o
algoritmo (Argon2id via `pwdlib`); nenhum outro módulo compara senha
diretamente. Senha nunca é cacheada nem persistida em texto puro — apenas
`hash_password(...)` sai deste módulo."""

from __future__ import annotations

from pwdlib import PasswordHash

_password_hash = PasswordHash.recommended()


def hash_password(senha: str) -> str:
    return _password_hash.hash(senha)


def verify_password(senha: str, password_hash: str) -> bool:
    try:
        return _password_hash.verify(senha, password_hash)
    except Exception:  # noqa: BLE001 — hash malformado/algoritmo desconhecido: trata como não confere
        return False
