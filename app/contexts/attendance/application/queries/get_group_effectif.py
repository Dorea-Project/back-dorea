"""Requête `GetGroupEffectif` — l'effectif réel (M7-1).

L'effectif **honnête** : les membres *vivants* (hors dormants et déménagés), le nombre de
partagés (Mme Richmond) et d'à-interpeller, et une liste de **candidats à revoir** — dormants
ou en absence **structurelle** (déménagement, gravité `structural`). Ce sont des **suggestions** :
le retrait / le passage `external_participant` reste un **acte pastoral** (M7 §4), jamais auto.
"""

from __future__ import annotations

from uuid import UUID

from app.contexts.attendance.application.dtos import GroupEffectifDTO, ReviewCandidateDTO
from app.contexts.attendance.application.pulse_service import (
    GroupPulseComputer,
    classify_effectif,
)
from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.groups.application.group_lookup import load_group_in_tenant
from app.contexts.groups.domain.repositories import GroupRepository
from app.contexts.iam.domain.permissions import Permission


class GetGroupEffectif:
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
        self, *, actor_account_id: UUID, tenant_id: UUID, group_id: UUID
    ) -> GroupEffectifDTO:
        group = await load_group_in_tenant(self._groups, group_id, tenant_id)
        await self._access.ensure_can(
            actor_account_id=actor_account_id,
            group=group,
            permission=Permission.VIEW_PASTORAL_ALERTS,
        )

        pulses = await self._computer.compute(group=group, now=self._clock())
        stats = classify_effectif(pulses)

        return GroupEffectifDTO(
            group_id=group_id,
            total_members=len(pulses),
            active_count=stats.active,
            at_risk_count=stats.at_risk,
            shared_count=stats.shared,
            review_candidates=[
                ReviewCandidateDTO(account_id=a, reason=r) for a, r in stats.review
            ],
        )
