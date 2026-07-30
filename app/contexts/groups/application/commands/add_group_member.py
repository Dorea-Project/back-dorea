"""Use case `AddGroupMember` — rattache un compte à un groupe (M4 §6, G-1).

Managé : un responsable scopé / Admin / Owner ajoute un membre (autorisation par
sous-arbre, `GroupAccessPolicy`). **Prérequis** : le compte a une **Membership église
active** dans le tenant du groupe (sinon refus) — le contexte Groupes n'enrôle pas lui-même.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from app.contexts.groups.application.dtos import GroupMemberDTO
from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.groups.application.group_lookup import load_group_in_tenant
from app.contexts.groups.application.watch_facts import EmitJoinedGroupFact
from app.contexts.groups.domain.errors import (
    DuplicateGroupMembershipError,
    RequiresChurchMembershipError,
)
from app.contexts.groups.domain.membership import GroupMembership
from app.contexts.groups.domain.repositories import (
    GroupMembershipRepository,
    GroupRepository,
)
from app.contexts.iam.domain.repositories import MembershipRepository


class AddGroupMember:
    def __init__(
        self,
        groups: GroupRepository,
        group_memberships: GroupMembershipRepository,
        church_memberships: MembershipRepository,
        access: GroupAccessPolicy,
        joined: EmitJoinedGroupFact | None = None,
        *,
        clock,
    ) -> None:
        self._groups = groups
        self._group_memberships = group_memberships
        self._church_memberships = church_memberships
        self._access = access
        # Les Groupes sont une **source** du moteur : entrer dans un groupe arme le regard, et
        # c'est le seul moyen de voir celui qui ne viendra jamais.
        self._joined = joined
        self._clock = clock

    async def execute(
        self, *, actor_account_id: UUID, tenant_id: UUID, group_id: UUID, account_id: UUID
    ) -> GroupMemberDTO:
        group = await load_group_in_tenant(self._groups, group_id, tenant_id)
        await self._access.ensure_can_manage(actor_account_id=actor_account_id, group=group)

        # Prérequis : appartenance à l'église (jamais créée ici — frontière de contexte).
        if await self._church_memberships.get_active(account_id, tenant_id) is None:
            raise RequiresChurchMembershipError(
                "Ce compte doit d'abord être membre de l'église.",
                details={"account_id": str(account_id), "tenant_id": str(tenant_id)},
            )

        if await self._group_memberships.get_active(account_id, group_id) is not None:
            raise DuplicateGroupMembershipError(
                "Ce compte est déjà membre de ce groupe.",
                details={"account_id": str(account_id), "group_id": str(group_id)},
            )

        now = self._clock()
        membership = GroupMembership.join(
            id=uuid4(),
            group_id=group_id,
            account_id=account_id,
            tenant_id=tenant_id,
            now=now,
            joined_by_account_id=actor_account_id,
        )
        await self._group_memberships.add(membership)
        if self._joined is not None:
            # Best-effort : le moteur ne bloque jamais une adhésion.
            await self._joined.execute(
                account_id=account_id,
                tenant_id=tenant_id,
                group_id=group_id,
                joined_at=now,
                recorded_at=now,
            )
        return GroupMemberDTO(
            group_id=group_id,
            account_id=account_id,
            status=membership.status.value,
            joined_at=now,
        )
