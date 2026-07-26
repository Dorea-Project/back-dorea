"""Use cases `EngageAnnouncement` / `WithdrawEngagement` (M8) — l'engagement structurant.

Le membre pose un **choix** (je viens / je sers / je porte) — pas un accusé de lecture. Il doit être
dans la **portée**, l'annonce **vivante** (ni archivée ni expirée), et l'intention accepter un
engagement (« informer » n'en accepte pas — mais les réactions, si). Une mobilisation refuse une
réponse de trop ; se retirer libère la place. Idempotent.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from app.contexts.announcements.application.dtos import AnnouncementDTO
from app.contexts.announcements.application.mapping import to_announcement_dto
from app.contexts.announcements.application.ports import AudiencePort, GatheringRsvpPort
from app.contexts.announcements.domain.aggregates import Announcement, AnnouncementEngagement
from app.contexts.announcements.domain.enums import AnnouncementIntent, AnnouncementScope
from app.contexts.announcements.domain.errors import (
    AnnouncementClosedError,
    AnnouncementNotFoundError,
    MobilizationFullError,
    NotInAudienceError,
    ResponsesNotAcceptedError,
)
from app.contexts.announcements.domain.repositories import (
    AnnouncementEngagementRepository,
    AnnouncementRepository,
)


async def load_live(
    announcements: AnnouncementRepository, announcement_id: UUID, now
) -> Announcement:
    announcement = await announcements.get(announcement_id)
    if announcement is None:
        raise AnnouncementNotFoundError(
            "Annonce introuvable.", details={"announcement_id": str(announcement_id)}
        )
    if not announcement.is_live(now):
        raise AnnouncementClosedError(
            "Cette annonce est archivée ou expirée.",
            details={"announcement_id": str(announcement_id)},
        )
    return announcement


async def ensure_in_audience(
    audience: AudiencePort, announcement: Announcement, account_id: UUID
) -> None:
    """Plateforme / église-entière atteignent tout le monde ; un groupe borne à son sous-arbre."""
    if announcement.scope is not AnnouncementScope.GROUP:
        return  # rien à résoudre (et une annonce plateforme n'a pas de tenant)
    covering = await audience.covering_group_ids(
        account_id=account_id, tenant_id=announcement.tenant_id
    )
    if not announcement.reaches(covering):
        raise NotInAudienceError(
            "Vous n'êtes pas dans la portée de cette annonce.",
            details={"announcement_id": str(announcement.id)},
        )


class EngageAnnouncement:
    def __init__(
        self,
        announcements: AnnouncementRepository,
        engagements: AnnouncementEngagementRepository,
        audience: AudiencePort,
        *,
        clock,
        rsvp: GatheringRsvpPort | None = None,
    ) -> None:
        self._announcements = announcements
        self._engagements = engagements
        self._audience = audience
        self._clock = clock
        self._rsvp = rsvp

    async def execute(
        self, *, actor_account_id: UUID, announcement_id: UUID
    ) -> AnnouncementDTO:
        now = self._clock()
        announcement = await load_live(self._announcements, announcement_id, now)
        if not announcement.accepts_engagement:
            raise ResponsesNotAcceptedError(
                "Cette annonce n'attend pas d'engagement.",
                details={"intent": announcement.intent.value},
            )
        await ensure_in_audience(self._audience, announcement, actor_account_id)

        existing = await self._engagements.get(announcement_id, actor_account_id)
        if existing is None:
            await self._ensure_slot_available(announcement)
            await self._engagements.add(
                AnnouncementEngagement(
                    id=uuid4(),
                    announcement_id=announcement_id,
                    account_id=actor_account_id,
                    responded_at=now,
                )
            )
            # Convoquer une rencontre → le « je viens » pré-remplit la présence attendue (M6).
            if (
                self._rsvp is not None
                and announcement.intent is AnnouncementIntent.CONVENE
                and announcement.gathering_id is not None
            ):
                await self._rsvp.set_rsvp(
                    gathering_id=announcement.gathering_id,
                    account_id=actor_account_id,
                    now=now,
                )
        count = await self._engagements.count_for(announcement_id)
        return to_announcement_dto(
            announcement, viewer_account_id=actor_account_id,
            engagement_count=count, engaged=True,
        )

    async def _ensure_slot_available(self, announcement: Announcement) -> None:
        # Une mobilisation sans plafond (la veillée) ne se remplit jamais.
        if announcement.intent is not AnnouncementIntent.MOBILIZE or not announcement.is_capped:
            return
        count = await self._engagements.count_for(announcement.id)
        if count >= announcement.slots_needed:
            raise MobilizationFullError(
                "Toutes les places sont prises.",
                details={"announcement_id": str(announcement.id)},
            )


class WithdrawEngagement:
    def __init__(
        self,
        announcements: AnnouncementRepository,
        engagements: AnnouncementEngagementRepository,
        *,
        rsvp: GatheringRsvpPort | None = None,
    ) -> None:
        self._announcements = announcements
        self._engagements = engagements
        self._rsvp = rsvp

    async def execute(
        self, *, actor_account_id: UUID, announcement_id: UUID
    ) -> AnnouncementDTO:
        announcement = await self._announcements.get(announcement_id)
        if announcement is None:
            raise AnnouncementNotFoundError(
                "Annonce introuvable.", details={"announcement_id": str(announcement_id)}
            )
        await self._engagements.remove(announcement_id, actor_account_id)  # idempotent
        # Se rétracter retire aussi le « je viens » de la rencontre liée.
        if self._rsvp is not None and announcement.gathering_id is not None:
            await self._rsvp.clear_rsvp(
                gathering_id=announcement.gathering_id, account_id=actor_account_id
            )
        count = await self._engagements.count_for(announcement_id)
        return to_announcement_dto(
            announcement, viewer_account_id=actor_account_id,
            engagement_count=count, engaged=False,
        )
