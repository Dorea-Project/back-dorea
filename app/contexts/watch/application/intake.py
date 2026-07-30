"""Étage 01 — l'intake : la porte, et le ledger derrière.

Un fait est refusé s'il vient d'une source inconnue, s'il lui manque le consentement que son
type exige, s'il porte sur quelqu'un retiré de la veille, ou s'il a déjà été admis. Sinon il est
**écrit au ledger** — append-only, immuable, et source de vérité de tout ce qui suit.

Puis la pipeline se déroule : interpréter → arbitrer → matérialiser. Tout ce qui vient après le
ledger est une projection ; c'est ce qui rend la reprojection sûre et la rétractation propre.

Le rejeu d'une exclusion mérite un mot. Le contrôle « personne exclue » vit ici, à l'entrée : il
filtre ce qui **entre**, et le rejeu ne repasse pas par l'intake — il rejoue un journal déjà
filtré. Le déterminisme tient. Ce qui ne tient pas encore, c'est l'exclusion **rétroactive** :
un décès survenu en mars et annoncé en avril laisse derrière lui des semaines de faits
légitimement admis. La réponse n'est pas un second contrôle, c'est la rétraction — elle viendra
avec le `Signal`.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.contexts.watch.application.arbitration import (
    Arbitration,
    ArbitrationPolicy,
    arbitrate,
)
from app.contexts.watch.application.interpretation import (
    InterpreterRegistry,
    NeutralizationView,
    OpenCaseView,
    WatchStateView,
)
from app.contexts.watch.application.materialization import (
    MaterializationResult,
    Materializer,
)
from app.contexts.watch.application.ports import (
    NeutralizationStore,
    ScheduledCheckStore,
    SignalStore,
)
from app.contexts.watch.domain.errors import (
    ConsentRequiredError,
    FactKindNotAllowedError,
    InvalidPayloadError,
)
from app.contexts.watch.domain.facts import Fact, SubjectKind
from app.contexts.watch.domain.registry import SourceRegistry


class FactLedger:
    """Contrat du journal. Append-only : aucune méthode ne modifie ni ne supprime un fait."""

    async def append(self, fact: Fact) -> Fact: ...

    async def exists(self, fact_id: UUID) -> bool: ...

    async def stream(self, tenant_id: UUID) -> list[Fact]: ...


@dataclass(frozen=True)
class IntakeResult:
    accepted: bool
    reason: str | None = None
    fact: Fact | None = None
    arbitration: Arbitration | None = None
    materialization: MaterializationResult | None = None


class Intake:
    def __init__(
        self,
        ledger: FactLedger,
        sources: SourceRegistry,
        interpreters: InterpreterRegistry,
        store: NeutralizationStore,
        signals: SignalStore | None = None,
        checks: ScheduledCheckStore | None = None,
        *,
        policy: ArbitrationPolicy | None = None,
    ) -> None:
        self._ledger = ledger
        self._sources = sources
        self._interpreters = interpreters
        self._store = store
        self._signals = signals
        self._materializer = Materializer(store, signals, checks)
        self._policy = policy or ArbitrationPolicy()

    async def submit(self, fact: Fact) -> IntakeResult:
        source = self._sources.get(fact.source)  # lève si non enregistrée
        if fact.kind not in source.kinds:
            raise FactKindNotAllowedError(
                "Cette source n'est pas enregistrée pour émettre ce type de fait.",
                details={"source": fact.source, "kind": fact.kind.value},
            )
        missing = source.required_payload_keys - set(fact.payload)
        if missing:
            raise InvalidPayloadError(
                "Le payload ne porte pas ce que ce type de fait exige.",
                details={"missing": sorted(missing), "kind": fact.kind.value},
            )
        if fact.requires_consent() and fact.consent is None:
            raise ConsentRequiredError(
                "Ce type de fait ne peut pas entrer sans preuve de consentement.",
                details={"kind": fact.kind.value},
            )

        if await self._ledger.exists(fact.fact_id):
            return IntakeResult(accepted=False, reason="duplicate")

        state = await self._load_state(fact.tenant_id)
        if fact.is_about_person and state.is_excluded(fact.subject_id):
            # Retirée de la veille : plus rien n'entre sur elle, quelle que soit la source.
            return IntakeResult(accepted=False, reason="subject_excluded")

        sealed = await self._ledger.append(fact)
        return await self._run(sealed, state)

    async def _run(self, fact: Fact, state: WatchStateView) -> IntakeResult:
        proposed = self._interpreters.interpret(fact, state)
        decided = arbitrate(proposed, state, policy=self._policy)
        written = await self._materializer.apply(fact, decided.admitted, decided.held)
        return IntakeResult(
            accepted=True, fact=fact, arbitration=decided, materialization=written
        )

    async def _load_state(self, tenant_id: UUID) -> WatchStateView:
        """Charge une fois l'état que les interpreters liront — eux restent purs."""
        return await load_state(self._store, self._signals, tenant_id)


def person_subject(subject_id: UUID) -> tuple[SubjectKind, UUID]:
    return SubjectKind.PERSON, subject_id


async def load_state(
    store: NeutralizationStore, signals: SignalStore | None, tenant_id: UUID
) -> WatchStateView:
    """L'état projeté, chargé **une fois** avant l'interprétation.

    Partagé entre l'intake et la reprojection pour qu'ils lisent rigoureusement la même chose —
    sinon le rejeu ne reproduirait pas ce que le direct a produit."""
    excluded = await store.excluded_subject_ids(tenant_id)
    neutralizations = await store.open_neutralizations(tenant_id)
    cases = await signals.live_cases(tenant_id) if signals is not None else []
    return WatchStateView(
        excluded_subject_ids=frozenset(excluded),
        open_neutralizations=tuple(
            NeutralizationView(
                id=row[0], subject_id=row[1], starts_at=row[2], expected_return_at=row[3]
            )
            for row in neutralizations
        ),
        open_cases=tuple(
            OpenCaseView(
                id=row[0], subject_id=row[1], owner_id=row[2], origin=row[3], is_held=row[4]
            )
            for row in cases
        ),
    )
