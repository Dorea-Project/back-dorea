"""Use case (requête) : lister toutes mes appartenances actives.

Point d'atterrissage **post-login** : l'app mobile ne connaît pas encore de
`tenant_id`. Cette requête répond « à quelles églises j'appartiens, avec quel
statut et quels rôles ? » à partir du seul acteur authentifié. Une liste **vide**
est une réponse valide (compte sans appartenance active), jamais une erreur.
"""

from __future__ import annotations

from uuid import UUID

from app.contexts.iam.application.dtos import MembershipStatusDTO
from app.contexts.iam.application.ports import OwnershipChecker
from app.contexts.iam.application.projections import to_membership_status_dto
from app.contexts.iam.domain.repositories import MembershipRepository


class GetMyMemberships:
    def __init__(
        self, memberships: MembershipRepository, ownership: OwnershipChecker
    ) -> None:
        self._memberships = memberships
        self._ownership = ownership

    async def execute(self, *, account_id: UUID) -> list[MembershipStatusDTO]:
        memberships = await self._memberships.list_active_by_account(account_id)
        dtos: list[MembershipStatusDTO] = []
        for m in memberships:
            is_owner = await self._ownership.is_active_owner(account_id, m.tenant_id)
            dtos.append(to_membership_status_dto(m, is_owner=is_owner))
        return dtos
