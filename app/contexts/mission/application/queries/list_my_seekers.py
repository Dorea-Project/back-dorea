"""Requête `ListMySeekers` (M9-0) — le **fruit missionnaire**, privé à l'inviteur.

Les chercheurs que *j'ai* amenés + le signal des réactions légères (touché/édifié/Amen). C'est
**mon** suivi, pas un score public (anti-vitrine, cf. la consolation M8).
"""

from __future__ import annotations

from uuid import UUID

from app.contexts.mission.application.dtos import MySeekersDTO, SeekerDTO
from app.contexts.mission.domain.repositories import (
    MissionLinkRepository,
    MissionReactionRepository,
    SeekerRepository,
)


class ListMySeekers:
    def __init__(
        self,
        links: MissionLinkRepository,
        seekers: SeekerRepository,
        reactions: MissionReactionRepository,
    ) -> None:
        self._links = links
        self._seekers = seekers
        self._reactions = reactions

    async def execute(
        self, *, actor_account_id: UUID, tenant_id: UUID
    ) -> MySeekersDTO:
        mine = await self._seekers.list_by_inviter_account(actor_account_id, tenant_id)
        mine.sort(key=lambda s: s.created_at, reverse=True)

        counts: dict[str, int] = {}
        link = await self._links.get_active_personal(actor_account_id, tenant_id)
        if link is not None:
            raw = await self._reactions.counts_by_kind(link.id)
            counts = {k.value: n for k, n in raw.items()}

        return MySeekersDTO(
            total=len(mine),
            seekers=[
                SeekerDTO(
                    id=s.id,
                    name=s.name,
                    status=s.status.value,
                    created_at=s.created_at,
                    accompanied_by=s.accompanied_by_account_id,
                    accompanied_at=s.accompanied_at,
                )
                for s in mine
            ],
            reaction_counts=counts,
        )
