"""Vérification de credentials — partagée par les deux canaux (mobile JWT, session backoffice).

Même store (`accounts.password_hash`), même hasher argon2id : la vérification est
identique quel que soit le canal. Réponse indifférenciée (téléphone inconnu vs code
faux) pour éviter l'énumération de comptes.
"""

from __future__ import annotations

from app.contexts.auth.application.ports import PasswordHasher
from app.contexts.auth.domain.credentials import AuthCredentials
from app.contexts.auth.domain.errors import AccountInactiveError, InvalidCredentialsError

# Hash leurre pour l'**équité temporelle** (DOREA-015) : un identifiant inconnu subit un `verify`
# argon2 factice, pour ne pas répondre plus vite qu'un compte existant (oracle d'existence).
_decoy_hash: str | None = None


def _decoy(hasher: PasswordHasher) -> str:
    global _decoy_hash
    if _decoy_hash is None:
        _decoy_hash = hasher.hash("dorea-decoy-for-constant-time-verify")
    return _decoy_hash


def verify_credentials(
    cred: AuthCredentials | None,
    plain_secret: str,
    hasher: PasswordHasher,
    *,
    use_pin: bool = False,
) -> AuthCredentials:
    """Retourne le credential si valide, sinon lève. Ne révèle pas *quelle* condition a échoué.

    `use_pin=True` vérifie le **PIN mobile** (`pin_hash`) ; sinon le **mot de passe backoffice**
    (`password_hash`). Un compte peut avoir l'un, l'autre, ou les deux (double-surface).

    Anti-énumération (DOREA-015) : identifiant inconnu → `verify` leurre + erreur générique (pas
    d'oracle temporel) ; la **suspension n'est révélée qu'après un secret correct** (sinon un
    attaquant sans le secret distinguerait un compte suspendu d'un compte inexistant).
    """
    stored = cred.pin_hash if (cred and use_pin) else (cred.password_hash if cred else None)
    if cred is None or stored is None:
        hasher.verify(_decoy(hasher), plain_secret)  # équité temporelle — résultat ignoré
        raise InvalidCredentialsError("Identifiant ou secret invalide.")
    if not hasher.verify(stored, plain_secret):
        raise InvalidCredentialsError("Identifiant ou secret invalide.")
    if not cred.is_active:
        raise AccountInactiveError("Ce compte est suspendu.")  # révélé seulement ici
    return cred
