"""Requête **publique** `GetCard` (M9-0) — ce que voit celui qui reçoit le lien (sans compte).

Le visage (qui invite : personne ou groupe) + l'église + le message + l'image + le lieu/géoloc.
Rien de sensible. Un lien expiré/révoqué renvoie la carte avec `active=False`.
"""

from __future__ import annotations

from app.contexts.mission.application.dtos import MissionCardDTO
from app.contexts.mission.application.ports import InviterDirectory
from app.contexts.mission.domain.enums import InviterKind
from app.contexts.mission.domain.errors import MissionLinkNotFoundError
from app.contexts.mission.domain.repositories import MissionLinkRepository


class GetCard:
    def __init__(
        self,
        links: MissionLinkRepository,
        directory: InviterDirectory,
        *,
        clock,
    ) -> None:
        self._links = links
        self._directory = directory
        self._clock = clock

    async def execute(self, *, code: str) -> MissionCardDTO:
        link = await self._links.get_by_code(code)
        if link is None:
            raise MissionLinkNotFoundError("Code d'invitation inconnu.")

        if link.inviter_kind is InviterKind.PERSON:
            label = await self._directory.person_label(link.inviter_account_id)
        else:
            label = await self._directory.group_label(link.inviter_group_id)
        church = await self._directory.church_label(link.tenant_id)

        return MissionCardDTO(
            inviter_label=label or "Un membre",
            inviter_kind=link.inviter_kind.value,
            church_label=church or "une église",
            message=link.message,
            media_urls=list(link.media_urls),
            place_label=link.place_label,
            latitude=link.latitude,
            longitude=link.longitude,
            active=link.is_active(self._clock()),
        )
