"""Routes d'auth **backoffice** (email + mot de passe + OTP nouvel appareil).

`/login` : email+password+device_id → session (appareil connu) OU 202 « OTP requis ».
`/verify` : email+otp+device_id → l'appareil devient de confiance + session.
Session livrée via cookie **HttpOnly**.
"""

from __future__ import annotations

from contextlib import suppress
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Cookie, Response, status
from pydantic import BaseModel, Field

from app.api.deps import SettingsDep
from app.contexts.auth.domain.errors import InvalidTokenError
from app.contexts.auth.interface.backoffice_dependencies import (
    BACKOFFICE_SESSION_COOKIE,
    BackofficeAuthenticateDep,
    BackofficeVerifyDeviceDep,
    CurrentBackofficeUser,
    DeviceRevocationDep,
    TokenServiceDep,
)

router = APIRouter()


class BackofficeLoginRequest(BaseModel):
    email: str = Field(examples=["pasteur@bethel.ci"])
    password: str = Field(examples=["MotDePasse#2026"])
    device_id: str = Field(description="Identifiant stable de l'appareil (généré par le front)")


class BackofficeVerifyRequest(BaseModel):
    email: str
    otp: str = Field(examples=["123456"])
    device_id: str


class OtpRequired(BaseModel):
    status: str = "otp_required"


class BackofficeSession(BaseModel):
    account_id: UUID


def _set_session_cookie(response: Response, token: str, settings) -> None:
    response.set_cookie(
        key=BACKOFFICE_SESSION_COOKIE,
        value=token,
        httponly=True,
        secure=settings.backoffice_cookie_secure,
        samesite="lax",
        max_age=settings.jwt_session_ttl_seconds,
        path=settings.backoffice_prefix,
    )


@router.post("/login", summary="Connexion backoffice (email + mot de passe + appareil)")
async def backoffice_login(
    payload: BackofficeLoginRequest,
    command: BackofficeAuthenticateDep,
    settings: SettingsDep,
    response: Response,
) -> OtpRequired | None:
    outcome = await command.execute(
        email=payload.email, password=payload.password, device_id=payload.device_id
    )
    if outcome.otp_required:
        response.status_code = status.HTTP_202_ACCEPTED
        return OtpRequired()  # OTP envoyé — appeler /verify
    _set_session_cookie(response, outcome.session_token, settings)
    response.status_code = status.HTTP_204_NO_CONTENT
    return None


@router.post(
    "/verify",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Vérifier l'OTP d'un nouvel appareil → appareil de confiance + session",
)
async def backoffice_verify(
    payload: BackofficeVerifyRequest,
    command: BackofficeVerifyDeviceDep,
    settings: SettingsDep,
    response: Response,
) -> None:
    token = await command.execute(
        email=payload.email, otp=payload.otp, device_id=payload.device_id
    )
    _set_session_cookie(response, token, settings)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Déconnexion backoffice — révoque l'appareil et efface le cookie",
)
async def backoffice_logout(
    response: Response,
    settings: SettingsDep,
    devices: DeviceRevocationDep,
    tokens: TokenServiceDep,
    session: Annotated[str | None, Cookie(alias=BACKOFFICE_SESSION_COOKIE)] = None,
) -> None:
    """DOREA-016 — effacer le cookie ne prouvait rien : le jeton restait valable 12 h.
    On **révoque l'appareil**, et la session meurt à l'instant."""
    if session is not None:
        with suppress(InvalidTokenError):  # jeton déjà mort : la déconnexion réussit
            claims = tokens.decode_session(session)
            await devices.revoke(claims.account_id, claims.device_id, datetime.now(UTC))
    response.delete_cookie(BACKOFFICE_SESSION_COOKIE, path=settings.backoffice_prefix)


@router.get("/me", summary="L'utilisateur backoffice authentifié (via cookie de session)")
async def backoffice_me(actor: CurrentBackofficeUser) -> BackofficeSession:
    return BackofficeSession(account_id=actor.account_id)
