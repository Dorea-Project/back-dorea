"""Use cases `SetReaction` / `RemoveReaction` (M8) — la réaction emoji.

**Pas de commentaires** (zéro modération, zéro drama) — mais une réaction, légère et expressive,
possible sur **toute** annonce (même « informer »). L'emoji doit venir de la **palette du type**
(pas de 🎉 sur un décès). Une réaction par personne, **changeable** ; se retirer la supprime.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from app.contexts.announcements.application.commands.engage_announcement import (
    ensure_in_audience,
    load_live,
)
from app.contexts.announcements.application.dtos import AnnouncementDTO
from app.contexts.announcements.application.mapping import to_announcement_dto
from app.contexts.announcements.application.ports import AudiencePort
from app.contexts.announcements.domain.aggregates import AnnouncementReaction
from app.contexts.announcements.domain.errors import AnnouncementNotFoundError
from app.contexts.announcements.domain.repositories import (
    AnnouncementReactionRepository,
    AnnouncementRepository,
)


class SetReaction:
    def __init__(
        self,
        announcements: AnnouncementRepository,
        reactions: AnnouncementReactionRepository,
        audience: AudiencePort,
        *,
        clock,
    ) -> None:
        self._announcements = announcements
        self._reactions = reactions
        self._audience = audience
        self._clock = clock

    async def execute(
        self, *, actor_account_id: UUID, announcement_id: UUID, emoji: str
    ) -> AnnouncementDTO:
        now = self._clock()
        announcement = await load_live(self._announcements, announcement_id, now)
        announcement.ensure_emoji_allowed(emoji)  # palette du type
        await ensure_in_audience(self._audience, announcement, actor_account_id)

        await self._reactions.set_for(
            AnnouncementReaction(
                id=uuid4(),
                announcement_id=announcement_id,
                account_id=actor_account_id,
                emoji=emoji,
                reacted_at=now,
            )
        )
        # On ne renvoie **pas** le décompte : il n'appartient pas au fil (voir GetConsolation).
        # Le clic ouvre un geste : l'`invitation` remonte dans la réponse.
        return to_announcement_dto(
            announcement, viewer_account_id=actor_account_id, my_reaction=emoji
        )


class RemoveReaction:
    def __init__(
        self,
        announcements: AnnouncementRepository,
        reactions: AnnouncementReactionRepository,
    ) -> None:
        self._announcements = announcements
        self._reactions = reactions

    async def execute(
        self, *, actor_account_id: UUID, announcement_id: UUID
    ) -> AnnouncementDTO:
        announcement = await self._announcements.get(announcement_id)
        if announcement is None:
            raise AnnouncementNotFoundError(
                "Annonce introuvable.", details={"announcement_id": str(announcement_id)}
            )
        await self._reactions.remove(announcement_id, actor_account_id)  # idempotent
        return to_announcement_dto(
            announcement, viewer_account_id=actor_account_id, my_reaction=None
        )
