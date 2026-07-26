"""Use case `RevokeRole` — retrait ciblé d'une attribution de rôle (§5.6).

Autorité symétrique de l'attribution (Owner retire le staff, Admin retire l'équipe).
Garde-fou : on ne retire pas le **dernier** `group_leader` d'un groupe sans remplaçant
(`IAM_GROUP_LAST_LEADER_REMOVAL_BLOCKED`).
"""

from __future__ import annotations

from uuid import UUID

from app.contexts.iam.application.access_control import AccessControl
from app.contexts.iam.application.dtos import RevokeRoleResult
from app.contexts.iam.application.ports import MembershipLifecycleStore
from app.contexts.iam.domain.enums import RevocationReason, RoleCode
from app.contexts.iam.domain.errors import (
    GroupLastLeaderRemovalBlockedError,
    MembershipNotFoundError,
    RoleAssignmentNotFoundError,
    UnauthorizedScopeError,
)
from app.contexts.iam.domain.repositories import MembershipRepository
from app.contexts.iam.domain.role_authority import ROLE_AUTHORITY


class RevokeRole:
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
        role: RoleCode,
        group_id: UUID | None = None,
    ) -> RevokeRoleResult:
        required_permission = ROLE_AUTHORITY.get(role)
        if required_permission is None:
            # network_supervisor ne se retire pas par cette voie.
            raise UnauthorizedScopeError(
                "Ce rôle ne se révoque pas par cette opération.",
                details={"role": role.value},
            )

        await self._access.ensure(
            account_id=actor_account_id, tenant_id=tenant_id, permission=required_permission
        )

        target = await self._memberships.get_active(target_account_id, tenant_id)
        if target is None:
            raise MembershipNotFoundError(
                "Aucune appartenance active pour ce compte dans ce tenant.",
                details={"account_id": str(target_account_id), "tenant_id": str(tenant_id)},
            )

        assignment = next(
            (
                ra
                for ra in target.active_roles()
                if ra.role is role and ra.group_id == group_id
            ),
            None,
        )
        if assignment is None:
            raise RoleAssignmentNotFoundError(
                "Ce rôle n'est pas attribué (activement) à ce membre.",
                details={"role": role.value, "group_id": str(group_id) if group_id else None},
            )

        # Dernier responsable d'un groupe → retrait bloqué (garder ≥ 1).
        if role is RoleCode.GROUP_LEADER and group_id is not None:
            active = await self._memberships.count_active_group_leaders(tenant_id, group_id)
            if active <= 1:
                raise GroupLastLeaderRemovalBlockedError(
                    "Retrait du dernier responsable du groupe interdit (désigner un remplaçant).",
                    details={"group_id": str(group_id)},
                )

        await self._store.revoke_role(
            role_assignment_id=assignment.id,
            revoked_at=self._clock(),
            reason=RevocationReason.ADMIN_ACTION,
        )

        return RevokeRoleResult(
            membership_id=target.id, role=role.value, group_id=group_id
        )
