"""Requête `GetMultiplicationTree` — l'arbre de multiplication (B7+).

La vision cellulaire *c'est* la reproduction (G-3) : une cellule en enfante d'autres
(`multiplied_from_id`, `generation`). Cette requête rend la **forêt de reproduction** visible et
attache à chaque nœud ses **vitals** (effectif réel, à-risque, prête à multiplier). Elle révèle la
**fertilité** : quelles cellules se reproduisent, lesquelles restent stériles, la santé par
génération. Autorité **église-entière** (comme le dashboard). Lecture seule.
"""

from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from app.contexts.attendance.application.dtos import (
    LineageNodeDTO,
    MultiplicationTreeDTO,
)
from app.contexts.attendance.application.pulse_service import GroupPulseComputer, classify_effectif
from app.contexts.attendance.application.vitals import compute_group_vitals
from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.groups.domain.aggregates import Group
from app.contexts.groups.domain.enums import GroupType
from app.contexts.groups.domain.repositories import GroupMembershipRepository, GroupRepository
from app.contexts.iam.domain.permissions import Permission


class GetMultiplicationTree:
    def __init__(
        self,
        computer: GroupPulseComputer,
        groups: GroupRepository,
        group_memberships: GroupMembershipRepository,
        access: GroupAccessPolicy,
        *,
        clock,
    ) -> None:
        self._computer = computer
        self._groups = groups
        self._group_memberships = group_memberships
        self._access = access
        self._clock = clock

    async def execute(self, *, actor_account_id: UUID, tenant_id: UUID) -> MultiplicationTreeDTO:
        await self._access.ensure_church_wide(
            actor_account_id=actor_account_id,
            tenant_id=tenant_id,
            permission=Permission.VIEW_PASTORAL_ALERTS,
        )

        cells = [
            g
            for g in await self._groups.list_active_by_tenant(tenant_id)
            if g.type is GroupType.CELLULE
        ]
        now = self._clock()
        vitals_by_id = {}
        for g in cells:
            roster = await self._group_memberships.list_active_by_group(g.id)
            pulses = await self._computer.compute(group=g, now=now)
            vitals_by_id[g.id] = compute_group_vitals(g, len(roster), classify_effectif(pulses))

        ids = {g.id for g in cells}
        children_of: dict[UUID, list[Group]] = defaultdict(list)
        roots: list[Group] = []
        for g in cells:
            mother = g.multiplied_from_id
            # Racine = sans mère, ou mère hors périmètre actif (clôturée → sous-arbre visible).
            if mother is not None and mother in ids:
                children_of[mother].append(g)
            else:
                roots.append(g)

        def build(g: Group) -> LineageNodeDTO:
            kids = sorted(children_of[g.id], key=lambda c: c.name)
            return LineageNodeDTO(vitals=vitals_by_id[g.id], children=[build(c) for c in kids])

        return MultiplicationTreeDTO(
            tenant_id=tenant_id,
            cells_count=len(cells),
            max_generation=max((g.generation for g in cells), default=0),
            roots=[build(g) for g in sorted(roots, key=lambda g: g.name)],
        )
