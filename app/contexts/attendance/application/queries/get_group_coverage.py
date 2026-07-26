"""Requête `GetGroupCoverage` (P1 — Fondation A) — le **calcul** de couverture d'un groupe.

Sur une fenêtre, dérive les occurrences attendues de la cadence et classe chacune en
saisie / acquittée / silencieuse. `silencieuse` = trou de veille ; `has_cadence=False` = veille
**aveugle** sur ce groupe. Ceci n'est que le calcul : l'émission d'alerte (« Béthel — 5 semaines
sans rencontre »), l'agrégation et l'escalade sont P2. L'autorisation est appliquée à la route.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.contexts.attendance.application.dtos import (
    CoverageOccurrenceDTO,
    GroupCoverageDTO,
)
from app.contexts.attendance.domain.cadence import (
    OccurrenceState,
    expected_occurrences,
    occurrence_state,
)
from app.contexts.attendance.domain.repositories import (
    CadenceAcknowledgementRepository,
    ChurchSuspensionRepository,
    GatheringRepository,
    GroupCadenceRepository,
)


class GetGroupCoverage:
    def __init__(
        self,
        cadences: GroupCadenceRepository,
        gatherings: GatheringRepository,
        acknowledgements: CadenceAcknowledgementRepository,
        suspensions: ChurchSuspensionRepository,
    ) -> None:
        self._cadences = cadences
        self._gatherings = gatherings
        self._acks = acknowledgements
        self._suspensions = suspensions

    async def execute(
        self, *, tenant_id: UUID, group_id: UUID, from_date: datetime, to_date: datetime
    ) -> GroupCoverageDTO:
        cadence = await self._cadences.get_active_by_group(group_id)
        if cadence is None:
            return GroupCoverageDTO(
                group_id=group_id,
                from_date=from_date,
                to_date=to_date,
                has_cadence=False,  # veille aveugle : aucun rythme déclaré
                expected_count=0,
                saisie_count=0,
                acquittee_count=0,
                silencieuse_count=0,
                occurrences=[],
            )

        occurrences = expected_occurrences(cadence, from_date, to_date)
        gathering_dates = [g.scheduled_at for g in await self._gatherings.list_by_group(group_id)]
        ack_dates = [a.occurrence_date for a in await self._acks.list_by_group(group_id)]
        suspensions = [
            (s.from_date, s.to_date)
            for s in await self._suspensions.list_active_by_tenant(tenant_id)
        ]

        rows: list[CoverageOccurrenceDTO] = []
        counts = {
            OccurrenceState.SAISIE: 0,
            OccurrenceState.ACQUITTEE: 0,
            OccurrenceState.SILENCIEUSE: 0,
        }
        for occ in occurrences:
            state = occurrence_state(
                occ,
                gathering_dates=gathering_dates,
                acknowledged_dates=ack_dates,
                suspensions=suspensions,
            )
            counts[state] += 1
            rows.append(CoverageOccurrenceDTO(occurrence_at=occ, state=state.value))

        return GroupCoverageDTO(
            group_id=group_id,
            from_date=from_date,
            to_date=to_date,
            has_cadence=True,
            expected_count=len(occurrences),
            saisie_count=counts[OccurrenceState.SAISIE],
            acquittee_count=counts[OccurrenceState.ACQUITTEE],
            silencieuse_count=counts[OccurrenceState.SILENCIEUSE],
            occurrences=rows,
        )
