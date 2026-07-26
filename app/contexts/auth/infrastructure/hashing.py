"""Hashage argon2id du code secret.

⚠️ L'algorithme et ses paramètres doivent rester cohérents entre les canaux
d'auth (session backoffice + JWT mobile) du même backend (faiblesse R5) : la
chaîne argon2 encodée (`$argon2id$v=19$m=...`) est portable, donc `verify`
interopère entre les deux canaux tant que l'algo est le même.
"""

from __future__ import annotations

from argon2 import PasswordHasher as _Argon2
from argon2.exceptions import Argon2Error

from app.contexts.auth.application.ports import PasswordHasher

# Version logique du schéma de hash (colonne accounts.hash_algo_version).
HASH_ALGO_VERSION = 1


class Argon2PasswordHasher(PasswordHasher):
    def __init__(self) -> None:
        self._hasher = _Argon2()  # argon2id, paramètres par défaut de la lib

    def verify(self, hashed: str, plain: str) -> bool:
        try:
            return self._hasher.verify(hashed, plain)
        except Argon2Error:
            return False

    def hash(self, plain: str) -> str:
        return self._hasher.hash(plain)
