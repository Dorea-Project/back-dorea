"""Dépendances OTP — neutres (partagées backoffice & mobile), sans cycle d'imports.

`get_code_generator` est isolé pour être surchargeable en test (code déterministe).
"""

from __future__ import annotations

from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.api.deps import DbSession, SettingsDep
from app.contexts.auth.application.otp_service import OtpService
from app.contexts.auth.application.ports import CodeGenerator, OtpSender
from app.contexts.auth.infrastructure.hashing import Argon2PasswordHasher
from app.contexts.auth.infrastructure.otp import SecureCodeGenerator
from app.contexts.auth.infrastructure.otp_delivery import build_otp_sender
from app.contexts.auth.infrastructure.persistence.otp_repository import SqlOtpChallengeRepository
from app.core.config import get_settings

_hasher = Argon2PasswordHasher()


@lru_cache
def _get_sender() -> OtpSender:
    # Sender réel (email/SMS) si configuré, sinon repli sur le log — construit une fois (settings
    # est déjà un singleton mémoïsé).
    return build_otp_sender(get_settings())


def get_code_generator(settings: SettingsDep) -> CodeGenerator:
    return SecureCodeGenerator(settings.otp_code_length)


CodeGeneratorDep = Annotated[CodeGenerator, Depends(get_code_generator)]


def get_otp_service(
    session: DbSession, settings: SettingsDep, codes: CodeGeneratorDep
) -> OtpService:
    return OtpService(
        SqlOtpChallengeRepository(session),
        _get_sender(),
        _hasher,
        codes,
        clock=lambda: datetime.now(UTC),
        ttl_seconds=settings.otp_ttl_seconds,
    )


OtpServiceDep = Annotated[OtpService, Depends(get_otp_service)]
