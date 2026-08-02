"""Quels groupes attendent des rencontres, et quand était la dernière qu'on leur connaisse.

Une seule requête par église : les cadences actives, jointes à la date de la dernière rencontre
saisie de chaque groupe. C'est tout ce dont la détection des groupes aveugles a besoin — elle fait
le reste avec la fonction pure `expected_occurrences`.

Le nom du groupe est joint parce qu'un défaut de couverture se lit : *« aucune rencontre saisie
pour la cellule Bethel »* est actionnable, un identifiant ne l'est pas.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.attendance.infrastructure.persistence.cadence_repository import _to_cadence
from app.contexts.attendance.infrastructure.persistence.models import (
    GatheringModel,
    GroupCadenceModel,
)
from app.contexts.groups.domain.enums import GroupStatus
from app.contexts.groups.domain.membership import GroupMembershipStatus
from app.contexts.groups.infrastructure.persistence.models import (
    GroupMembershipModel,
    GroupModel,
)
from app.contexts.watch.application.blind_groups import GroupWatchRhythm, RhythmlessGroup


class SqlGroupRhythms:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def groups_without_rhythm(self, *, tenant_id: UUID) -> list[RhythmlessGroup]:
        """Les groupes actifs **avec des membres** et **sans cadence active**.

        `watched_groups` part des cadences : elle ne peut pas, par construction, voir un groupe
        qui n'en a pas. C'est pourquoi cette requête part des **groupes**."""
        with_cadence = select(GroupCadenceModel.group_id).where(
            GroupCadenceModel.tenant_id == tenant_id,
            GroupCadenceModel.canceled_at.is_(None),
        )
        stmt = (
            select(
                GroupModel.id,
                GroupModel.name,
                func.count(GroupMembershipModel.id),
            )
            .join(
                GroupMembershipModel,
                (GroupMembershipModel.group_id == GroupModel.id)
                & (GroupMembershipModel.status == GroupMembershipStatus.ACTIVE.value),
            )
            .where(
                GroupModel.tenant_id == tenant_id,
                GroupModel.status == GroupStatus.ACTIVE.value,
                GroupModel.id.not_in(with_cadence),
            )
            .group_by(GroupModel.id, GroupModel.name)
        )
        return [
            RhythmlessGroup(
                group_id=group_id, label=name or "ce groupe", member_count=int(count)
            )
            for group_id, name, count in (await self._session.execute(stmt)).all()
        ]

    async def watched_groups(self, *, tenant_id: UUID) -> list[GroupWatchRhythm]:
        last_gathering = (
            select(
                GatheringModel.group_id.label("group_id"),
                func.max(GatheringModel.scheduled_at).label("last_at"),
            )
            .where(GatheringModel.tenant_id == tenant_id)
            .group_by(GatheringModel.group_id)
            .subquery()
        )
        stmt = (
            select(GroupCadenceModel, GroupModel.name, last_gathering.c.last_at)
            .outerjoin(GroupModel, GroupModel.id == GroupCadenceModel.group_id)
            .outerjoin(
                last_gathering, last_gathering.c.group_id == GroupCadenceModel.group_id
            )
            .where(
                GroupCadenceModel.tenant_id == tenant_id,
                GroupCadenceModel.canceled_at.is_(None),
            )
        )
        rows = (await self._session.execute(stmt)).all()
        return [
            GroupWatchRhythm(
                group_id=cadence.group_id,
                label=name or "ce groupe",
                cadence=_to_cadence(cadence),
                last_gathering_at=last_at,
            )
            for cadence, name, last_at in rows
        ]
