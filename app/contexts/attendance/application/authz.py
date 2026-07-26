"""Autorisation de la présence — réutilise la portée sous-arbre des Groupes (M6 §6).

Marquer une présence = `RECORD_ATTENDANCE` sur le groupe de la rencontre (le `group_leader`
**et** le `leader_in_training` la portent). L'évaluation vit dans les Groupes (l'arbre y est).
"""

from __future__ import annotations

from uuid import UUID

from app.contexts.attendance.domain.aggregates import Gathering
from app.contexts.attendance.domain.errors import GatheringNotFoundError
from app.contexts.attendance.domain.repositories import GatheringRepository
from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.groups.application.group_lookup import load_group_in_tenant
from app.contexts.groups.domain.aggregates import Group
from app.contexts.groups.domain.repositories import GroupRepository
from app.contexts.iam.domain.permissions import Permission


async def load_gathering(gatherings: GatheringRepository, gathering_id: UUID) -> Gathering:
    gathering = await gatherings.get(gathering_id)
    if gathering is None:
        raise GatheringNotFoundError(
            "Rencontre introuvable.", details={"gathering_id": str(gathering_id)}
        )
    return gathering


async def authorize_on_gathering(
    *,
    gathering: Gathering,
    groups: GroupRepository,
    access: GroupAccessPolicy,
    actor_account_id: UUID,
) -> Group:
    """Charge le groupe de la rencontre et exige `RECORD_ATTENDANCE` (portée sous-arbre)."""
    group = await load_group_in_tenant(groups, gathering.group_id, gathering.tenant_id)
    await access.ensure_can(
        actor_account_id=actor_account_id, group=group, permission=Permission.RECORD_ATTENDANCE
    )
    return group
