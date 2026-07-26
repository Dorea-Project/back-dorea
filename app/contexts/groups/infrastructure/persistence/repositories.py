"""Implémentation SQLAlchemy de `GroupRepository`."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.groups.domain.aggregates import Group
from app.contexts.groups.domain.enums import GroupStatus, GroupType
from app.contexts.groups.domain.membership import GroupMembership, GroupMembershipStatus
from app.contexts.groups.domain.repositories import (
    GroupMembershipRepository,
    GroupRepository,
)
from app.contexts.groups.infrastructure.persistence.models import (
    GroupMembershipModel,
    GroupModel,
)

_ACTIVE = GroupMembershipStatus.ACTIVE.value


def _to_group(row: GroupModel) -> Group:
    return Group(
        id=row.id,
        tenant_id=row.tenant_id,
        name=row.name,
        type=GroupType(row.type),
        path=row.path,
        parent_group_id=row.parent_group_id,
        status=GroupStatus(row.status),
        created_at=row.created_at,
        created_by_account_id=row.created_by_account_id,
        multiplied_from_id=row.multiplied_from_id,
        generation=row.generation,
    )


class SqlGroupRepository(GroupRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, group: Group) -> None:
        self._session.add(
            GroupModel(
                id=group.id,
                tenant_id=group.tenant_id,
                name=group.name,
                type=group.type.value,
                status=group.status.value,
                parent_group_id=group.parent_group_id,
                path=group.path,
                multiplied_from_id=group.multiplied_from_id,
                created_at=group.created_at,
                created_by_account_id=group.created_by_account_id,
            )
        )
        await self._session.flush()

    async def get(self, group_id: UUID) -> Group | None:
        row = await self._session.get(GroupModel, group_id)
        return _to_group(row) if row is not None else None

    async def list_children_by_lineage(self, mother_id: UUID) -> list[Group]:
        stmt = select(GroupModel).where(GroupModel.multiplied_from_id == mother_id)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_group(r) for r in rows]

    async def list_active_structural_children(self, parent_id: UUID) -> list[Group]:
        stmt = select(GroupModel).where(
            GroupModel.parent_group_id == parent_id,
            GroupModel.status != GroupStatus.CLOSED.value,
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_group(r) for r in rows]

    async def list_active_by_tenant(self, tenant_id: UUID) -> list[Group]:
        stmt = select(GroupModel).where(
            GroupModel.tenant_id == tenant_id,
            GroupModel.status != GroupStatus.CLOSED.value,
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_group(r) for r in rows]

    async def save(self, group: Group) -> None:
        await self._session.execute(
            update(GroupModel)
            .where(GroupModel.id == group.id)
            .values(name=group.name, status=group.status.value, generation=group.generation)
        )


def _to_group_membership(row: GroupMembershipModel) -> GroupMembership:
    return GroupMembership(
        id=row.id,
        group_id=row.group_id,
        account_id=row.account_id,
        tenant_id=row.tenant_id,
        status=GroupMembershipStatus(row.status),
        joined_at=row.joined_at,
        joined_by_account_id=row.joined_by_account_id,
        left_at=row.left_at,
    )


class SqlGroupMembershipRepository(GroupMembershipRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, membership: GroupMembership) -> None:
        self._session.add(
            GroupMembershipModel(
                id=membership.id,
                group_id=membership.group_id,
                account_id=membership.account_id,
                tenant_id=membership.tenant_id,
                status=membership.status.value,
                joined_at=membership.joined_at,
                joined_by_account_id=membership.joined_by_account_id,
                left_at=membership.left_at,
            )
        )
        await self._session.flush()

    async def save(self, membership: GroupMembership) -> None:
        await self._session.execute(
            update(GroupMembershipModel)
            .where(GroupMembershipModel.id == membership.id)
            .values(status=membership.status.value, left_at=membership.left_at)
        )

    async def get_active(self, account_id: UUID, group_id: UUID) -> GroupMembership | None:
        stmt = select(GroupMembershipModel).where(
            GroupMembershipModel.account_id == account_id,
            GroupMembershipModel.group_id == group_id,
            GroupMembershipModel.status == _ACTIVE,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_group_membership(row) if row is not None else None

    async def list_active_by_group(self, group_id: UUID) -> list[GroupMembership]:
        stmt = select(GroupMembershipModel).where(
            GroupMembershipModel.group_id == group_id,
            GroupMembershipModel.status == _ACTIVE,
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_group_membership(r) for r in rows]

    async def list_active_by_account_and_tenant(
        self, account_id: UUID, tenant_id: UUID
    ) -> list[GroupMembership]:
        """Toutes les cellules/groupes actifs d'un compte dans un tenant (transfert sortant).

        Hors interface `GroupMembershipRepository` (besoin ponctuel de l'adaptateur roster)."""
        stmt = select(GroupMembershipModel).where(
            GroupMembershipModel.account_id == account_id,
            GroupMembershipModel.tenant_id == tenant_id,
            GroupMembershipModel.status == _ACTIVE,
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_group_membership(r) for r in rows]
