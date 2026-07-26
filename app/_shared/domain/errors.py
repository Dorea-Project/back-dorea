"""Erreurs de domaine — base commune à tous les contextes bornés.

Chaque contexte préfixe ses codes (`IAM_`, `ATT_`, `ANN_`, …) afin de tracer
l'origine du contexte borné dans les logs et les réponses API, quel que soit le
service qui les relaie (cf. M1 §6). Le mapping HTTP est assuré par la couche
interface (`app/_shared/interface/exception_handlers.py`).
"""

from typing import Any


class DomainError(Exception):
    """Erreur métier portant un code stable et un statut HTTP explicite."""

    code: str = "DOMAIN_ERROR"
    http_status: int = 400

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        http_status: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if http_status is not None:
            self.http_status = http_status
        self.details = details or {}


class NotFoundError(DomainError):
    code = "NOT_FOUND"
    http_status = 404


class UnauthorizedError(DomainError):
    code = "UNAUTHORIZED"
    http_status = 401


class ForbiddenError(DomainError):
    code = "FORBIDDEN"
    http_status = 403


class PayloadTooLargeError(DomainError):
    """Corps de requête au-delà de la limite autorisée (protection anti-DoS mémoire)."""

    code = "PAYLOAD_TOO_LARGE"
    http_status = 413
