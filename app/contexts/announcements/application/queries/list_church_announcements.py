"""Requête `ListChurchAnnouncements` (M8) — la vue backoffice / **l'archive** de l'église.

Toutes les annonces de l'église (y compris **archivées** et expirées) + leurs retours. C'est la
mémoire : rien n'est détruit. Autorité église-entière (`PUBLISH_ANNOUNCEMENT` — Admin/Owner).

Ici le décompte des réactions **est** divulgué : ce n'est pas une vitrine mais un poste de
pilotage pastoral (« 40 réactions, 2 personnes à la veillée »). Le fil, lui, n'en montre rien.
"""

from __future__ import annotations

from uuid import UUID

from app.contexts.announcements.application.dtos import AnnouncementFeedDTO
from app.contexts.announcements.application.mapping import to_announcement_dto
from app.contexts.announcements.domain.repositories import (
    AnnouncementEngagementRepository,
    AnnouncementReactionRepository,
    AnnouncementRepository,
)
from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.iam.domain.permissions import Permission


class ListChurchAnnouncements:
    def __init__(
        self,
        announcements: AnnouncementRepository,
        engagements: AnnouncementEngagementRepository,
        reactions: AnnouncementReactionRepository,
        access: GroupAccessPolicy,
    ) -> None:
        self._announcements = announcements
        self._engagements = engagements
        self._reactions = reactions
        self._access = access

    async def execute(
        self, *, actor_account_id: UUID, tenant_id: UUID
    ) -> AnnouncementFeedDTO:
        await self._access.ensure_church_wide(
            actor_account_id=actor_account_id,
            tenant_id=tenant_id,
            permission=Permission.PUBLISH_ANNOUNCEMENT,
        )
        items = await self._announcements.list_by_tenant(tenant_id)
        items.sort(key=lambda a: a.published_at, reverse=True)

        ids = [a.id for a in items]
        counts = await self._engagements.counts_for_many(ids)
        engaged = await self._engagements.engaged_among(actor_account_id, ids)
        reaction_counts = await self._reactions.counts_by_emoji_for_many(ids)
        mine = await self._reactions.reactions_of_account_among(actor_account_id, ids)

        return AnnouncementFeedDTO(
            tenant_id=tenant_id,
            count=len(items),
            announcements=[
                to_announcement_dto(
                    a,
                    viewer_account_id=actor_account_id,
                    reveal_identity=True,  # pilotage pastoral : qui a publié, qui est concerné
                    engagement_count=counts.get(a.id, 0),
                    engaged=a.id in engaged,
                    reaction_counts=reaction_counts.get(a.id, {}),
                    my_reaction=mine.get(a.id),
                )
                for a in items
            ],
            next_before=None,  # l'archive n'est pas paginée (vue de pilotage)
        )
