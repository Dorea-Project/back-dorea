"""« Je suis passé le voir. » — l'émission d'un geste posé.

Le jumeau de `RaiseConcern`, et son inverse dans le temps : l'un déclare une intention qu'on se
donne, l'autre un acte déjà accompli. Ils partagent la preuve de consentement — `SPEAK_FOR_ANOTHER`
— parce que ce n'est pas la permission du sujet qu'on exige, c'est l'engagement de celui qui parle.

**Trois différences avec le signalement, et chacune est une décision.**

*Il ne résout aucun propriétaire.* Un geste n'ouvre pas de cas : il n'y a donc personne à qui
l'adresser. Poser la question ferait entrer un geste dans le plafond de débit d'un responsable,
alors qu'un geste est précisément ce qui n'a rien coûté à l'institution.

*Il n'a pas de contrepartie à écrire.* La confirmation dit `noted`, une fois, et rien de plus. Le
déclarant n'apprend pas si un cas existait — ce serait lui dire que la personne est en veille,
c'est-à-dire fuiter un cas à un membre. Il apprend seulement que c'est parti.

*Il ne se compte nulle part.* Aucun total ne remonte vers celui qui l'a posé, aucun écran ne le
range, aucune relance ne lui dira qu'il n'a rien déclaré ce mois-ci — ce serait dire le silence, et
le produit s'interdit de le dire. La contrepartie du geste est ailleurs, et elle est réelle :
personne ne rappellera Sondet pour rien.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from app.contexts.watch.application.intake import Intake
from app.contexts.watch.application.ports import NeutralizationStore, SignalStore
from app.contexts.watch.domain.errors import ConcernRefusedError, SelfGestureError
from app.contexts.watch.domain.facts import (
    ConsentProof,
    ConsentScope,
    Fact,
    FactKind,
    SubjectKind,
)
from app.contexts.watch.domain.gesture import GestureKind
from app.contexts.watch.domain.registry import COMPANION


@dataclass(frozen=True)
class GestureAcknowledged:
    """« Merci. » — **une seule fois**, et rien de plus.

    Ni compteur, ni récapitulatif, ni « c'est le 4ᵉ ce mois-ci ». Un geste qu'on félicite devient
    un geste qu'on pose pour être félicité."""

    message: str = "Merci."


class DeclareGesture:
    def __init__(
        self,
        intake: Intake,
        signals: SignalStore,
        exclusions: NeutralizationStore,
        *,
        clock,
        id_factory=uuid4,
    ) -> None:
        self._intake = intake
        self._signals = signals
        self._exclusions = exclusions
        self._clock = clock
        self._new_id = id_factory

    async def execute(
        self,
        *,
        actor_account_id: UUID,
        subject_account_id: UUID,
        tenant_id: UUID,
        gesture: GestureKind,
        source: str = COMPANION,
    ) -> GestureAcknowledged:
        now = self._clock()
        await self._guard(actor_account_id, subject_account_id, tenant_id)

        await self._intake.submit(
            Fact(
                fact_id=self._new_id(),
                tenant_id=tenant_id,
                occurred_at=now,
                recorded_at=now,
                source=source,
                kind=FactKind.GESTURE_DONE,
                subject_kind=SubjectKind.PERSON,
                subject_id=subject_account_id,
                # **Le geste, et rien du motif.** Aucune place pour « parce qu'il est malade » :
                # il n'y a pas de champ où l'écrire, et c'est la spécification.
                payload={"kind": gesture.value},
                consent=ConsentProof(
                    given_by=actor_account_id,
                    scope=ConsentScope.SPEAK_FOR_ANOTHER,
                    given_at=now,
                ),
            )
        )
        return GestureAcknowledged()

    async def _guard(self, actor: UUID, subject: UUID, tenant_id: UUID) -> None:
        if actor == subject:
            raise SelfGestureError(
                "Un geste se pose pour quelqu'un d'autre.",
                details={"kind": FactKind.GESTURE_DONE.value},
            )
        if subject in await self._exclusions.excluded_subject_ids(tenant_id):
            raise ConcernRefusedError(
                "Cette personne est retirée de la veille.", details={"reason": "excluded"}
            )
        if subject in await self._signals.do_not_contact_ids(tenant_id):
            raise ConcernRefusedError(
                "Cette personne a demandé qu'on cesse de la contacter.",
                details={"reason": "do_not_contact"},
            )
