"""Use cases de l'**onboarding** — demande, vérification email, validation Dorea.

Flux : `submit` (public) → `verify_email` (OTP) → `approve`/`reject` (Dorea).
La matérialisation (tenant + owner) n'a lieu **qu'à l'approbation** (`build_genesis`).
"""

from __future__ import annotations

from uuid import UUID, uuid4

from app.contexts.auth.application.otp_service import OtpService
from app.contexts.auth.application.ports import PasswordHasher
from app.contexts.auth.domain.otp import OtpChannel, OtpPurpose
from app.contexts.auth.domain.password import Password
from app.contexts.tenant.application.dtos import (
    OnboardingResult,
    ProvisionTenantResult,
    SubmitOnboardingInput,
)
from app.contexts.tenant.application.genesis import build_genesis
from app.contexts.tenant.application.ports import ProvisioningStore
from app.contexts.tenant.domain.drafts import OwnerDraft, TenantDraft
from app.contexts.tenant.domain.errors import OnboardingNotFoundError
from app.contexts.tenant.domain.onboarding import OnboardingRequest, OnboardingStatus
from app.contexts.tenant.domain.repositories import OnboardingRepository


class SubmitOnboarding:
    def __init__(
        self, requests: OnboardingRepository, otp: OtpService, hasher: PasswordHasher, *, clock
    ) -> None:
        self._requests = requests
        self._otp = otp
        self._hasher = hasher
        self._clock = clock

    async def execute(self, data: SubmitOnboardingInput) -> OnboardingResult:
        password_hash = self._hasher.hash(Password(data.owner_password).value)
        now = self._clock()
        request = OnboardingRequest(
            id=uuid4(),
            status=OnboardingStatus.SUBMITTED,
            submitted_at=now,
            tenant=TenantDraft(
                name=data.tenant_name,
                denomination=data.denomination,
                country=data.country,
                city=data.city,
                address=data.address,
                latitude=data.latitude,
                longitude=data.longitude,
                contact_email=data.contact_email,
                estimated_member_count=data.estimated_member_count,
                logo_url=data.logo_url,
                short_description=data.short_description,
                contact_name=data.contact_name,
                contact_phone=data.contact_phone,
                timezone=data.timezone,
                language=data.language,
                currency=data.currency,
                operates_annexes=data.operates_annexes,
            ),
            owner=OwnerDraft(
                email=data.owner_email,
                phone=data.owner_phone,
                first_name=data.owner_first_name,
                last_name=data.owner_last_name,
                years_of_experience=data.owner_years_of_experience,
            ),
            owner_password_hash=password_hash,
        )
        await self._requests.add(request)
        await self._otp.issue(
            purpose=OtpPurpose.ONBOARDING_EMAIL, channel=OtpChannel.EMAIL, target=data.owner_email
        )
        return OnboardingResult(request_id=request.id, status=request.status.value)


class VerifyOnboardingEmail:
    def __init__(self, requests: OnboardingRepository, otp: OtpService) -> None:
        self._requests = requests
        self._otp = otp

    async def execute(self, *, request_id: UUID, otp: str) -> OnboardingResult:
        request = await self._get(request_id)
        await self._otp.verify(
            purpose=OtpPurpose.ONBOARDING_EMAIL, target=request.owner.email, code=otp
        )
        request.mark_email_verified()
        await self._requests.save(request)
        return OnboardingResult(request_id=request.id, status=request.status.value)

    async def _get(self, request_id: UUID) -> OnboardingRequest:
        request = await self._requests.get_by_id(request_id)
        if request is None:
            raise OnboardingNotFoundError("Demande d'onboarding introuvable.")
        return request


class ApproveOnboarding:
    """Validation Dorea → matérialise le tenant + owner (genèse)."""

    def __init__(
        self,
        requests: OnboardingRepository,
        store: ProvisioningStore,
        *,
        platform_account_id,
        clock,
        hash_algo_version: int,
    ) -> None:
        self._requests = requests
        self._store = store
        self._platform_account_id = platform_account_id
        self._clock = clock
        self._hash_algo_version = hash_algo_version

    async def execute(self, *, request_id: UUID) -> ProvisionTenantResult:
        request = await self._requests.get_by_id(request_id)
        if request is None:
            raise OnboardingNotFoundError("Demande d'onboarding introuvable.")

        now = self._clock()
        request.approve(now)  # garde : doit être email_verified

        genesis = build_genesis(
            tenant=request.tenant,
            owner=request.owner,
            owner_password_hash=request.owner_password_hash,
            now=now,
        )
        await self._store.provision(
            tenant=genesis.tenant,
            owner_account=genesis.owner_account,
            owner_membership=genesis.owner_membership,
            ownership=genesis.ownership,
            owner_password_hash=request.owner_password_hash,
            hash_algo_version=self._hash_algo_version,
            actor_account_id=self._platform_account_id,
        )
        await self._requests.save(request)
        return ProvisionTenantResult(
            tenant_id=genesis.tenant.id,
            owner_account_id=genesis.owner_account.id,
            owner_membership_id=genesis.owner_membership.id,
        )


class RejectOnboarding:
    def __init__(self, requests: OnboardingRepository, *, clock) -> None:
        self._requests = requests
        self._clock = clock

    async def execute(self, *, request_id: UUID, reason: str) -> OnboardingResult:
        request = await self._requests.get_by_id(request_id)
        if request is None:
            raise OnboardingNotFoundError("Demande d'onboarding introuvable.")
        request.reject(self._clock(), reason)
        await self._requests.save(request)
        return OnboardingResult(request_id=request.id, status=request.status.value)
