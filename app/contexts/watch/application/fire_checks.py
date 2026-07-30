"""Le temps entre par le ledger — `FireDueChecks`.

C'est le dernier organe du moteur, et il est volontairement bête : il ne décide rien. Pour chaque
échéance arrivée à terme, il **soumet un fait `CHECK_FIRED` à l'intake**, exactement comme le
ferait n'importe quelle source. L'interprétation, l'arbitrage et l'écriture suivent le chemin
normal.

Pourquoi ce détour plutôt qu'un service qui « évalue les échéances » : un interpreter ne lit
jamais l'horloge. S'il le faisait, rejouer le ledger demain donnerait un autre résultat
qu'aujourd'hui, et l'invariant de déterminisme — celui sur lequel repose toute la reprojection —
tomberait sans bruit.

**Le garde anti-orage.** Si le cron ne tourne pas pendant trois jours, toutes les échéances dues
partent d'un coup : le responsable ouvre l'application sur cinquante lignes et n'ouvre plus rien
du tout. On en tire un nombre borné par passe, les plus anciennes d'abord ; le reste **reste dû**.
Rien n'est perdu, tout est étalé — la panne de cron devient un retard, pas une avalanche.

Et ce qui a été différé est **dit**, jamais tu : une passe qui affiche « 20 tirées » en taisant
les 180 restantes ressemble à une passe qui a tout traité.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import NAMESPACE_URL, UUID, uuid5

from app.contexts.watch.application.intake import Intake
from app.contexts.watch.application.ports import ScheduledCheckStore
from app.contexts.watch.application.referent_ports import WatchParameterRepository
from app.contexts.watch.domain.facts import Fact, FactKind, SubjectKind
from app.contexts.watch.domain.parameters import WatchParam
from app.contexts.watch.domain.registry import WATCH_SCHEDULER

_FACT_NAMESPACE = uuid5(NAMESPACE_URL, "dorea:watch:check_fired")


def fact_id_for(check_id: UUID) -> UUID:
    """Identité **dérivée** de l'échéance : une échéance ne peut tomber qu'une fois.

    C'est le contrôle de doublon de l'intake qui devient la protection contre les crons qui se
    chevauchent — pas une convention d'exploitation qu'on espère respectée."""
    return uuid5(_FACT_NAMESPACE, str(check_id))


@dataclass(frozen=True)
class FiredChecks:
    fired: int
    deferred: int  # dues mais retenues par le garde anti-orage — **elles reviendront**

    @property
    def was_capped(self) -> bool:
        return self.deferred > 0


class FireDueChecks:
    def __init__(
        self,
        checks: ScheduledCheckStore,
        intake: Intake,
        params: WatchParameterRepository,
        *,
        clock,
    ) -> None:
        self._checks = checks
        self._intake = intake
        self._params = params
        self._clock = clock

    async def execute(self, *, tenant_id: UUID) -> FiredChecks:
        now = self._clock()
        cap = await self._params.get_int(tenant_id, WatchParam.CHECK_BURST_CAP)
        due = await self._checks.due(tenant_id=tenant_id, now=now, limit=cap)

        for check in due:
            # Marquée tirée **avant** d'entrer : la ligne est déjà verrouillée par `due()`, et si
            # l'intake échoue, la transaction entière retombe. L'ordre inverse laissait une
            # fenêtre où le fait était au ledger sans que l'échéance soit close — la passe
            # suivante l'aurait retirée.
            await self._checks.mark_fired(check_id=check.id, at=now)
            await self._intake.submit(
                Fact(
                    # **Dérivé de l'échéance**, jamais tiré au hasard : c'est ce qui rend le
                    # contrôle de doublon de l'intake capable d'attraper quelque chose. Avec un
                    # identifiant neuf à chaque passe, deux crons qui se chevauchent écrivaient
                    # deux fois la même échéance et relançaient deux fois la même personne.
                    fact_id=fact_id_for(check.id),
                    tenant_id=tenant_id,
                    # `occurred_at` est la date d'**échéance**, pas celle de la passe : une
                    # panne de cron de trois jours ne doit pas décaler l'histoire de trois jours.
                    occurred_at=check.due_at,
                    recorded_at=now,
                    source=WATCH_SCHEDULER,
                    kind=FactKind.CHECK_FIRED,
                    subject_kind=SubjectKind.PERSON,
                    subject_id=check.subject_id,
                    payload={
                        # Ce que la pose savait voyage jusqu'au tir : le groupe, la cadence, la
                        # date de la dernière parole. L'interpreter reste pur.
                        **dict(check.payload),
                        "check_id": str(check.id),
                        "kind": check.kind,
                        # La raison de la programmation voyage jusqu'au fait : sans elle, le
                        # rappel arrive sans qu'on sache l'expliquer.
                        "reason": check.reason,
                    },
                )
            )

        remaining = await self._checks.pending_count(tenant_id=tenant_id, now=now)
        return FiredChecks(fired=len(due), deferred=remaining)
