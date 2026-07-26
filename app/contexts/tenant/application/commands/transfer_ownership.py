"""Use case `TransferOwnership` — succession du siège Owner (P6).

Acte **Plateforme** (mutation pastorale). Clôt la propriété active puis en ouvre une
nouvelle dans le **même** tenant, en une transaction. L'ancien Owner conserve son
`Account` (identité globale) ; seule la propriété change de main.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from app.contexts.iam.domain.repositories import MembershipRepository
from app.contexts.tenant.domain.enums import OwnershipMode
from app.contexts.tenant.domain.errors import NewOwnerNotEligibleError, TenantNotFoundError
from app.contexts.tenant.domain.ownership import Ownership
from app.contexts.tenant.domain.repositories import OwnershipRepository


class TransferOwnership:
    def __init__(
        self,
        ownership: OwnershipRepository,
        memberships: MembershipRepository,
        *,
        clock,
    ) -> None:
        self._ownership = ownership
        self._memberships = memberships
        self._clock = clock

    async def execute(self, *, tenant_id: UUID, new_owner_account_id: UUID) -> UUID:
        current = await self._ownership.get_active_for_tenant(tenant_id)
        if current is None:
            raise TenantNotFoundError("Aucune propriété active pour ce tenant.")

        # Valider le futur titulaire AVANT de clore l'ancien siège (acte
        # irréversible) : il doit être membre confirmé actif de CE tenant.
        membership = await self._memberships.get_active(new_owner_account_id, tenant_id)
        if membership is None or not membership.is_confirmed_member:
            raise NewOwnerNotEligibleError(
                "Le nouveau titulaire doit être un membre confirmé de cette église."
            )

        now = self._clock()
        # Clôturer l'ancienne AVANT d'ouvrir la nouvelle (invariant « 1 active / tenant »).
        await self._ownership.end_active(tenant_id, now)
        await self._ownership.add(
            Ownership(
                id=uuid4(),
                account_id=new_owner_account_id,
                tenant_id=tenant_id,
                mode=OwnershipMode.SUCCESSION,
                started_at=now,
            )
        )
        return new_owner_account_id
