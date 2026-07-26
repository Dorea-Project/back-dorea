"""Traduction des erreurs de domaine en réponses HTTP.

Forme de réponse stable, indépendante du contexte émetteur :

    { "error": { "code": "IAM_UNAUTHORIZED_SCOPE", "message": "...", "details": {...} } }
"""

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app._shared.domain.errors import DomainError
from app.core.logging import get_logger

logger = get_logger("errors")


def _error_body(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _domain_error_handler(_: Request, exc: DomainError) -> JSONResponse:
        logger.info("domain_error", code=exc.code, message=exc.message, details=exc.details)
        return JSONResponse(
            status_code=exc.http_status,
            content=_error_body(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(IntegrityError)
    async def _integrity_handler(_: Request, exc: IntegrityError) -> JSONResponse:
        # Violation de contrainte BDD (unicité, clé étrangère…) : on renvoie un
        # 409 stable au lieu de laisser fuiter un 500 « Internal Server Error ».
        # Le détail (nom de contrainte, SQL) est journalisé mais **jamais** exposé.
        logger.warning("integrity_error", detail=str(exc.orig))
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=_error_body(
                "CONFLICT",
                "La ressource entre en conflit avec une donnée existante.",
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_error_body(
                "VALIDATION_ERROR",
                "La requête est invalide.",
                {"errors": exc.errors()},
            ),
        )
