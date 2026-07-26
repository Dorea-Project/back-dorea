"""Use case : autorisation (`CanPerform`, M1 §8.2).

Garde transverse réutilisée par tous les contextes : charge l'appartenance
active de l'acteur dans le tenant, puis délègue la décision au service de
domaine. `ensure()` lève `IAM_UNAUTHORIZED_SCOPE` (spec §6) en cas de refus.
"""

from __future__ import annotations

from uuid import UUID

from app.contexts.iam.domain.errors import UnauthorizedScopeError
from app.contexts.iam.domain.permissions import Permission
from app.contexts.iam.domain.repositories import MembershipRepository
from app.contexts.iam.domain.services import AuthorizationService


class CheckPermission:
    def __init__(self, memberships: MembershipRepository) -> None:
        self._memberships = memberships

    async def execute(
        self,
        *,
        account_id: UUID,
        tenant_id: UUID,
        permission: Permission,
        group_id: UUID | None = None,
    ) -> bool:
        membership = await self._memberships.get_active(account_id, tenant_id)
        if membership is None:
            return False
        return AuthorizationService.can_perform(membership, permission, group_id=group_id)

    async def ensure(
        self,
        *,
        account_id: UUID,
        tenant_id: UUID,
        permission: Permission,
        group_id: UUID | None = None,
    ) -> None:
        allowed = await self.execute(
            account_id=account_id,
            tenant_id=tenant_id,
            permission=permission,
            group_id=group_id,
        )
        if not allowed:
            raise UnauthorizedScopeError(
                "Action non autorisée dans cette portée.",
                details={
                    "permission": permission.value,
                    "tenant_id": str(tenant_id),
                    "group_id": str(group_id) if group_id is not None else None,
                },
            )
