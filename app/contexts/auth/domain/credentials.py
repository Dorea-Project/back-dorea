"""Vue d'authentification d'un compte (read model du contexte Auth).

Auth ne manipule pas l'agrégat `Account` d'IAM : il n'a besoin que du strict
nécessaire pour vérifier une connexion. Cette projection est reconstruite en
lecture depuis la table `accounts` (schéma détenu par ce backend).
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class AuthCredentials:
    account_id: UUID
    phone_number: str
    password_hash: str | None  # backoffice (email + mot de passe)
    hash_algo_version: int | None
    is_active: bool
    email: str | None = None
    pin_hash: str | None = None  # mobile (téléphone + PIN)
