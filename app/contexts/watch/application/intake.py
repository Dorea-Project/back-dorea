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

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, replace
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
from app.contexts.watch.application.owner_assignment import ResolveOwners
from app.contexts.watch.application.ports import (
    ContactAttemptStore,
    NeutralizationStore,
    RegimeStore,
    ScheduledCheckStore,
    SignalStore,
)
from app.contexts.watch.domain.effects import OpenCase, ProposedEffect
from app.contexts.watch.domain.errors import (
    ConsentRequiredError,
    FactKindNotAllowedError,
    InvalidPayloadError,
)
from app.contexts.watch.domain.facts import (
    CASE_ACTS,
    KIND_REQUIRED_KEYS,
    Fact,
    SubjectKind,
)
from app.contexts.watch.domain.regime import TenantRegime
from app.contexts.watch.domain.registry import SourceRegistry


class FactLedger:
    """Contrat du journal. Append-only : aucune méthode ne modifie ni ne supprime un fait."""

    async def append(self, fact: Fact) -> Fact: ...

    async def exists(self, fact_id: UUID) -> bool: ...

    def stream(self, tenant_id: UUID) -> AsyncIterator[Fact]:
        """Le journal d'une église, **dans l'ordre de `seq`**, en flux.

        Un flux et non une liste : le rejeu d'une grande église ne doit pas commencer par charger
        son journal entier en mémoire. Et l'ordre est celui de la base, pas d'un tri refait après
        coup — c'est le même ordre total qui fonde l'invariant de déterminisme."""
        ...


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
        owners: ResolveOwners | None = None,
        attempts: ContactAttemptStore | None = None,
        regimes: RegimeStore | None = None,
        *,
        policy: ArbitrationPolicy | None = None,
    ) -> None:
        self._ledger = ledger
        self._sources = sources
        self._interpreters = interpreters
        self._store = store
        self._signals = signals
        # Sans résolveur, une ouverture garde le propriétaire que la source a joint et rien de
        # plus : c'est le régime des tests d'unité purs, jamais celui de la production — où la
        # colonne est NOT NULL et refuserait l'écriture.
        self._owners = owners
        # Le rodage : sans dépôt, on suppose une église qui parle (tests d'unité).
        self._regimes = regimes
        self._materializer = Materializer(store, signals, checks, attempts=attempts)
        self._policy = policy or ArbitrationPolicy()

    async def submit(self, fact: Fact) -> IntakeResult:
        source = self._sources.get(fact.source)  # lève si non enregistrée
        if fact.kind not in source.kinds:
            raise FactKindNotAllowedError(
                "Cette source n'est pas enregistrée pour émettre ce type de fait.",
                details={"source": fact.source, "kind": fact.kind.value},
            )
        # Ce que la **source** exige, et ce que le **type de fait** exige : un geste sans acteur
        # ni cas visé n'est pas un geste, quelle que soit la surface qui l'envoie.
        missing = (
            source.required_payload_keys | KIND_REQUIRED_KEYS.get(fact.kind, frozenset())
        ) - set(fact.payload)
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

        state = await self._load_state(fact)
        if (
            fact.is_about_person
            and fact.kind not in CASE_ACTS
            and state.is_excluded(fact.subject_id)
        ):
            # Retirée de la veille : plus rien n'entre sur elle, quelle que soit la source.
            #
            # **Sauf les gestes du responsable.** Fermer le cas d'un défunt est justement l'acte
            # qu'on attend de lui ; le refuser laisserait le cas ouvert pour toujours sur son
            # écran, et ferait de la mort de quelqu'un un bug d'interface.
            return IntakeResult(accepted=False, reason="subject_excluded")

        sealed = await self._ledger.append(fact)
        return await self._run(sealed, state)

    async def _run(self, fact: Fact, state: WatchStateView) -> IntakeResult:
        proposed = self._interpreters.interpret(fact, state)
        # Étage 02bis — le destinataire, résolu **avant** l'arbitrage : c'est lui qui compte le
        # plafond par propriétaire, et après la fusion il est trop tard pour savoir à qui
        # l'ouverture aurait été adressée.
        undeliverable: tuple[tuple[ProposedEffect, str], ...] = ()
        if self._owners is not None:
            proposed, undeliverable = await self._owners.execute(
                proposed, tenant_id=fact.tenant_id, at=fact.occurred_at
            )
        # Puis seulement le budget des destinataires — l'arbitrage ne peut pas compter avant que
        # l'on sache à qui les cas s'adressent.
        state = await with_owner_budgets(state, proposed, self._signals, fact.tenant_id)
        decided = arbitrate(proposed, state, policy=self._policy)
        if undeliverable:
            decided = replace(decided, dropped=decided.dropped + undeliverable)
        written = await self._materializer.apply(
            fact, decided.admitted, decided.held, decided.held_reason.value
        )
        return IntakeResult(
            accepted=True, fact=fact, arbitration=decided, materialization=written
        )

    async def _load_state(self, fact: Fact) -> WatchStateView:
        """Charge l'état **du sujet** que les interpreters liront — eux restent purs."""
        return await load_state(self._store, self._signals, fact, self._regimes)


def person_subject(subject_id: UUID) -> tuple[SubjectKind, UUID]:
    return SubjectKind.PERSON, subject_id


def warn_if_disconnected(source: str, intake: Intake | None) -> None:
    """Une source construite **sans intake** n'émet rien, et ne le dit à personne.

    Le patron `Intake | None` est utile : il laisse tester un module sans monter le moteur, et il
    laisse un contexte fonctionner si la veille n'est pas déployée. Mais c'est aussi le plus
    silencieux des défauts d'assemblage — un oubli de câblage et une source entière se tait, sans
    erreur, sans test rouge, jusqu'au jour où l'on cherche pourquoi personne n'a été signalé."""
    if intake is None:
        logging.getLogger("dorea.watch.intake").warning(
            "source « %s » construite sans intake : elle n'émettra aucun fait de veille.", source
        )


async def load_state(
    store: NeutralizationStore,
    signals: SignalStore | None,
    fact: Fact,
    regimes: RegimeStore | None = None,
) -> WatchStateView:
    """L'état **borné au sujet du fait** — trois lectures ponctuelles, indexées.

    C'est tout ce qu'un interpreter a le droit de demander, et c'est ce qui fait que le coût d'un
    fait ne dépend plus de la taille de l'église. Une église de cinq mille membres payait cent fois
    le prix d'une église de cinquante pour écrire la même présence.

    Partagé entre l'intake et la reprojection : ils doivent lire rigoureusement la même chose,
    sinon le rejeu ne reproduirait pas ce que le direct a produit."""
    subject_id = fact.subject_id
    excluded = await store.is_excluded(subject_id, fact.tenant_id)
    neutralizations = await store.neutralizations_of_subject(subject_id, fact.tenant_id)
    case = (
        await signals.case_of_subject(subject_id, fact.tenant_id)
        if signals is not None
        else None
    )
    # Le régime de rodage : une église qui observe détecte tout et n'émet rien. Sans dépôt —
    # les tests d'unité purs — on suppose une église qui parle.
    regime = (
        await regimes.regime_of(fact.tenant_id) if regimes is not None else TenantRegime.STEADY
    )
    return WatchStateView.for_subject(
        subject_id,
        excluded=excluded,
        regime=regime,
        neutralizations=tuple(
            NeutralizationView(
                id=row[0], subject_id=row[1], starts_at=row[2], expected_return_at=row[3]
            )
            for row in neutralizations
        ),
        case=(
            OpenCaseView(
                id=case[0], subject_id=case[1], owner_id=case[2], origin=case[3], is_held=case[4]
            )
            if case is not None
            else None
        ),
    )


async def load_full_state(
    store: NeutralizationStore, signals: SignalStore | None, tenant_id: UUID
) -> WatchStateView:
    """L'état de **toute** l'église — la vue matérialisée d'origine.

    Le chemin d'un fait ne l'emprunte plus. Elle reste la référence contre laquelle la vue réduite
    est vérifiée, et sert ce qui lit réellement une église entière."""
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


async def with_owner_budgets(
    state: WatchStateView, effects, signals: SignalStore | None, tenant_id: UUID
) -> WatchStateView:
    """Précharge le budget des propriétaires que l'arbitrage va interroger.

    **L'ordre est la spécification.** La vue est bornée au sujet du fait ; le plafond de débit, lui,
    compte les cas du *propriétaire*, qui n'est presque jamais le sujet. Sans ce préchargement — et
    donc sans que les destinataires soient déjà résolus — le compteur répondrait zéro, le plafond ne
    retiendrait plus rien, et rien ne le dirait : un responsable pourrait recevoir trente cas dans
    la soirée sans qu'un seul test ne rougisse."""
    if signals is None or state.subject_id is None:
        return state
    owners = {
        getattr(e, "owner_account_id", None) for e in effects if isinstance(e, OpenCase)
    }
    counts = {
        owner: await signals.open_cases_count(owner, tenant_id) for owner in owners
    }
    return state.with_owner_counts(counts)
