"""Use case `CloseMembership` — clôture d'une appartenance avec **cascade** (§5.2/§5.5).

« Admin seul » (`CLOSE_MEMBERSHIP`). Clôturer révoque **tous** les rôles dans la même
transaction. Deux garde-fous protègent les invariants du tenant :
- on ne clôture pas le **dernier Owner** (I1) — succession = acte Plateforme ;
- on ne clôture pas un membre qui tient le **dernier `group_leader`** d'un groupe.

Le **Compte survit** : on ne ferme qu'une appartenance (ce qui rend possible
« qui a changé d'église », §1).
"""

from __future__ import annotations

from uuid import UUID

from app.contexts.iam.application.access_control import AccessControl
from app.contexts.iam.application.dtos import CloseMembershipResult
from app.contexts.iam.application.ports import MembershipLifecycleStore
from app.contexts.iam.domain.enums import MembershipClosureReason, MembershipStatus
from app.contexts.iam.domain.errors import (
    GroupLastLeaderRemovalBlockedError,
    LastOwnerRemovalBlockedError,
    MembershipNotFoundError,
)
from app.contexts.iam.domain.permissions import Permission
from app.contexts.iam.domain.repositories import MembershipRepository


class CloseMembership:
    def __init__(
        self,
        memberships: MembershipRepository,
        store: MembershipLifecycleStore,
        access: AccessControl,
        *,
        clock,
    ) -> None:
        self._memberships = memberships
        self._store = store
        self._access = access
        self._clock = clock

    async def execute(
        self,
        *,
        actor_account_id: UUID,
        tenant_id: UUID,
        target_account_id: UUID,
        closure_reason: MembershipClosureReason,
    ) -> CloseMembershipResult:
        await self._access.ensure(
            account_id=actor_account_id,
            tenant_id=tenant_id,
            permission=Permission.CLOSE_MEMBERSHIP,
        )

        target = await self._memberships.get_active(target_account_id, tenant_id)
        if target is None:
            raise MembershipNotFoundError(
                "Aucune appartenance active pour ce compte dans ce tenant.",
                details={"account_id": str(target_account_id), "tenant_id": str(tenant_id)},
            )

        # Garde I1 : on ne clôture jamais le dernier Owner (succession = Plateforme).
        if await self._access.is_owner(target_account_id, tenant_id):
            raise LastOwnerRemovalBlockedError(
                "On ne clôture pas l'Owner du tenant (succession via la Plateforme).",
                details={"tenant_id": str(tenant_id)},
            )

        # Garde : la cascade ne doit pas orphaner un groupe de son dernier responsable.
        for ra in target.list_group_leaders():
            if ra.group_id is not None:
                active = await self._memberships.count_active_group_leaders(tenant_id, ra.group_id)
                if active <= 1:
                    raise GroupLastLeaderRemovalBlockedError(
                        "La clôture retirerait le dernier responsable d'un groupe.",
                        details={"group_id": str(ra.group_id)},
                    )

        await self._store.close_membership(
            membership_id=target.id,
            closed_at=self._clock(),
            closure_reason=closure_reason,
        )

        return CloseMembershipResult(
            membership_id=target.id,
            status=MembershipStatus.CLOSED.value,
            closure_reason=closure_reason.value,
        )
