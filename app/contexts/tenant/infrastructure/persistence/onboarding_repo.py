"""Implémentation SQLAlchemy de `OnboardingRepository`."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.tenant.domain.drafts import OwnerDraft, TenantDraft
from app.contexts.tenant.domain.onboarding import OnboardingRequest, OnboardingStatus
from app.contexts.tenant.domain.repositories import OnboardingRepository
from app.contexts.tenant.infrastructure.persistence.models import OnboardingRequestModel


def _to_request(row: OnboardingRequestModel) -> OnboardingRequest:
    return OnboardingRequest(
        id=row.id,
        status=OnboardingStatus(row.status),
        submitted_at=row.submitted_at,
        tenant=TenantDraft(
            name=row.tenant_name,
            denomination=row.denomination,
            country=row.country,
            city=row.city,
            address=row.address,
            latitude=row.latitude,
            longitude=row.longitude,
            contact_email=row.contact_email,
            estimated_member_count=row.estimated_member_count,
            logo_url=row.logo_url,
            short_description=row.short_description,
            contact_name=row.contact_name,
            contact_phone=row.contact_phone,
            timezone=row.timezone,
            language=row.language,
            currency=row.currency,
            operates_annexes=row.operates_annexes,
        ),
        owner=OwnerDraft(
            email=row.owner_email,
            phone=row.owner_phone,
            first_name=row.owner_first_name,
            last_name=row.owner_last_name,
            years_of_experience=row.owner_years_of_experience,
        ),
        owner_password_hash=row.owner_password_hash,
        decided_at=row.decided_at,
        rejection_reason=row.rejection_reason,
    )


class SqlOnboardingRepository(OnboardingRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, request: OnboardingRequest) -> None:
        t, o = request.tenant, request.owner
        self._session.add(
            OnboardingRequestModel(
                id=request.id,
                status=request.status.value,
                submitted_at=request.submitted_at,
                decided_at=request.decided_at,
                rejection_reason=request.rejection_reason,
                tenant_name=t.name,
                denomination=t.denomination,
                country=t.country,
                city=t.city,
                address=t.address,
                latitude=t.latitude,
                longitude=t.longitude,
                contact_email=t.contact_email,
                estimated_member_count=t.estimated_member_count,
                logo_url=t.logo_url,
                short_description=t.short_description,
                contact_name=t.contact_name,
                contact_phone=t.contact_phone,
                timezone=t.timezone,
                language=t.language,
                currency=t.currency,
                operates_annexes=t.operates_annexes,
                owner_email=o.email,
                owner_phone=o.phone,
                owner_first_name=o.first_name,
                owner_last_name=o.last_name,
                owner_years_of_experience=o.years_of_experience,
                owner_password_hash=request.owner_password_hash,
            )
        )
        await self._session.flush()

    async def get_by_id(self, request_id: UUID) -> OnboardingRequest | None:
        row = await self._session.get(OnboardingRequestModel, request_id)
        return _to_request(row) if row is not None else None

    async def save(self, request: OnboardingRequest) -> None:
        await self._session.execute(
            update(OnboardingRequestModel)
            .where(OnboardingRequestModel.id == request.id)
            .values(
                status=request.status.value,
                decided_at=request.decided_at,
                rejection_reason=request.rejection_reason,
            )
        )
