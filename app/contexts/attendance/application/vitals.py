"""Carte d'un groupe (« vitals ») — infos + réalités, partagée mobile & backoffice (B7)."""

from __future__ import annotations

from app.contexts.attendance.application.dtos import GroupVitalsDTO
from app.contexts.attendance.application.pulse_service import EffectifStats
from app.contexts.groups.application.commands.multiply_cell import MULTIPLY_THRESHOLD
from app.contexts.groups.domain.aggregates import Group
from app.contexts.groups.domain.enums import GroupType


def compute_group_vitals(group: Group, roster_count: int, stats: EffectifStats) -> GroupVitalsDTO:
    is_cell = group.type is GroupType.CELLULE
    return GroupVitalsDTO(
        group_id=group.id,
        name=group.name,
        type=group.type.value,
        status=group.status.value,
        generation=group.generation,
        roster_count=roster_count,
        active_count=stats.active,
        at_risk_count=stats.at_risk,
        shared_count=stats.shared,
        review_count=len(stats.review),
        # `ready_to_multiply` honnête (M7-3) : présents réels, cellule uniquement.
        ready_to_multiply=is_cell and stats.active >= MULTIPLY_THRESHOLD,
    )
