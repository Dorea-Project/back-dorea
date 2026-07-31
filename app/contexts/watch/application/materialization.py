"""Étage 04 — la matérialisation : écrire ce que l'arbitrage a admis.

Seul chemin d'écriture de l'engine. Tout ce qui est ici est une **projection** du ledger : on
peut l'effacer et la reconstruire sans rien perdre, puisque la vérité est le journal.

Sait écrire : la neutralisation et son extinction, le retrait définitif, le **cas** et son
enrichissement, la mémoire du lien.

Sait aussi écrire l'**échéance** et son annulation. C'est par elle que le temps entre dans la
veille : quand une échéance tombe, le worker écrit un `CHECK_FIRED` au ledger — il ne modifie
aucun état lui-même. Un interpreter ne lit donc jamais l'horloge, et rejouer demain rend
exactement ce que le direct a produit.

**L'annulation est vitale, et elle est ici plutôt que dispersée.** Un retrait définitif ou un
retour constaté annule ce qui était programmé — sinon on programme des rappels sur des gens
décédés, l'échec le plus coûteux que ce produit puisse produire.

Sait enfin écrire le **signal de couverture** : un défaut de dispositif va dans
`watch_coverage_gaps`, là où il se lira. Un défaut consigné dans un journal applicatif n'existe
pour personne — et l'église mal configurée resterait silencieuse, son écran vide disant « tout va
bien » alors qu'il dit « personne n'est là pour voir ».
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID, uuid4

from app.contexts.watch.application.ports import (
    ContactAttemptStore,
    NeutralizationStore,
    ScheduledCheckStore,
    SignalStore,
)
from app.contexts.watch.application.referent_ports import CoverageGapStore
from app.contexts.watch.domain.coverage import CoverageGapRecord
from app.contexts.watch.domain.effects import (
    CancelScheduledChecks,
    CoverageScope,
    CoverageSignal,
    EffectKind,
    EnrichCase,
    ExcludeForever,
    Extinguish,
    ExtinguishCause,
    MarkCaseSeen,
    Neutralise,
    OpenCase,
    ProposedEffect,
    RecordContactAttempt,
    RecordMemory,
    ResolveCase,
    ResolveContactAttempt,
    ScheduleCheck,
)
from app.contexts.watch.domain.facts import Fact


@dataclass(frozen=True)
class MaterializationResult:
    written: tuple[EffectKind, ...] = ()
    deferred: tuple[EffectKind, ...] = ()  # proposés, pas encore matérialisables
    held: tuple[EffectKind, ...] = ()  # retenus par le plafond — détectés, non émis


class Materializer:
    def __init__(
        self,
        store: NeutralizationStore,
        signals: SignalStore | None = None,
        checks: ScheduledCheckStore | None = None,
        gaps: CoverageGapStore | None = None,
        *,
        attempts: ContactAttemptStore | None = None,
        id_factory=uuid4,
    ) -> None:
        self._store = store
        self._signals = signals
        self._checks = checks
        # Le magasin des défauts de dispositif. Sans lui, `CoverageSignal` restait « proposé et
        # jamais écrit » — et depuis le lot 2a, ce silence-là est au moins bruyant.
        self._gaps = gaps
        # Les tentatives de contact sont désormais écrites depuis le journal, elles aussi.
        self._attempts = attempts
        self._new_id = id_factory

    async def apply(
        self,
        fact: Fact,
        effects: Sequence[ProposedEffect],
        held: Sequence[ProposedEffect] = (),
    ) -> MaterializationResult:
        written: list[EffectKind] = []
        deferred: list[EffectKind] = []
        actor = _actor_of(fact)
        source_ref = _source_ref_of(fact)

        for effect in effects:
            kind = await self._write(fact, effect, actor=actor, source_ref=source_ref)
            if kind is not None:
                written.append(kind)
                continue
            missed = _kind_of(effect)
            deferred.append(missed)
            _report_deferred(fact, missed)

        # Un cas retenu est écrit lui aussi — mais en `HELD` : détecté, non émis, réévalué.
        # Le perdre ferait mentir la mesure du plafond au moment même où elle compte.
        held_kinds: list[EffectKind] = []
        for effect in held:
            if isinstance(effect, OpenCase) and self._signals is not None:
                await self._signals.open_case(
                    subject_id=effect.subject_id,
                    tenant_id=fact.tenant_id,
                    origin=effect.origin.value,
                    reason=effect.reason,
                    opened_at=effect.opened_at,
                    expires_at=effect.expires_at,
                    source_ref=source_ref,
                    held=True,
                    owner_account_id=effect.owner_account_id,
                )
                held_kinds.append(EffectKind.OPEN_CASE)

        return MaterializationResult(
            written=tuple(written), deferred=tuple(deferred), held=tuple(held_kinds)
        )

    async def _cancel_checks(self, fact: Fact, subject_id: UUID, *, kind, at) -> None:
        if self._checks is not None:
            await self._checks.cancel_for(
                subject_id=subject_id, tenant_id=fact.tenant_id, kind=kind, at=at
            )

    async def _write(
        self, fact: Fact, effect: ProposedEffect, *, actor: UUID, source_ref: UUID
    ) -> EffectKind | None:
        """Renvoie le type écrit, ou None si cet effet n'est pas encore matérialisable."""
        if isinstance(effect, ScheduleCheck) and self._checks is not None:
            await self._checks.schedule(
                subject_id=effect.subject_id,
                tenant_id=fact.tenant_id,
                kind=effect.kind,
                # La raison voyage avec l'échéance : un rappel qu'on ne sait plus expliquer est
                # un rappel qu'on ignore. Le payload voyage aussi : c'est ce que l'interpreter du
                # tir lira, écrit maintenant plutôt que relu dans un état qui aura bougé.
                reason=effect.reason,
                payload=dict(effect.payload),
                due_at=effect.at,
                at=fact.occurred_at,
            )
            return EffectKind.SCHEDULE_CHECK

        if isinstance(effect, CancelScheduledChecks) and self._checks is not None:
            await self._checks.cancel_for(
                subject_id=effect.subject_id,
                tenant_id=fact.tenant_id,
                kind=effect.kind,
                at=fact.occurred_at,
            )
            return EffectKind.CANCEL_SCHEDULED_CHECKS

        if isinstance(effect, ExcludeForever):
            # Retrait définitif : **plus rien** ne doit tomber sur cette personne. C'est
            # l'annulation la plus importante du module — relancer un défunt est l'échec que
            # tout le reste existe pour empêcher.
            await self._cancel_checks(fact, effect.subject_id, kind=None, at=effect.at)
            await self._store.exclude_forever(
                subject_id=effect.subject_id,
                tenant_id=fact.tenant_id,
                source_ref=source_ref,
                declared_by_account_id=actor,
                reason=effect.reason,
                at=effect.at,
            )
            return EffectKind.EXCLUDE_FOREVER

        if isinstance(effect, Extinguish):
            await self._store.extinguish(
                subject_id=effect.subject_id,
                tenant_id=fact.tenant_id,
                cause=effect.cause.value,
                at=effect.at,
            )
            if effect.cause is ExtinguishCause.RETURNED:
                # La personne est revenue : l'échéance de retour n'a plus d'objet. On n'annule
                # que celle-là — le cas, lui, reste ouvert (« on peut être présent et endeuillé »).
                await self._cancel_checks(fact, effect.subject_id, kind="return", at=effect.at)
            if self._signals is not None:
                # Le cas ne se ferme que si la cause l'autorise **sans acte humain**.
                await self._signals.extinguish(
                    subject_id=effect.subject_id,
                    tenant_id=fact.tenant_id,
                    cause=effect.cause.value,
                    at=effect.at,
                )
            return EffectKind.EXTINGUISH

        if isinstance(effect, Neutralise):
            await self._store.neutralize(
                subject_id=effect.subject_id,
                tenant_id=fact.tenant_id,
                role=effect.role,
                starts_at=effect.starts_at,
                expected_return_at=effect.expected_return_at,
                source_ref=source_ref,
                declared_by_account_id=actor,
                reason=effect.reason,
            )
            return EffectKind.NEUTRALISE

        if isinstance(effect, OpenCase) and self._signals is not None:
            await self._signals.open_case(
                subject_id=effect.subject_id,
                tenant_id=fact.tenant_id,
                origin=effect.origin.value,
                reason=effect.reason,
                opened_at=effect.opened_at,
                expires_at=effect.expires_at,
                source_ref=source_ref,
                held=False,
                owner_account_id=effect.owner_account_id,
            )
            return EffectKind.OPEN_CASE

        if isinstance(effect, EnrichCase) and self._signals is not None:
            await self._signals.enrich_case(
                subject_id=effect.subject_id,
                tenant_id=fact.tenant_id,
                source_ref=source_ref,
                extend_to=effect.extend_to,
                annotation=effect.annotation,
                priority=effect.priority.value if effect.priority else None,
                downgrade=effect.downgrade,
            )
            return EffectKind.ENRICH_CASE

        if isinstance(effect, CoverageSignal) and self._gaps is not None:
            # Un défaut de dispositif, consigné là où il se lira — jamais dans un journal
            # applicatif. `record_once` déduplique : un rappel qui revient chaque nuit devient du
            # bruit, et le bruit se désapprend en trois semaines.
            await self._gaps.record_once(
                CoverageGapRecord(
                    id=self._new_id(),
                    tenant_id=fact.tenant_id,
                    scope=CoverageScope.PERSON,
                    subject_id=effect.subject_id,
                    gap=effect.gap,
                    reason=effect.reason,
                    observed_at=effect.at,
                )
            )
            return EffectKind.COVERAGE_SIGNAL

        if isinstance(effect, RecordContactAttempt) and self._attempts is not None:
            await self._attempts.record(
                attempt_id=effect.attempt_id,
                subject_id=effect.subject_id,
                tenant_id=fact.tenant_id,
                by_account_id=effect.by_account_id,
                channel=effect.channel,
                at=effect.at,
            )
            if self._signals is not None:
                # L'intention est écrite **avant** que l'application perde la main : c'est ce qui
                # rend `first_contact_at` juste même quand personne ne revient dire l'issue.
                await self._signals.mark_contact_started_for_subject(
                    subject_id=effect.subject_id, tenant_id=fact.tenant_id, at=effect.at
                )
            return EffectKind.RECORD_CONTACT_ATTEMPT

        if isinstance(effect, ResolveContactAttempt) and self._attempts is not None:
            await self._attempts.resolve(
                attempt_id=effect.attempt_id,
                result=effect.result,
                at=effect.at,
                commitment=effect.commitment,
            )
            return EffectKind.RESOLVE_CONTACT_ATTEMPT

        if isinstance(effect, MarkCaseSeen) and self._signals is not None:
            await self._signals.mark_seen(
                subject_id=effect.subject_id, tenant_id=fact.tenant_id, at=effect.at
            )
            return EffectKind.MARK_CASE_SEEN

        if isinstance(effect, ResolveCase) and self._signals is not None:
            await self._signals.resolve_case(
                subject_id=effect.subject_id,
                tenant_id=fact.tenant_id,
                outcome=effect.outcome,
                at=effect.at,
                by_account_id=effect.by_account_id,
            )
            return EffectKind.RESOLVE_CASE

        if isinstance(effect, RecordMemory) and self._signals is not None:
            await self._signals.record_memory(
                subject_id=effect.subject_id,
                tenant_id=fact.tenant_id,
                item=effect.item,
                at=effect.at,
                reason=effect.reason,
            )
            return EffectKind.RECORD_MEMORY

        return None


_logger = logging.getLogger("dorea.watch.materialization")

# Combien de fois chaque type d'effet a été proposé sans pouvoir être écrit, depuis le démarrage.
# Un compteur, pas une table : c'est un défaut d'assemblage, il se lit à l'exploitation et il doit
# **tomber à zéro** quand tout est branché.
DEFERRED_COUNTS: dict[EffectKind, int] = {}


def _report_deferred(fact: Fact, kind: EffectKind) -> None:
    """Un effet proposé que rien n'a écrit. **Jamais en silence.**

    L'engine renvoyait déjà la liste des différés, et tous ses appelants la jetaient. Un
    interpreter pouvait donc proposer une échéance, ne rien produire, et personne ne l'apprenait —
    exactement le faux silence que le module existe pour empêcher, retourné contre lui-même.

    Le cas réel : la reprojection construite sans store d'échéances effaçait les échéances d'une
    église et n'en reposait aucune, sans une ligne de journal."""
    DEFERRED_COUNTS[kind] = DEFERRED_COUNTS.get(kind, 0) + 1
    _logger.warning(
        "effet proposé non matérialisé : %s (source=%s, kind=%s, fact_id=%s, tenant=%s)",
        kind.value,
        fact.source,
        fact.kind.value,
        fact.fact_id,
        fact.tenant_id,
    )


_KIND_OF: dict[str, EffectKind] = {
    "OpenCase": EffectKind.OPEN_CASE,
    "EnrichCase": EffectKind.ENRICH_CASE,
    "Neutralise": EffectKind.NEUTRALISE,
    "Extinguish": EffectKind.EXTINGUISH,
    "ExcludeForever": EffectKind.EXCLUDE_FOREVER,
    "RecordMemory": EffectKind.RECORD_MEMORY,
    "MarkCaseSeen": EffectKind.MARK_CASE_SEEN,
    "RecordContactAttempt": EffectKind.RECORD_CONTACT_ATTEMPT,
    "ResolveContactAttempt": EffectKind.RESOLVE_CONTACT_ATTEMPT,
    "ResolveCase": EffectKind.RESOLVE_CASE,
    "ScheduleCheck": EffectKind.SCHEDULE_CHECK,
    "CancelScheduledChecks": EffectKind.CANCEL_SCHEDULED_CHECKS,
    "CoverageSignal": EffectKind.COVERAGE_SIGNAL,
}


def _kind_of(effect: ProposedEffect) -> EffectKind:
    return _KIND_OF[type(effect).__name__]


def _actor_of(fact: Fact) -> UUID:
    """Qui a produit le fait — porté par le payload, à défaut le sujet lui-même."""
    actor = fact.payload.get("actor_account_id")
    return UUID(str(actor)) if actor else fact.subject_id


def _source_ref_of(fact: Fact) -> UUID:
    """Ce à quoi rattacher l'écriture — l'annonce d'origine, à défaut le fait lui-même.

    C'est la clé d'idempotence : rejouer le même fait ne crée jamais un doublon."""
    ref = fact.payload.get("announcement_id")
    return UUID(str(ref)) if ref else fact.fact_id
