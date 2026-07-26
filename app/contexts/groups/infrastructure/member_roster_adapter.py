"""Adaptateur `MemberRosterPort` — côté **Groupes** (Groupes → iam, sens correct).

iam exprime son besoin (libérer un membre de ses groupes ici, le placer dans un groupe là-bas) via
le port `MemberRosterPort` ; cet adaptateur le réalise sur le roster des groupes, sans qu'iam ait à
connaître le contexte Groupes. Utilisé par la saga de transfert (`AcceptTransfer`).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from app.contexts.groups.domain.membership import GroupMembership
from app.contexts.groups.infrastructure.persistence.repositories import (
    SqlGroupMembershipRepository,
)
from app.contexts.iam.application.ports import MemberRosterPort


class GroupRosterAdapter(MemberRosterPort):
    def __init__(self, group_memberships: SqlGroupMembershipRepository) -> None:
        self._group_memberships = group_memberships

    async def release_from_tenant(
        self, *, account_id: UUID, tenant_id: UUID, now: datetime
    ) -> None:
        active = await self._group_memberships.list_active_by_account_and_tenant(
            account_id, tenant_id
        )
        for membership in active:
            membership.leave(now=now)
            await self._group_memberships.save(membership)

    async def place_in_group(
        self,
        *,
        account_id: UUID,
        tenant_id: UUID,
        group_id: UUID,
        now: datetime,
        by_account_id: UUID,
    ) -> None:
        if await self._group_memberships.get_active(account_id, group_id) is not None:
            return  # idempotent : déjà dans la cellule
        await self._group_memberships.add(
            GroupMembership.join(
                id=uuid4(),
                group_id=group_id,
                account_id=account_id,
                tenant_id=tenant_id,
                now=now,
                joined_by_account_id=by_account_id,
            )
        )
