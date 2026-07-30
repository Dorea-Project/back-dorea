"""Les Groupes comme **source** du moteur de veille — ils émettent, ils ne décident pas.

Une seule chose à dire : *quelqu'un vient d'entrer dans ce groupe*. C'est ce qui permet au moteur
de regarder celui qui n'est **jamais** venu — sans ce fait, seule une présence arme le regard, et
le nouveau inscrit qu'on ne revoit pas reste invisible.

Comme la Présence, cette source joint au fait **la date à laquelle il faudra regarder**, calculée
d'après le rythme déclaré du groupe. L'interpreter reste pur : il ne lit ni l'horloge, ni la
cadence, et le rejeu rend exactement ce que le direct a rendu.

Best-effort, jamais bloquant : si le moteur n'est pas monté, l'adhésion se fait quand même.
"""

from __future__ import annotations

from datetime import datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from app.contexts.attendance.application.absence_rhythm import AbsenceRhythm
from app.contexts.watch.application.intake import Intake, warn_if_disconnected
from app.contexts.watch.domain.facts import Fact, FactKind, SubjectKind
from app.contexts.watch.domain.registry import GROUPS

_FACT_NAMESPACE = uuid5(NAMESPACE_URL, "dorea:watch:joined_group")


def fact_id_for(group_id: UUID, account_id: UUID) -> UUID:
    """Identité **dérivée** de (groupe, personne) : réinscrire quelqu'un ne rejoue rien.

    Une sortie puis une nouvelle entrée dans le même groupe ne réarme donc pas le regard — c'est
    volontaire : la personne est déjà suivie, et le rejeu du journal ne doit pas empiler."""
    return uuid5(_FACT_NAMESPACE, f"{group_id}:{account_id}")


class EmitJoinedGroupFact:
    def __init__(self, intake: Intake | None, rhythm: AbsenceRhythm | None = None) -> None:
        warn_if_disconnected("groups", intake)
        self._intake = intake
        self._rhythm = rhythm

    async def execute(
        self,
        *,
        account_id: UUID,
        tenant_id: UUID,
        group_id: UUID,
        joined_at: datetime,
        recorded_at: datetime,
    ) -> bool:
        if self._intake is None or self._rhythm is None:
            return False

        due = await self._rhythm.next_check_at(
            group_id=group_id, tenant_id=tenant_id, since=joined_at
        )
        if due is None:
            # Un groupe sans cadence déclarée n'attend personne à une date connue : il n'y a
            # rien à armer, et on ne pose pas d'échéance sur une intuition.
            return False

        result = await self._intake.submit(
            Fact(
                fact_id=fact_id_for(group_id, account_id),
                tenant_id=tenant_id,
                occurred_at=joined_at,  # la date de l'adhésion
                recorded_at=recorded_at,
                source=GROUPS,
                kind=FactKind.JOINED_GROUP,
                subject_kind=SubjectKind.PERSON,
                subject_id=account_id,
                payload={"group_id": str(group_id), "check_absence_at": due.isoformat()},
            )
        )
        return result.accepted
