"""Use case `PromoteGroupToChurch` — church planting (M4 §7/§8, G-4).

Un groupe (typiquement un amas de cellules) **s'émancipe** en église autonome. Acte
**Plateforme (Dorea)** — gouverné, gardé au niveau de l'interface par le jeton de service.
Fait naître une église-fille (Tenant, `parent_id` = église-mère → filiation), un **Owner**
(Ownership `emancipation`), et **re-pointe** les membres du groupe (nouvelles Memberships,
non destructif). La cellule source est **clôturée** (elle est devenue église).
"""

from __future__ import annotations

from uuid import UUID, uuid4

from app.contexts.groups.application.dtos import ChurchPlantDTO
from app.contexts.groups.application.ports import ChurchPlantStore
from app.contexts.groups.domain.errors import (
    GroupAlreadyPromotedError,
    GroupNotFoundError,
    RequiresChurchMembershipError,
)
from app.contexts.groups.domain.repositories import (
    GroupMembershipRepository,
    GroupRepository,
)
from app.contexts.iam.domain.aggregates import Membership
from app.contexts.iam.domain.enums import MembershipStatus
from app.contexts.iam.domain.repositories import MembershipRepository
from app.contexts.tenant.domain.aggregates import Tenant
from app.contexts.tenant.domain.enums import OwnershipMode
from app.contexts.tenant.domain.ownership import Ownership


class PromoteGroupToChurch:
    def __init__(
        self,
        groups: GroupRepository,
        group_memberships: GroupMembershipRepository,
        church_memberships: MembershipRepository,
        store: ChurchPlantStore,
        *,
        platform_account_id: UUID,
        clock,
    ) -> None:
        self._groups = groups
        self._group_memberships = group_memberships
        self._church_memberships = church_memberships
        self._store = store
        self._platform_account_id = platform_account_id
        self._clock = clock

    async def execute(
        self, *, group_id: UUID, church_name: str, owner_account_id: UUID
    ) -> ChurchPlantDTO:
        group = await self._groups.get(group_id)
        if group is None:
            raise GroupNotFoundError("Groupe introuvable.", details={"group_id": str(group_id)})
        if not group.is_promotable:
            raise GroupAlreadyPromotedError(
                "Ce groupe est déjà promu ou clôturé.", details={"group_id": str(group_id)}
            )

        source_tenant_id = group.tenant_id
        # L'owner désigné doit être membre actif de l'église source.
        if await self._church_memberships.get_active(owner_account_id, source_tenant_id) is None:
            raise RequiresChurchMembershipError(
                "Le futur Owner doit être membre de l'église source.",
                details={"account_id": str(owner_account_id), "tenant_id": str(source_tenant_id)},
            )

        now = self._clock()
        new_tenant = Tenant(
            id=uuid4(),
            name=church_name,
            created_at=now,
            parent_id=source_tenant_id,  # filiation église-mère ↔ fille
        )
        ownership = Ownership(
            id=uuid4(),
            account_id=owner_account_id,
            tenant_id=new_tenant.id,
            mode=OwnershipMode.EMANCIPATION,
            started_at=now,
        )
        owner_membership = _confirmed(owner_account_id, new_tenant.id, now)

        # Re-pointe les membres du groupe (hors owner, déjà pourvu).
        member_ids = {
            gm.account_id
            for gm in await self._group_memberships.list_active_by_group(group_id)
        } - {owner_account_id}
        memberships = [owner_membership] + [
            _confirmed(account_id, new_tenant.id, now) for account_id in member_ids
        ]

        await self._store.plant(
            tenant=new_tenant,
            ownership=ownership,
            memberships=memberships,
            actor_account_id=self._platform_account_id,
        )
        group.mark_promoted()
        await self._groups.save(group)

        return ChurchPlantDTO(
            source_group_id=group_id,
            tenant_id=new_tenant.id,
            parent_tenant_id=source_tenant_id,
            owner_account_id=owner_account_id,
            owner_membership_id=owner_membership.id,
            member_count=len(memberships),
        )


def _confirmed(account_id: UUID, tenant_id: UUID, now) -> Membership:
    return Membership(
        id=uuid4(),
        account_id=account_id,
        tenant_id=tenant_id,
        status=MembershipStatus.CONFIRMED_MEMBER,  # congrégation fondatrice (bootstrap)
        last_transition_at=now,
        role_assignments=[],
    )
