"""Autorisation à **deux étages** (gouvernance au-dessus du RBAC).

```
Acteur autorisé sur un tenant pour une permission :
  1. Owner ACTIF du tenant (table tenant_ownerships) ?  → OUI = tout pouvoir
  2. Sinon → sa Membership → RBAC borné par la propriété (rôles + portée)
```

La propriété (Owner) n'est **plus un rôle** : c'est une relation de gouvernance
vérifiée en premier. Le RBAC (`AuthorizationService`) ne gère que les rôles
fonctionnels (pasteur, admin, responsable…).
"""

from __future__ import annotations

from uuid import UUID

from app.contexts.iam.application.ports import OwnershipChecker
from app.contexts.iam.domain.errors import UnauthorizedScopeError
from app.contexts.iam.domain.permissions import Permission
from app.contexts.iam.domain.repositories import MembershipRepository
from app.contexts.iam.domain.services import AuthorizationService


class AccessControl:
    def __init__(self, ownership: OwnershipChecker, memberships: MembershipRepository) -> None:
        self._ownership = ownership
        self._memberships = memberships

    async def is_owner(self, account_id: UUID, tenant_id: UUID) -> bool:
        return await self._ownership.is_active_owner(account_id, tenant_id)

    async def ensure(
        self,
        *,
        account_id: UUID,
        tenant_id: UUID,
        permission: Permission,
        group_id: UUID | None = None,
    ) -> None:
        """Autorise, sinon lève `UnauthorizedScopeError`."""
        if await self._ownership.is_active_owner(account_id, tenant_id):
            return  # 1ᵉʳ étage : l'Owner peut tout, sans portée.

        membership = await self._memberships.get_active(account_id, tenant_id)
        if membership is None or not AuthorizationService.can_perform(
            membership, permission, group_id=group_id
        ):
            raise UnauthorizedScopeError(
                "Droit insuffisant dans ce tenant.",
                details={"tenant_id": str(tenant_id), "permission": permission.value},
            )
