"""Use case `MultiplyCell` — la division cellulaire (M4 §2/§8, G-3).

Le cœur « organisme vivant » : une cellule enfante une **fille** (sœur reliée par lignée,
génération +1), on **déplace** les membres choisis (mère→fille), et on **promeut** un
nouveau responsable (typiquement le « Timothée ») en `group_leader` de la fille — le tout
atomiquement. Explicite (déclenché par l'humain) ; seule une cellule se multiplie.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from app.contexts.groups.application.dtos import MultiplicationDTO
from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.groups.application.group_lookup import load_group_in_tenant
from app.contexts.groups.application.ports import ChurchRoleStore
from app.contexts.groups.domain.enums import GroupType
from app.contexts.groups.domain.errors import (
    MemberNotInCellError,
    NotACellError,
    RequiresChurchMembershipError,
)
from app.contexts.groups.domain.membership import GroupMembership
from app.contexts.groups.domain.repositories import (
    GroupMembershipRepository,
    GroupRepository,
)
from app.contexts.iam.domain.enums import RoleCode
from app.contexts.iam.domain.repositories import MembershipRepository

MULTIPLY_THRESHOLD = 12  # effectif à partir duquel le système SUGGÈRE la multiplication


class MultiplyCell:
    def __init__(
        self,
        groups: GroupRepository,
        group_memberships: GroupMembershipRepository,
        church_memberships: MembershipRepository,
        roles: ChurchRoleStore,
        access: GroupAccessPolicy,
        *,
        clock,
    ) -> None:
        self._groups = groups
        self._group_memberships = group_memberships
        self._church_memberships = church_memberships
        self._roles = roles
        self._access = access
        self._clock = clock

    async def execute(
        self,
        *,
        actor_account_id: UUID,
        tenant_id: UUID,
        mother_group_id: UUID,
        daughter_name: str,
        new_leader_account_id: UUID,
        member_account_ids: list[UUID],
    ) -> MultiplicationDTO:
        mother = await load_group_in_tenant(self._groups, mother_group_id, tenant_id)
        if mother.type is not GroupType.CELLULE:
            raise NotACellError(
                "Seule une cellule se multiplie.",
                details={"group_id": str(mother_group_id), "type": mother.type.value},
            )
        await self._access.ensure_can_manage(actor_account_id=actor_account_id, group=mother)

        leader_membership = await self._church_memberships.get_active(
            new_leader_account_id, tenant_id
        )
        if leader_membership is None:
            raise RequiresChurchMembershipError(
                "Le futur responsable doit être membre de l'église.",
                details={"account_id": str(new_leader_account_id), "tenant_id": str(tenant_id)},
            )

        # Les membres à déplacer doivent appartenir à la mère (lecture préalable).
        movers = list(dict.fromkeys(member_account_ids))  # dédup, ordre préservé
        for acc in movers:
            if await self._group_memberships.get_active(acc, mother.id) is None:
                raise MemberNotInCellError(
                    "Ce membre n'appartient pas à la cellule-mère.",
                    details={"account_id": str(acc), "mother_group_id": str(mother.id)},
                )

        now = self._clock()
        daughter = mother.multiply(
            daughter_id=uuid4(),
            name=daughter_name,
            now=now,
            created_by_account_id=actor_account_id,
        )
        await self._groups.add(daughter)

        # Déplace chaque membre : quitte la mère, rejoint la fille.
        for acc in movers:
            await self._relocate(acc, mother.id, daughter, tenant_id, actor_account_id, now)
        # Le nouveau responsable rejoint aussi la fille (s'il n'était pas déjà déplacé).
        if new_leader_account_id not in movers:
            await self._relocate(
                new_leader_account_id, mother.id, daughter, tenant_id, actor_account_id, now
            )

        # Promotion : le nouveau responsable devient group_leader de la fille.
        await self._roles.add_group_role(
            membership_id=leader_membership.id,
            tenant_id=tenant_id,
            role=RoleCode.GROUP_LEADER.value,
            group_id=daughter.id,
            assigned_by_account_id=actor_account_id,
            now=now,
        )

        return MultiplicationDTO(
            mother_group_id=mother.id,
            daughter_group_id=daughter.id,
            daughter_name=daughter.name,
            generation=daughter.generation,
            moved_members=len(movers),
            new_leader_account_id=new_leader_account_id,
        )

    async def _relocate(self, account_id, mother_id, daughter, tenant_id, actor, now) -> None:
        current = await self._group_memberships.get_active(account_id, mother_id)
        if current is not None:
            current.leave(now=now)
            await self._group_memberships.save(current)
        await self._group_memberships.add(
            GroupMembership.join(
                id=uuid4(),
                group_id=daughter.id,
                account_id=account_id,
                tenant_id=tenant_id,
                now=now,
                joined_by_account_id=actor,
            )
        )
