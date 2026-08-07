"""Composition root du contexte Auth — câble hasher, JWT, dépôt et use cases,
et fournit l'acteur authentifié aux autres contextes.
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.deps import DbSession, SettingsDep
from app.contexts.auth.application.actor import Actor
from app.contexts.auth.application.commands.account_security import ChangePassword, ChangePhone
from app.contexts.auth.application.commands.login import Login
from app.contexts.auth.application.commands.refresh_token import RefreshToken
from app.contexts.auth.application.commands.register_member import RegisterMember
from app.contexts.auth.application.commands.verify_device_login import VerifyDeviceLogin
from app.contexts.auth.application.login_throttle import LoginThrottle
from app.contexts.auth.application.ports import PasswordHasher, TokenClaims, TokenService
from app.contexts.auth.domain.errors import InvalidTokenError
from app.contexts.auth.domain.repositories import CredentialsRepository
from app.contexts.auth.infrastructure.hashing import HASH_ALGO_VERSION, Argon2PasswordHasher
from app.contexts.auth.infrastructure.jwt_service import JwtTokenService
from app.contexts.auth.infrastructure.persistence.device_repository import SqlDeviceRepository
from app.contexts.auth.infrastructure.persistence.repositories import (
    SqlAccountSecurityRepository,
    SqlCredentialsRepository,
    SqlLoginAttemptRepository,
)
from app.contexts.auth.interface.otp_dependencies import OtpServiceDep

# Le hasher est sans état → instance unique réutilisée.
_hasher = Argon2PasswordHasher()


def get_password_hasher() -> PasswordHasher:
    return _hasher


def get_token_service(settings: SettingsDep) -> TokenService:
    return JwtTokenService(
        secret=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
        access_ttl_seconds=settings.jwt_access_ttl_seconds,
        refresh_ttl_seconds=settings.jwt_refresh_ttl_seconds,
        session_ttl_seconds=settings.jwt_session_ttl_seconds,
    )


PasswordHasherDep = Annotated[PasswordHasher, Depends(get_password_hasher)]
TokenServiceDep = Annotated[TokenService, Depends(get_token_service)]


def get_credentials_repository(session: DbSession) -> CredentialsRepository:
    return SqlCredentialsRepository(session)


CredentialsRepositoryDep = Annotated[CredentialsRepository, Depends(get_credentials_repository)]


def _throttle(session) -> LoginThrottle:
    return LoginThrottle(
        SqlLoginAttemptRepository(session), clock=lambda: datetime.now(UTC)
    )


def get_login_command(
    credentials: CredentialsRepositoryDep,
    hasher: PasswordHasherDep,
    tokens: TokenServiceDep,
    otp: OtpServiceDep,
    session: DbSession,
) -> Login:
    return Login(
        credentials, SqlDeviceRepository(session), otp, hasher, tokens, _throttle(session)
    )


def get_verify_device_login_command(
    tokens: TokenServiceDep, otp: OtpServiceDep, session: DbSession
) -> VerifyDeviceLogin:
    return VerifyDeviceLogin(
        SqlDeviceRepository(session), otp, tokens, clock=lambda: datetime.now(UTC)
    )


def get_refresh_command(tokens: TokenServiceDep, session: DbSession) -> RefreshToken:
    return RefreshToken(tokens, SqlDeviceRepository(session))


def get_register_member_command(
    credentials: CredentialsRepositoryDep,
    hasher: PasswordHasherDep,
    tokens: TokenServiceDep,
    otp: OtpServiceDep,
    session: DbSession,
) -> RegisterMember:
    return RegisterMember(
        credentials,
        SqlAccountSecurityRepository(session),
        SqlDeviceRepository(session),
        otp,
        hasher,
        tokens,
        clock=lambda: datetime.now(UTC),
        hash_algo_version=HASH_ALGO_VERSION,
    )


LoginDep = Annotated[Login, Depends(get_login_command)]
VerifyDeviceLoginDep = Annotated[VerifyDeviceLogin, Depends(get_verify_device_login_command)]
RefreshTokenDep = Annotated[RefreshToken, Depends(get_refresh_command)]
RegisterMemberDep = Annotated[RegisterMember, Depends(get_register_member_command)]

# --- Acteur authentifié (remplace le placeholder pré-M2) ---

_bearer = HTTPBearer(auto_error=False, description="JWT d'accès mobile")


async def get_current_claims(
    tokens: TokenServiceDep,
    session: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> TokenClaims:
    """Qui, et **depuis quel appareil** — la porte d'entrée mobile."""
    if credentials is None:
        raise InvalidTokenError("Jeton d'accès requis.")
    claims = tokens.decode_access(credentials.credentials)
    # DOREA-016 — la signature ne suffit pas : l'appareil doit être **encore** de
    # confiance. Un appareil déconnecté ou révoqué est refusé à la porte, sans
    # attendre l'expiration du jeton.
    if not await SqlDeviceRepository(session).is_trusted(claims.account_id, claims.device_id):
        raise InvalidTokenError("Appareil révoqué — reconnectez-vous.")
    return claims


CurrentActorClaims = Annotated[TokenClaims, Depends(get_current_claims)]


async def get_current_actor(claims: CurrentActorClaims) -> Actor:
    return Actor(account_id=claims.account_id)


CurrentActor = Annotated[Actor, Depends(get_current_actor)]


def get_mobile_device_revocation(session: DbSession) -> SqlDeviceRepository:
    """Le registre des appareils, pour la déconnexion mobile (DOREA-016)."""
    return SqlDeviceRepository(session)


MobileDeviceRevocationDep = Annotated[
    SqlDeviceRepository, Depends(get_mobile_device_revocation)
]


# --- Opérations sensibles membre (P5) ---


def get_change_password_command(
    credentials: CredentialsRepositoryDep,
    hasher: PasswordHasherDep,
    otp: OtpServiceDep,
    session: DbSession,
) -> ChangePassword:
    return ChangePassword(
        credentials,
        SqlAccountSecurityRepository(session),
        otp,
        hasher,
        hash_algo_version=HASH_ALGO_VERSION,
    )


def get_change_phone_command(otp: OtpServiceDep, session: DbSession) -> ChangePhone:
    return ChangePhone(SqlAccountSecurityRepository(session), otp)


ChangePasswordDep = Annotated[ChangePassword, Depends(get_change_password_command)]
ChangePhoneDep = Annotated[ChangePhone, Depends(get_change_phone_command)]
