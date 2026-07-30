"""Quand faudra-t-il regarder si cette personne a disparu — **le rythme du groupe le dit**.

Le silence ne peut pas entrer comme fait : c'est l'asymétrie fondatrice du produit. La seule façon
de le constater est donc de **poser une échéance au moment d'une parole**, et de la laisser tomber
plus tard. Reste à savoir *quand*, et c'est ici que ça se décide.

**En occurrences tenues, jamais en jours.** Trois semaines de silence dans une cellule
hebdomadaire et un trimestre dans une commission mensuelle ne disent pas la même chose. Le rythme
est une propriété **du groupe** — sa cadence déclarée — et l'échéance se pose à la N-ième
rencontre attendue après la dernière présence. Une cellule vivante détecte à J+10 ; une commission
mensuelle ne crie pas au silence après trois semaines normales.

**Pourquoi ce calcul vit ici et pas dans l'interpreter.** Un interpreter est pur : il ne lit ni
l'horloge, ni la cadence, ni les paramètres de l'église. La date est donc calculée **au moment de
la parole**, par la couche applicative, et voyage ensuite dans le fait — figée. C'est ce qui rend
le rejeu identique au direct : trois ans plus tard, le même fait rendra la même échéance, même si
le groupe a changé de rythme entre-temps.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from uuid import UUID

from app.contexts.attendance.domain.cadence import expected_occurrences
from app.contexts.attendance.domain.repositories import GroupCadenceRepository
from app.contexts.watch.application.referent_ports import WatchParameterRepository
from app.contexts.watch.domain.parameters import WatchParam

# Combien d'occurrences on est prêt à énumérer d'avance pour trouver la N-ième. Une cellule
# hebdomadaire tient largement dans l'année ; au-delà, il n'y a pas de cadence exploitable.
_HORIZON_DAYS = 400


class AbsenceRhythm(ABC):
    """Quand reposer le regard sur quelqu'un, d'après le rythme de son groupe."""

    @abstractmethod
    async def next_check_at(
        self, *, group_id: UUID, tenant_id: UUID, since: datetime
    ) -> datetime | None:
        """La date de la N-ième rencontre attendue après `since`, plus la marge de saisie.

        `None` quand le groupe n'a pas de cadence déclarée : sans rythme attendu, il n'y a pas
        d'occurrence à manquer — et on ne pose pas une échéance sur une intuition."""
        ...


class CadenceAbsenceRhythm(AbsenceRhythm):
    def __init__(
        self, cadences: GroupCadenceRepository, params: WatchParameterRepository
    ) -> None:
        self._cadences = cadences
        self._params = params

    async def next_check_at(
        self, *, group_id: UUID, tenant_id: UUID, since: datetime
    ) -> datetime | None:
        cadence = await self._cadences.get_active_by_group(group_id)
        if cadence is None:
            return None

        threshold = await self._params.get_int(
            tenant_id, WatchParam.ABSENCE_OCCURRENCES_THRESHOLD
        )
        grace = await self._params.get_int(tenant_id, WatchParam.ABSENCE_CHECK_GRACE_DAYS)

        horizon = since + timedelta(days=_HORIZON_DAYS)
        upcoming = [
            occurrence
            for occurrence in expected_occurrences(cadence, since, horizon)
            if occurrence > since
        ]
        if len(upcoming) < threshold:
            return None  # la cadence s'arrête avant : rien à attendre, donc rien à constater
        # La marge de saisie : sans elle, l'échéance tombe pendant que le responsable est encore
        # en train de remplir sa feuille de présence, et on ouvrirait un cas sur un retard de
        # saisie — le faux positif le plus vexant qui soit pour un bénévole.
        return upcoming[threshold - 1] + timedelta(days=grace)
