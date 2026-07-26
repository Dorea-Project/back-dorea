"""Adaptateur `InviterDirectory` — le **visage** de la carte, lu dans iam / groups / tenant.

Mission → iam+groups+tenant (sens correct). Ne renvoie qu'un **libellé** (prénom / nom de groupe /
nom d'église), jamais autre chose.
"""

from __future__ import annotations

from uuid import UUID

from app.contexts.groups.infrastructure.persistence.repositories import SqlGroupRepository
from app.contexts.iam.infrastructure.persistence.repositories import SqlAlchemyAccountRepository
from app.contexts.mission.application.ports import InviterDirectory
from app.contexts.tenant.infrastructure.persistence.tenant_repo import SqlTenantRepository


class DirectoryAdapter(InviterDirectory):
    def __init__(
        self,
        accounts: SqlAlchemyAccountRepository,
        groups: SqlGroupRepository,
        tenants: SqlTenantRepository,
    ) -> None:
        self._accounts = accounts
        self._groups = groups
        self._tenants = tenants

    async def person_label(self, account_id: UUID) -> str | None:
        account = await self._accounts.get_by_id(account_id)
        if account is None:
            return None
        return account.first_name or "Un membre"

    async def group_label(self, group_id: UUID) -> str | None:
        group = await self._groups.get(group_id)
        return group.name if group is not None else None

    async def church_label(self, tenant_id: UUID) -> str | None:
        tenant = await self._tenants.get_by_id(tenant_id)
        return tenant.name if tenant is not None else None
