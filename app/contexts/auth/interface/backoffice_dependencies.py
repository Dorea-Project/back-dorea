"""Injection du canal **backoffice** — login email+password+OTP, garde cookie.

Session livrée/relue via cookie **HttpOnly** (protégé du JS → atténuation XSS).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import Cookie, Depends

from app.api.deps import DbSession
from app.contexts.auth.application.actor import Actor
from app.contexts.auth.application.commands.backoffice_authenticate import BackofficeAuthenticate
from app.contexts.auth.application.commands.backoffice_verify_device import BackofficeVerifyDevice
from app.contexts.auth.application.login_throttle import LoginThrottle
from app.contexts.auth.domain.errors import InvalidTokenError
from app.contexts.auth.infrastructure.persistence.device_repository import SqlDeviceRepository
from app.contexts.auth.infrastructure.persistence.repositories import SqlLoginAttemptRepository
from app.contexts.auth.interface.dependencies import (
    CredentialsRepositoryDep,
    PasswordHasherDep,
    TokenServiceDep,
)
from app.contexts.auth.interface.otp_dependencies import (  # noqa: F401 (re-export)
    OtpServiceDep,
    get_code_generator,
)

# Nom du cookie de session backoffice (stable).
BACKOFFICE_SESSION_COOKIE = "dorea_backoffice_session"


def get_backoffice_authenticate(
    credentials: CredentialsRepositoryDep,
    otp: OtpServiceDep,
    hasher: PasswordHasherDep,
    tokens: TokenServiceDep,
    session: DbSession,
) -> BackofficeAuthenticate:
    return BackofficeAuthenticate(
        credentials, SqlDeviceRepository(session), otp, hasher, tokens,
        LoginThrottle(SqlLoginAttemptRepository(session), clock=lambda: datetime.now(UTC)),
    )


BackofficeAuthenticateDep = Annotated[
    BackofficeAuthenticate, Depends(get_backoffice_authenticate)
]


def get_backoffice_verify_device(
    otp: OtpServiceDep, tokens: TokenServiceDep, session: DbSession
) -> BackofficeVerifyDevice:
    return BackofficeVerifyDevice(
        SqlDeviceRepository(session), otp, tokens, clock=lambda: datetime.now(UTC)
    )


BackofficeVerifyDeviceDep = Annotated[
    BackofficeVerifyDevice, Depends(get_backoffice_verify_device)
]


async def get_current_backoffice_user(
    tokens: TokenServiceDep,
    session: Annotated[str | None, Cookie(alias=BACKOFFICE_SESSION_COOKIE)] = None,
) -> Actor:
    if session is None:
        raise InvalidTokenError("Session backoffice requise.")
    return Actor(account_id=tokens.decode_session(session))


CurrentBackofficeUser = Annotated[Actor, Depends(get_current_backoffice_user)]
