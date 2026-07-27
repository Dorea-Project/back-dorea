"""« Je m'en occupe cette semaine. » — l'émission d'un signalement par un tiers.

**La formulation est la spécification.** Deux libellés étaient possibles, et ils ne déclarent pas
la même chose :

- « Je le sens loin » déclare quelque chose **sur la personne**. Ça glisse vers le diagnostic, et
  conservé, ça fait une fiche.
- « Je m'en occupe » déclare quelque chose **sur soi**. Aucun risque : il n'y a rien à écrire sur
  la personne.

La seconde est retenue : elle est plus honnête sur ce qui se passe réellement, et elle règle le
problème du diagnostic **par construction**. C'est aussi pourquoi ce service n'accepte aucun
texte libre : il n'y a pas de champ où l'écrire.

Trois refus, et un seul est une politesse — les deux autres sont des paroles qu'aucune bonne
intention ne reprend : la personne s'est retirée de la veille, ou a demandé qu'on cesse.

Le propriétaire du cas est résolu **ici**, à l'émission, parce que les interpreters sont purs.
S'il est nul, on émet quand même : perdre l'inquiétude parce que l'église n'a configuré personne
serait exactement le faux silence que le produit existe pour empêcher — et ce trou-là est déjà
consigné par `ResolveSignalOwner`.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from app.contexts.watch.application.intake import Intake
from app.contexts.watch.application.ports import NeutralizationStore, SignalStore
from app.contexts.watch.application.referent_resolution import ResolveSignalOwner
from app.contexts.watch.domain.concern import Nuance
from app.contexts.watch.domain.errors import ConcernRefusedError, SelfConcernError
from app.contexts.watch.domain.facts import (
    ConsentProof,
    ConsentScope,
    Fact,
    FactKind,
    SubjectKind,
)
from app.contexts.watch.domain.registry import WATCH_UI


@dataclass(frozen=True)
class ConcernAcknowledged:
    """« Noté. » — **une seule fois**, et rien de plus.

    Pas de confirmation détaillée, pas de récapitulatif de ce qui a été signalé : l'émetteur n'a
    pas besoin d'une preuve, il a besoin de savoir que c'est parti. Et surtout, la personne
    concernée n'apprendra jamais rien — aucune notification ne part vers elle."""

    message: str = "Noté."
    opened: bool = True


class RaiseConcern:
    def __init__(
        self,
        intake: Intake,
        owners: ResolveSignalOwner,
        signals: SignalStore,
        exclusions: NeutralizationStore,
        *,
        clock,
        id_factory=uuid4,
    ) -> None:
        self._intake = intake
        self._owners = owners
        self._signals = signals
        self._exclusions = exclusions
        self._clock = clock
        self._new_id = id_factory

    async def execute(
        self,
        *,
        emitter_account_id: UUID,
        subject_account_id: UUID,
        tenant_id: UUID,
        nuance: Nuance | None = None,
        source: str = WATCH_UI,
    ) -> ConcernAcknowledged:
        now = self._clock()
        await self._guard(emitter_account_id, subject_account_id, tenant_id)

        owner = await self._owners.execute(
            person_id=subject_account_id, tenant_id=tenant_id, at=now
        )
        payload: dict[str, str] = {}
        if owner is not None:
            payload["owner_account_id"] = str(owner.account_id)
        if nuance is not None:
            payload["nuance"] = nuance.value

        result = await self._intake.submit(
            Fact(
                fact_id=self._new_id(),
                tenant_id=tenant_id,
                occurred_at=now,
                recorded_at=now,
                source=source,
                kind=FactKind.THIRD_PARTY_CONCERN,
                subject_kind=SubjectKind.PERSON,
                subject_id=subject_account_id,
                payload=payload,
                # L'identité du déclarant sert **à l'intake** — le fait exige une preuve de
                # consentement à porter le souci d'autrui — puis elle n'est plus jointe à rien.
                # Aucune projection ne la relit : `ThirdPartyConcernV1` n'en tire qu'un booléen.
                consent=ConsentProof(
                    given_by=emitter_account_id,
                    scope=ConsentScope.SPEAK_FOR_ANOTHER,
                    given_at=now,
                ),
            )
        )
        return ConcernAcknowledged(opened=result.accepted)

    async def _guard(self, emitter: UUID, subject: UUID, tenant_id: UUID) -> None:
        if emitter == subject:
            raise SelfConcernError(
                "Se signaler soi-même est une déclaration, pas un signalement par un tiers.",
                details={"kind": FactKind.THIRD_PARTY_CONCERN.value},
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
