"""Use case (requête) : lire le statut d'appartenance et les rôles actifs.

Correspond à `GetMembershipStatus` + `GetActiveRoles` (M1 §8.2), combinés en une
seule lecture utile à l'app mobile Flutter.
"""

from __future__ import annotations

from uuid import UUID

from app.contexts.iam.application.dtos import MembershipStatusDTO
from app.contexts.iam.application.ports import OwnershipChecker
from app.contexts.iam.application.projections import to_membership_status_dto
from app.contexts.iam.domain.errors import MembershipNotFoundError
from app.contexts.iam.domain.repositories import MembershipRepository


class GetMembershipStatus:
    """Requête applicative — orchestre le dépôt et projette un DTO."""

    def __init__(
        self, memberships: MembershipRepository, ownership: OwnershipChecker
    ) -> None:
        self._memberships = memberships
        self._ownership = ownership

    async def execute(self, *, account_id: UUID, tenant_id: UUID) -> MembershipStatusDTO:
        membership = await self._memberships.get_active(account_id, tenant_id)
        if membership is None:
            raise MembershipNotFoundError(
                "Aucune appartenance active pour ce compte dans ce tenant.",
                details={"account_id": str(account_id), "tenant_id": str(tenant_id)},
            )

        is_owner = await self._ownership.is_active_owner(account_id, tenant_id)
        return to_membership_status_dto(membership, is_owner=is_owner)
