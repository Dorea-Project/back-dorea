"""Use case `AppointGroupLeadership` — nomme le leadership d'un groupe (M4 §5, G-2).

Responsable (`group_leader`, cap 6) ou responsable-en-formation (« Timothée »).

Gestion de groupe : autorisée par la **portée sous-arbre** (`ensure_can_manage`). Le leadership
est posé comme **rôle IAM scopé** (via `ChurchRoleStore`). Prérequis : Membership église active.
Cap de 6 responsables (`group_leader`) par nœud ; le grade `in_training` n'est pas capé.
"""

from __future__ import annotations

from uuid import UUID

from app.contexts.groups.application.dtos import LeadershipDTO
from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.groups.application.group_lookup import load_group_in_tenant
from app.contexts.groups.application.ports import ChurchRoleStore
from app.contexts.groups.domain.errors import (
    DuplicateLeadershipError,
    LeaderCapExceededError,
    RequiresChurchMembershipError,
)
from app.contexts.groups.domain.leadership import GroupLeadershipGrade
from app.contexts.groups.domain.repositories import GroupRepository
from app.contexts.iam.domain.enums import RoleCode
from app.contexts.iam.domain.repositories import MembershipRepository

_LEADER_CAP = 6  # 1 à 6 responsables par nœud (M4 §5)


class AppointGroupLeadership:
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
    ) -> LeadershipDTO:
        group = await load_group_in_tenant(self._groups, group_id, tenant_id)
        role = grade.to_role()
        # Autorité par grade (« structurer depuis au-dessus », G-5) : responsable plein →
        # parent ; responsable-en-formation (Timothée) → nœud (mentorat).
        if role is RoleCode.GROUP_LEADER:
            await self._access.ensure_can_manage_structure(
                actor_account_id=actor_account_id, group=group
            )
        else:
            await self._access.ensure_can_manage(actor_account_id=actor_account_id, group=group)

        membership = await self._church_memberships.get_active(account_id, tenant_id)
        if membership is None:
            raise RequiresChurchMembershipError(
                "Ce compte doit d'abord être membre de l'église.",
                details={"account_id": str(account_id), "tenant_id": str(tenant_id)},
            )

        if any(
            ra.role is role and ra.group_id == group_id for ra in membership.active_roles()
        ):
            raise DuplicateLeadershipError(
                "Ce compte porte déjà ce grade sur ce groupe.",
                details={"account_id": str(account_id), "group_id": str(group_id)},
            )

        if role is RoleCode.GROUP_LEADER:
            active = await self._church_memberships.count_active_group_leaders(tenant_id, group_id)
            if active >= _LEADER_CAP:
                raise LeaderCapExceededError(
                    f"Cap de {_LEADER_CAP} responsables atteint sur ce groupe.",
                    details={"group_id": str(group_id)},
                )

        now = self._clock()
        assignment_id = await self._roles.add_group_role(
            membership_id=membership.id,
            tenant_id=tenant_id,
            role=role.value,
            group_id=group_id,
            assigned_by_account_id=actor_account_id,
            now=now,
        )
        return LeadershipDTO(
            group_id=group_id,
            account_id=account_id,
            grade=grade.value,
            role=role.value,
            role_assignment_id=assignment_id,
        )
