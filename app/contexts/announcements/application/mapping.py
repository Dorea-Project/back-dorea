"""Projection agrégat → DTO (partagée par les commandes et les requêtes).

Deux dé-identifications par défaut (l'Église parle, pas la personne ; pas de score au fil) :
- **l'identité** (`author_account_id`/`concerns_account_id`) n'est révélée que si `reveal_identity`
  (l'archive backoffice — redevabilité). Dans le fil, l'auteur est tu ; le sujet ne voit qu'un
  booléen **`concerns_me`** (« ceci vous concerne »), sans exposer son id à toute l'église.
- **`reaction_counts`** reste `None` sauf là où il console (`GetConsolation`) ou éclaire (pilotage).

`invitation` (« le clic n'absout pas ») : le geste plus coûteux vers lequel réagir ouvre — masqué
une fois qu'on s'est engagé (le geste est fait) ou si l'intention n'attend aucun engagement.
"""

from __future__ import annotations

from uuid import UUID

from app.contexts.announcements.application.dtos import AnnouncementDTO
from app.contexts.announcements.domain.aggregates import Announcement


def to_announcement_dto(
    a: Announcement,
    *,
    viewer_account_id: UUID | None = None,
    reveal_identity: bool = False,
    engagement_count: int = 0,
    engaged: bool = False,
    my_reaction: str | None = None,
    reaction_counts: dict[str, int] | None = None,  # None = non divulgué
    subject_account_ids: set[UUID] | None = None,  # les personnes nommées (rôle non divulgué)
) -> AnnouncementDTO:
    slots_remaining = max(0, a.slots_needed - engagement_count) if a.is_capped else None
    invitation = a.invitation()
    return AnnouncementDTO(
        id=a.id,
        tenant_id=a.tenant_id,
        scope=a.scope.value,
        category=a.category.value,
        tone=a.tone.value,
        intent=a.intent.value,
        scope_group_id=a.scope_group_id,
        title=a.title,
        body=a.body,
        media_urls=list(a.media_urls),
        author_account_id=a.author_account_id if reveal_identity else None,
        concerns_account_id=a.concerns_account_id if reveal_identity else None,
        concerns_me=viewer_account_id is not None
        and (
            a.concerns(viewer_account_id)
            or (subject_account_ids is not None and viewer_account_id in subject_account_ids)
        ),
        published_at=a.published_at,
        expires_at=a.expires_at,
        status=a.status.value,
        occurred_at=a.occurred_at,
        event_at=a.event_at,
        gathering_id=a.gathering_id,
        slots_needed=a.slots_needed,
        accepts_engagement=a.accepts_engagement,
        engagement_count=engagement_count,
        engaged=engaged,
        slots_remaining=slots_remaining,
        # Le clic ouvre un geste — tant qu'on ne l'a pas encore fait.
        invitation=invitation.value if (invitation is not None and not engaged) else None,
        allowed_emojis=list(a.allowed_emojis),
        my_reaction=my_reaction,
        reaction_counts=reaction_counts,
    )
