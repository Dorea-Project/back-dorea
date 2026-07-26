"""Use case `RevokeGroupLeadership` — retirer un grade de leadership (M4 §5, G-5).

Pendant de `AppointGroupLeadership`. Autorité **par grade** (« structurer depuis au-dessus ») :
- `leader` (`group_leader`, plein) → autorité du **parent** (`ensure_can_manage_structure`) ;
- `in_training` (« Timothée ») → autorité du **nœud** (`ensure_can_manage`, mentorat).
"""

from __future__ import annotations

from uuid import UUID

from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.groups.application.group_lookup import load_group_in_tenant
from app.contexts.groups.application.ports import ChurchRoleStore
from app.contexts.groups.domain.errors import LeadershipNotFoundError
from app.contexts.groups.domain.leadership import GroupLeadershipGrade
from app.contexts.groups.domain.repositories import GroupRepository
from app.contexts.iam.domain.enums import RoleCode
from app.contexts.iam.domain.repositories import MembershipRepository


class RevokeGroupLeadership:
    def __init__(
        self,
        groups: GroupRepository,
        church_memberships: MembershipRepository,
        roles: ChurchRoleStore,
        access: GroupAccessPolicy,
        *,
        clock,
    ) -> None:
        self._groups = groups
        self._church_memberships = church_memberships
        self._roles = roles
        self._access = access
        self._clock = clock

    async def execute(
        self,
        *,
        actor_account_id: UUID,
        tenant_id: UUID,
        group_id: UUID,
        account_id: UUID,
        grade: GroupLeadershipGrade,
    ) -> None:
        group = await load_group_in_tenant(self._groups, group_id, tenant_id)
        role = grade.to_role()

        # Autorité par grade : plein → parent ; formation → nœud (mentorat).
        if role is RoleCode.GROUP_LEADER:
            await self._access.ensure_can_manage_structure(
                actor_account_id=actor_account_id, group=group
            )
        else:
            await self._access.ensure_can_manage(actor_account_id=actor_account_id, group=group)

        membership = await self._church_memberships.get_active(account_id, tenant_id)
        if membership is None:
            raise LeadershipNotFoundError(
                "Ce compte ne porte pas ce grade sur ce groupe.",
                details={"account_id": str(account_id), "group_id": str(group_id)},
            )
        touched = await self._roles.revoke_group_role(
            membership_id=membership.id,
            role=role.value,
            group_id=group_id,
            now=self._clock(),
        )
        if touched == 0:
            raise LeadershipNotFoundError(
                "Aucune attribution active à révoquer.",
                details={"account_id": str(account_id), "group_id": str(group_id)},
            )
