"""Requête `GetConsolation` (M8) — le décompte **remis à qui il console**.

Le retournement anti-vitrine : le « 32 personnes vous portent » ne s'affiche **nulle part** comme un
score sur le post (l'auteur ne récolte rien). Il est remis :
- au **sujet** de l'annonce (`concerns_account_id` — la famille en deuil, les parents) ;
- à l'**autorité pastorale église-entière**, pour voir la vérité (« 40 réactions, 2 visites »).

Personne d'autre. Le décompte existe, il ne se met pas en vitrine.
"""

from __future__ import annotations

from uuid import UUID

from app.contexts.announcements.application.dtos import ConsolationDTO
from app.contexts.announcements.domain.errors import AnnouncementNotFoundError
from app.contexts.announcements.domain.repositories import (
    AnnouncementEngagementRepository,
    AnnouncementReactionRepository,
    AnnouncementRepository,
)
from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.groups.domain.errors import UnauthorizedGroupActionError
from app.contexts.iam.domain.permissions import Permission


class GetConsolation:
    def __init__(
        self,
        announcements: AnnouncementRepository,
        reactions: AnnouncementReactionRepository,
        engagements: AnnouncementEngagementRepository,
        access: GroupAccessPolicy,
    ) -> None:
        self._announcements = announcements
        self._reactions = reactions
        self._engagements = engagements
        self._access = access

    async def execute(
        self, *, actor_account_id: UUID, announcement_id: UUID
    ) -> ConsolationDTO:
        announcement = await self._announcements.get(announcement_id)
        if announcement is None:
            raise AnnouncementNotFoundError(
                "Annonce introuvable.", details={"announcement_id": str(announcement_id)}
            )
        if not announcement.concerns(actor_account_id):
            await self._ensure_pastoral(announcement, actor_account_id)

        counts = await self._reactions.counts_by_emoji(announcement_id)
        return ConsolationDTO(
            announcement_id=announcement_id,
            title=announcement.title,
            total=sum(counts.values()),
            reaction_counts=counts,
            engagement_count=await self._engagements.count_for(announcement_id),
        )

    async def _ensure_pastoral(self, announcement, actor_account_id: UUID) -> None:
        """Ni le sujet, ni un pasteur → personne ne voit le décompte (surtout pas l'auteur)."""
        if announcement.tenant_id is None:
            raise UnauthorizedGroupActionError(
                "Le retour d'une annonce Dorea n'est pas exposé aux églises.",
                details={"announcement_id": str(announcement.id)},
            )
        await self._access.ensure_church_wide(
            actor_account_id=actor_account_id,
            tenant_id=announcement.tenant_id,
            permission=Permission.VIEW_PASTORAL_ALERTS,
        )
