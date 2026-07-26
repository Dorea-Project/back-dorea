"""Adaptateur `AudiencePort` — la portée sous-arbre, côté Groupes (Annonces → Groupes).

Renvoie tous les **ancêtres-ou-soi** des groupes actifs du membre, lus depuis le **chemin
matérialisé** (`/racine/.../cellule/`). Une annonce scopée à l'un de ces groupes atteint le membre.
"""

from __future__ import annotations

from uuid import UUID

from app.contexts.announcements.application.ports import AudiencePort
from app.contexts.groups.infrastructure.persistence.repositories import (
    SqlGroupMembershipRepository,
    SqlGroupRepository,
)


class GroupAudienceAdapter(AudiencePort):
    def __init__(
        self, group_memberships: SqlGroupMembershipRepository, groups: SqlGroupRepository
    ) -> None:
        self._group_memberships = group_memberships
        self._groups = groups

    async def covering_group_ids(
        self, *, account_id: UUID, tenant_id: UUID
    ) -> set[UUID]:
        memberships = await self._group_memberships.list_active_by_account_and_tenant(
            account_id, tenant_id
        )
        covering: set[UUID] = set()
        for m in memberships:
            group = await self._groups.get(m.group_id)
            if group is None:
                continue
            # Chemin `/a/b/c/` → {a, b, c} : tous les ancêtres-ou-soi de ce groupe.
            covering.update(UUID(seg) for seg in group.path.strip("/").split("/") if seg)
        return covering
