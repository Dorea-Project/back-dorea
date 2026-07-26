"""Adaptateur `GatheringRsvpPort` — côté **Présence** (Annonces → Présence, sens correct).

Le « je viens » d'une annonce *convoquer* liée à une rencontre est écrit comme un **RSVP** M6
(pré-signal), qui pré-remplit le roster — sans jamais écrire de présence réelle.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from app.contexts.announcements.application.ports import GatheringRsvpPort
from app.contexts.attendance.domain.rsvp import GatheringRsvp
from app.contexts.attendance.infrastructure.persistence.rsvp_repository import (
    SqlGatheringRsvpRepository,
)


class AttendanceRsvpAdapter(GatheringRsvpPort):
    def __init__(self, rsvps: SqlGatheringRsvpRepository) -> None:
        self._rsvps = rsvps

    async def set_rsvp(
        self, *, gathering_id: UUID, account_id: UUID, now: datetime
    ) -> None:
        await self._rsvps.set_for(
            GatheringRsvp(
                id=uuid4(), gathering_id=gathering_id, account_id=account_id, rsvp_at=now
            )
        )

    async def clear_rsvp(self, *, gathering_id: UUID, account_id: UUID) -> None:
        await self._rsvps.remove(gathering_id, account_id)
