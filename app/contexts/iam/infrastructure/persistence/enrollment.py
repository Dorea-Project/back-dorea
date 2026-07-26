"""Implémentation SQLAlchemy de `MemberEnrollmentStore` — écriture atomique d'un membre."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.iam.application.ports import MemberEnrollmentStore
from app.contexts.iam.domain.aggregates import Account, Membership
from app.contexts.iam.domain.enums import AccountCreationSource
from app.contexts.iam.infrastructure.persistence.models import (
    AccountModel,
    MembershipModel,
    RoleAssignmentModel,
)


def _add_membership_rows(
    session: AsyncSession, membership: Membership, actor_account_id: UUID
) -> None:
    now = membership.last_transition_at
    session.add(
        MembershipModel(
            id=membership.id,
            account_id=membership.account_id,
            tenant_id=membership.tenant_id,
            status=membership.status.value,
            last_transition_at=now,
            created_at=now,
            created_by_account_id=actor_account_id,
        )
    )
    for ra in membership.active_roles():
        session.add(
            RoleAssignmentModel(
                id=ra.id,
                membership_id=membership.id,
                tenant_id=membership.tenant_id,
                role=ra.role.value,
                group_id=ra.group_id,
                assigned_at=ra.assigned_at,
                assigned_by_account_id=actor_account_id,
            )
        )


class SqlMemberEnrollmentStore(MemberEnrollmentStore):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def enroll(
        self,
        *,
        account: Account,
        membership: Membership,
        creation_source: AccountCreationSource,
        actor_account_id: UUID,
    ) -> None:
        # Compte SANS credential (M-0) : activation ultérieure sur la surface.
        self._session.add(
            AccountModel(
                id=account.id,
                phone_number=account.phone_number,
                first_name=account.first_name,
                last_name=account.last_name,
                email=account.email,
                password_hash=None,
                pin_hash=None,
                hash_algo_version=None,
                is_phone_verified=account.is_phone_verified,
                created_at=membership.last_transition_at,
                created_by_type=creation_source.value,
                status=account.status.value,
            )
        )
        _add_membership_rows(self._session, membership, actor_account_id)
        await self._session.flush()

    async def add_membership(
        self, *, membership: Membership, actor_account_id: UUID
    ) -> None:
        _add_membership_rows(self._session, membership, actor_account_id)
        await self._session.flush()
