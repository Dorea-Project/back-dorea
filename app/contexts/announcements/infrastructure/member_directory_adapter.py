"""Adaptateur `MemberDirectoryPort` — liste les comptes membres actifs d'une église (iam).

Sert le broadcast d'une annonce église-entière : à qui pousser la notification."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.announcements.application.ports import MemberDirectoryPort
from app.contexts.groups.domain.membership import GroupMembershipStatus
from app.contexts.groups.infrastructure.persistence.models import (
    GroupMembershipModel,
    GroupModel,
)
from app.contexts.iam.domain.enums import MembershipStatus
from app.contexts.iam.infrastructure.persistence.models import MembershipModel


class IamMemberDirectoryAdapter(MemberDirectoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def member_account_ids(self, tenant_id: UUID) -> list[UUID]:
        stmt = select(MembershipModel.account_id.distinct()).where(
            MembershipModel.tenant_id == tenant_id,
            MembershipModel.status != MembershipStatus.CLOSED.value,
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def member_account_ids_in_subtree(
        self, tenant_id: UUID, group_id: UUID
    ) -> list[UUID]:
        group = await self._session.get(GroupModel, group_id)
        if group is None or group.tenant_id != tenant_id:
            return []
        # Chemin matérialisé : le sous-arbre = les groupes dont le chemin préfixe celui du scope
        # (le groupe lui-même inclus, car son propre chemin commence par lui-même).
        subtree = select(GroupModel.id).where(
            GroupModel.tenant_id == tenant_id,
            GroupModel.path.like(f"{group.path}%"),
        )
        stmt = select(GroupMembershipModel.account_id.distinct()).where(
            GroupMembershipModel.tenant_id == tenant_id,
            GroupMembershipModel.group_id.in_(subtree),
            GroupMembershipModel.status == GroupMembershipStatus.ACTIVE.value,
        )
        return list((await self._session.execute(stmt)).scalars().all())
