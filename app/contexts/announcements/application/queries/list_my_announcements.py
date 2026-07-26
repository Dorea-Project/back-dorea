"""Requête `ListMyAnnouncements` (M8) — le **fil d'actualité** du membre.

Fusionne les **trois portées** : les annonces **Dorea** (plateforme), celles de son **église**, et
celles des **groupes dont il relève** (sous-arbre). Ne montre que les annonces **vivantes** (ni
archivées, ni expirées), plus récentes d'abord, paginées au curseur. Chaque carte porte sa couleur
(le type), ses compteurs de **réactions** + la mienne, et son **engagement** éventuel.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.contexts.announcements.application.dtos import AnnouncementFeedDTO
from app.contexts.announcements.application.mapping import to_announcement_dto
from app.contexts.announcements.application.ports import AudiencePort
from app.contexts.announcements.domain.errors import NotAChurchMemberError
from app.contexts.announcements.domain.repositories import (
    AnnouncementEngagementRepository,
    AnnouncementReactionRepository,
    AnnouncementRepository,
)
from app.contexts.iam.domain.repositories import MembershipRepository

_MAX_LIMIT = 50


class ListMyAnnouncements:
    def __init__(
        self,
        announcements: AnnouncementRepository,
        engagements: AnnouncementEngagementRepository,
        reactions: AnnouncementReactionRepository,
        audience: AudiencePort,
        memberships: MembershipRepository,
        *,
        clock,
    ) -> None:
        self._announcements = announcements
        self._engagements = engagements
        self._reactions = reactions
        self._audience = audience
        self._memberships = memberships
        self._clock = clock

    async def execute(
        self,
        *,
        actor_account_id: UUID,
        tenant_id: UUID,
        limit: int = 20,
        before: datetime | None = None,
    ) -> AnnouncementFeedDTO:
        # Isolation inter-église : on ne lit le fil d'une église que si l'on en est membre actif.
        if await self._memberships.get_active(actor_account_id, tenant_id) is None:
            raise NotAChurchMemberError(
                "Rejoignez d'abord cette église pour en voir le fil.",
                details={"tenant_id": str(tenant_id)},
            )
        limit = max(1, min(limit, _MAX_LIMIT))
        now = self._clock()
        covering = await self._audience.covering_group_ids(
            account_id=actor_account_id, tenant_id=tenant_id
        )
        # Le dépôt borne déjà à (plateforme + cette église) et au vivant ;
        # on filtre ici la portée groupe.
        candidates = await self._announcements.list_feed_candidates(
            tenant_id, now=now, before=before, limit=limit
        )
        visible = [a for a in candidates if a.reaches(covering)]

        ids = [a.id for a in visible]
        counts = await self._engagements.counts_for_many(ids)
        engaged = await self._engagements.engaged_among(actor_account_id, ids)
        # Pas de `counts_by_emoji_for_many` ici : le fil ne porte aucun score de réaction.
        mine = await self._reactions.reactions_of_account_among(actor_account_id, ids)

        return AnnouncementFeedDTO(
            tenant_id=tenant_id,
            count=len(visible),
            announcements=[
                to_announcement_dto(
                    a,
                    viewer_account_id=actor_account_id,  # pour « concerns_me » ; auteur tu
                    engagement_count=counts.get(a.id, 0),
                    engaged=a.id in engaged,
                    my_reaction=mine.get(a.id),  # reaction_counts reste None : non divulgué
                )
                for a in visible
            ],
            # Curseur : la plus ancienne page servie (None si le dépôt a rendu moins que demandé).
            next_before=candidates[-1].published_at if len(candidates) == limit else None,
        )
