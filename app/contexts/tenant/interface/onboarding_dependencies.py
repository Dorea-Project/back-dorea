"""Injection des use cases d'onboarding."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends

from app.api.deps import DbSession, SettingsDep
from app.contexts.auth.infrastructure.hashing import HASH_ALGO_VERSION, Argon2PasswordHasher
from app.contexts.auth.interface.backoffice_dependencies import OtpServiceDep
from app.contexts.tenant.application.commands.onboarding import (
    ApproveOnboarding,
    RejectOnboarding,
    SubmitOnboarding,
    VerifyOnboardingEmail,
)
from app.contexts.tenant.infrastructure.persistence.onboarding_repo import SqlOnboardingRepository
from app.contexts.tenant.infrastructure.persistence.store import SqlProvisioningStore

_hasher = Argon2PasswordHasher()


def get_submit_onboarding(otp: OtpServiceDep, session: DbSession) -> SubmitOnboarding:
    return SubmitOnboarding(
        SqlOnboardingRepository(session), otp, _hasher, clock=lambda: datetime.now(UTC)
    )


def get_verify_onboarding_email(otp: OtpServiceDep, session: DbSession) -> VerifyOnboardingEmail:
    return VerifyOnboardingEmail(SqlOnboardingRepository(session), otp)


def get_approve_onboarding(session: DbSession, settings: SettingsDep) -> ApproveOnboarding:
    return ApproveOnboarding(
        SqlOnboardingRepository(session),
        SqlProvisioningStore(session),
        platform_account_id=settings.platform_account_id,
        clock=lambda: datetime.now(UTC),
        hash_algo_version=HASH_ALGO_VERSION,
    )


def get_reject_onboarding(session: DbSession) -> RejectOnboarding:
    return RejectOnboarding(SqlOnboardingRepository(session), clock=lambda: datetime.now(UTC))


SubmitOnboardingDep = Annotated[SubmitOnboarding, Depends(get_submit_onboarding)]
VerifyOnboardingEmailDep = Annotated[VerifyOnboardingEmail, Depends(get_verify_onboarding_email)]
ApproveOnboardingDep = Annotated[ApproveOnboarding, Depends(get_approve_onboarding)]
RejectOnboardingDep = Annotated[RejectOnboarding, Depends(get_reject_onboarding)]
