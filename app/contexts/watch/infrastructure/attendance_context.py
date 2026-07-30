"""Ce que la Présence répond quand une échéance d'absence tombe.

**On compte les rencontres tenues, jamais les semaines écoulées.** C'est toute la différence entre
un produit de soin et un détecteur d'inactivité : si la cellule ne s'est pas réunie pendant un
mois, personne n'a rien manqué, et personne ne doit apparaître comme absent. Le comptage porte donc
sur les rencontres qui ont **réellement eu lieu** — une rencontre non tenue n'existe pas dans cette
table, et le problème de l'acquittement se dissout au lieu d'être traité.

Le nombre est lu ici, une fois, au moment du tir, puis écrit dans le fait. Recompter au rejeu
donnerait un autre résultat dès qu'une saisie tardive arrive — et l'invariant de déterminisme
tomberait sans que rien ne le signale.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.attendance.application.absence_rhythm import AbsenceRhythm
from app.contexts.attendance.infrastructure.persistence.models import GatheringModel
from app.contexts.groups.infrastructure.persistence.models import GroupModel
from app.contexts.watch.application.check_context import CheckContext
from app.contexts.watch.application.interpreters.presence_recorded import (
    ABSENCE_WATCH_KIND,
)
from app.contexts.watch.application.referent_ports import WatchParameterRepository
from app.contexts.watch.domain.parameters import WatchParam


class AttendanceCheckContext(CheckContext):
    def __init__(
        self,
        session: AsyncSession,
        params: WatchParameterRepository,
        rhythm: AbsenceRhythm,
    ) -> None:
        self._session = session
        self._params = params
        self._rhythm = rhythm

    async def for_check(self, check) -> Mapping[str, Any]:
        if check.kind != ABSENCE_WATCH_KIND:
            return {}
        group_id, since = check.payload.get("group_id"), check.payload.get("since")
        if not group_id or not since:
            return {}

        group_uuid, since_at = UUID(str(group_id)), datetime.fromisoformat(str(since))
        occurrences = await self._held_between(
            group_uuid, check.tenant_id, since_at, check.due_at
        )
        threshold = await self._params.get_int(
            check.tenant_id, WatchParam.ABSENCE_OCCURRENCES_THRESHOLD
        )
        # La prochaine date où regarder si le seuil n'est pas atteint aujourd'hui. Sans elle, la
        # première échéance tombée serait la dernière, et le silence qui s'installe ensuite ne
        # serait constaté par personne.
        following = await self._rhythm.next_check_at(
            group_id=group_uuid, tenant_id=check.tenant_id, since=check.due_at
        )
        observed: dict[str, Any] = {
            "occurrences": occurrences,
            "threshold": threshold,
            "group_label": await self._label_of(group_uuid),
        }
        if following is not None:
            observed["next_check_at"] = following.isoformat()
        return observed

    async def _held_between(
        self, group_id: UUID, tenant_id: UUID, since: datetime, until: datetime
    ) -> int:
        """Combien de rencontres de ce groupe se sont **tenues** entre ces deux dates.

        La borne haute est l'échéance elle-même, pas l'heure de la passe : la marge de saisie y est
        déjà comprise, et compter jusqu'à « maintenant » rendrait le résultat dépendant de l'heure
        à laquelle le cron a tourné. Aucune horloge n'est lue ici."""
        stmt = select(func.count()).where(
            GatheringModel.tenant_id == tenant_id,
            GatheringModel.group_id == group_id,
            GatheringModel.scheduled_at > since,
            GatheringModel.scheduled_at <= until,
        )
        return int((await self._session.execute(stmt)).scalar_one())

    async def _label_of(self, group_id: UUID) -> str:
        """Le nom du groupe — pour que le responsable lise « trois rencontres **de la cellule
        Bethel** » et non un identifiant."""
        group = await self._session.get(GroupModel, group_id)
        return getattr(group, "name", "") or ""
