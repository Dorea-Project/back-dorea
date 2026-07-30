"""Requête `ListMySeekers` (M9-0) — le **fruit missionnaire**, privé à l'inviteur.

Les chercheurs que *j'ai* amenés + le signal des réactions légères (touché/édifié/Amen). C'est
**mon** suivi, pas un score public (anti-vitrine, cf. la consolation M8).
"""

from __future__ import annotations

from uuid import UUID

from app.contexts.mission.application.commands.accompany import to_seeker_dto
from app.contexts.mission.application.dtos import MySeekersDTO
from app.contexts.mission.domain.repositories import (
    MissionLinkRepository,
    MissionReactionRepository,
    SeekerRepository,
)
from app.contexts.watch.application.ports import SignalStore


class ListMySeekers:
    def __init__(
        self,
        links: MissionLinkRepository,
        seekers: SeekerRepository,
        reactions: MissionReactionRepository,
        signals: SignalStore | None = None,
    ) -> None:
        self._links = links
        self._seekers = seekers
        self._reactions = reactions
        self._signals = signals

    async def execute(
        self, *, actor_account_id: UUID, tenant_id: UUID
    ) -> MySeekersDTO:
        mine = await self._seekers.list_by_inviter_account(actor_account_id, tenant_id)
        mine.sort(key=lambda s: s.created_at, reverse=True)

        # **Une vue des cas, jamais une seconde liste.** Deux listes sur les mêmes personnes
        # finissent par se contredire, et l'inviteur ne sait plus laquelle croire. Une seule
        # requête pour toute la page — la provenance vient du chercheur, l'état vient du cas.
        cases: dict = {}
        if self._signals is not None:
            cases = await self._signals.cases_by_subjects(
                subject_ids=[s.person_account_id for s in mine], tenant_id=tenant_id
            )

        counts: dict[str, int] = {}
        link = await self._links.get_active_personal(actor_account_id, tenant_id)
        if link is not None:
            raw = await self._reactions.counts_by_kind(link.id)
            counts = {k.value: n for k, n in raw.items()}

        return MySeekersDTO(
            total=len(mine),
            seekers=[to_seeker_dto(s, cases.get(s.person_account_id)) for s in mine],
            reaction_counts=counts,
        )
