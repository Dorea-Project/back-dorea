"""Implémentations SQLAlchemy des dépôts IAM + mappers ORM → domaine."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.iam.domain.aggregates import Account, Membership
from app.contexts.iam.domain.entities import RoleAssignment
from app.contexts.iam.domain.enums import (
    AbsenceReason,
    AccountStatus,
    MembershipStatus,
    RevocationReason,
    RoleCode,
)
from app.contexts.iam.domain.repositories import AccountRepository, MembershipRepository
from app.contexts.iam.infrastructure.persistence.models import (
    AccountModel,
    MembershipModel,
    RoleAssignmentModel,
)


def _to_role_assignment(row: RoleAssignmentModel) -> RoleAssignment:
    return RoleAssignment(
        id=row.id,
        role=RoleCode(row.role),
        group_id=row.group_id,
        assigned_at=row.assigned_at,
        assigned_by_account_id=row.assigned_by_account_id,
        revoked_at=row.revoked_at,
        revoked_reason=(
            RevocationReason(row.revoked_reason) if row.revoked_reason is not None else None
        ),
    )


def _to_membership(row: MembershipModel) -> Membership:
    return Membership(
        id=row.id,
        account_id=row.account_id,
        tenant_id=row.tenant_id,
        status=MembershipStatus(row.status),
        last_transition_at=row.last_transition_at,
        active_absence_reason=(
            AbsenceReason(row.active_absence_reason)
            if row.active_absence_reason is not None
            else None
        ),
        closed_at=row.closed_at,
        role_assignments=[_to_role_assignment(ra) for ra in row.role_assignments],
    )


def _to_account(row: AccountModel) -> Account:
    return Account(
        id=row.id,
        phone_number=row.phone_number,
        status=AccountStatus(row.status),
        first_name=row.first_name,
        last_name=row.last_name,
        email=row.email,
        is_phone_verified=row.is_phone_verified,
    )


class SqlAlchemyAccountRepository(AccountRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, account_id: UUID) -> Account | None:
        row = await self._session.get(AccountModel, account_id)
        return _to_account(row) if row is not None else None

    async def get_by_phone(self, phone_number: str) -> Account | None:
        stmt = select(AccountModel).where(AccountModel.phone_number == phone_number)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_account(row) if row is not None else None


class SqlAlchemyMembershipRepository(MembershipRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_active(self, account_id: UUID, tenant_id: UUID) -> Membership | None:
        stmt = (
            select(MembershipModel)
            .where(
                MembershipModel.account_id == account_id,
                MembershipModel.tenant_id == tenant_id,
                MembershipModel.status != MembershipStatus.CLOSED.value,
            )
            .limit(1)
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_membership(row) if row is not None else None

    async def list_active_by_account(self, account_id: UUID) -> list[Membership]:
        stmt = select(MembershipModel).where(
            MembershipModel.account_id == account_id,
            MembershipModel.status != MembershipStatus.CLOSED.value,
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_membership(row) for row in rows]

    async def count_active_group_leaders(self, tenant_id: UUID, group_id: UUID) -> int:
        stmt = select(func.count()).where(
            RoleAssignmentModel.tenant_id == tenant_id,
            RoleAssignmentModel.role == RoleCode.GROUP_LEADER.value,
            RoleAssignmentModel.group_id == group_id,
            RoleAssignmentModel.revoked_at.is_(None),
        )
        return (await self._session.execute(stmt)).scalar_one()
