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
        if self._intake is None:
            return False

        # Un groupe sans cadence déclarée n'attend personne à une date connue : il n'y a rien à
        # armer. **Ce n'est pas une raison de ne rien écrire.**
        #
        # Le fait partait jadis à la poubelle dans ce cas, et la conséquence était silencieuse :
        # quelqu'un inscrit dans une cellule qui n'a pas déclaré son rythme n'existait nulle part
        # dans le journal. Le jour où la cellule déclarait enfin son rythme, un rejeu ne trouvait
        # rien à rejouer — la personne restait invisible pour toujours, sauf à venir d'elle-même.
        # C'est-à-dire exactement la population que ce fait a été créé pour couvrir : *celui qu'on
        # n'a jamais vu*.
        #
        # Le moteur a une règle pour ça, écrite et testée ailleurs : *un fait garde son sens
        # jusqu'à ce qu'on sache l'écrire*. Une source ne jette pas un fait parce qu'un détail
        # d'aval manque — elle dit ce qui a eu lieu, et l'engine fait ce qu'il peut. L'interpreter
        # sait déjà se taire sans la date (`arm_absence_watch`).
        due = (
            await self._rhythm.next_check_at(
                group_id=group_id, tenant_id=tenant_id, since=joined_at
            )
            if self._rhythm is not None
            else None
        )
        payload: dict = {"group_id": str(group_id)}
        if due is not None:
            payload["check_absence_at"] = due.isoformat()

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
                payload=payload,
            )
        )
        return result.accepted
