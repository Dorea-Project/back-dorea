"""Requête `GetGroupTrend` — la tendance d'un groupe dans le temps (B7+).

Le dashboard est une **photo** ; la décision (multiplier / fusionner / soigner) a besoin de la
**dérivée**. On rejoue le calcul **pur** de l'état de marche à N dates passées (l'horloge reculée)
et on lit l'effectif réel à chacune : une sparkline `active` / `at_risk` qui révèle le
**momentum** : « cette cellule monte » vs « cette cellule fond ». Lecture seule.
"""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from app.contexts.attendance.application.dtos import GroupTrendDTO, TrendPointDTO
from app.contexts.attendance.application.pulse_service import (
    GroupPulseComputer,
    classify_effectif,
)
from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.groups.application.group_lookup import load_group_in_tenant
from app.contexts.groups.domain.repositories import GroupRepository
from app.contexts.iam.domain.permissions import Permission

_MAX_WEEKS = 26  # garde-fou : au plus ~6 mois d'historique par appel


class GetGroupTrend:
    def __init__(
        self,
        computer: GroupPulseComputer,
        groups: GroupRepository,
        access: GroupAccessPolicy,
        *,
        clock,
    ) -> None:
        self._computer = computer
        self._groups = groups
        self._access = access
        self._clock = clock

    async def execute(
        self, *, actor_account_id: UUID, tenant_id: UUID, group_id: UUID, weeks: int = 8
    ) -> GroupTrendDTO:
        group = await load_group_in_tenant(self._groups, group_id, tenant_id)
        await self._access.ensure_can(
            actor_account_id=actor_account_id,
            group=group,
            permission=Permission.VIEW_PASTORAL_ALERTS,
        )

        weeks = max(1, min(weeks, _MAX_WEEKS))
        now = self._clock()
        points: list[TrendPointDTO] = []
        for k in reversed(range(weeks)):  # du plus ancien au plus récent
            as_of = now - timedelta(weeks=k)
            pulses = await self._computer.compute(group=group, now=as_of)
            stats = classify_effectif(pulses)
            points.append(
                TrendPointDTO(
                    as_of=as_of,
                    roster_count=len(pulses),
                    active_count=stats.active,
                    at_risk_count=stats.at_risk,
                )
            )
        return GroupTrendDTO(group_id=group_id, points=points)
