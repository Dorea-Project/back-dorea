"""Étage 04 — la matérialisation : écrire ce que l'arbitrage a admis.

Seul chemin d'écriture de l'engine. Tout ce qui est ici est une **projection** du ledger : on
peut l'effacer et la reconstruire sans rien perdre, puisque la vérité est le journal.

Sait écrire : la neutralisation et son extinction, le retrait définitif, le **cas** et son
enrichissement, la mémoire du lien.

Ne sait pas encore : l'échéance (`SCHEDULE_CHECK`, son annulation) et le signal de couverture —
ils attendent le worker et le `Referent`. Ils ne sont pas perdus : les faits sont au ledger, et
une reprojection les honorera le jour où l'objet existera.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from app.contexts.watch.application.ports import NeutralizationStore, SignalStore
from app.contexts.watch.domain.effects import (
    EffectKind,
    EnrichCase,
    ExcludeForever,
    Extinguish,
    Neutralise,
    OpenCase,
    ProposedEffect,
    RecordMemory,
)
from app.contexts.watch.domain.facts import Fact


@dataclass(frozen=True)
class MaterializationResult:
    written: tuple[EffectKind, ...] = ()
    deferred: tuple[EffectKind, ...] = ()  # proposés, pas encore matérialisables
    held: tuple[EffectKind, ...] = ()  # retenus par le plafond — détectés, non émis


class Materializer:
    def __init__(self, store: NeutralizationStore, signals: SignalStore | None = None) -> None:
        self._store = store
        self._signals = signals

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
            (written if kind is not None else deferred).append(kind or _kind_of(effect))

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
                )
                held_kinds.append(EffectKind.OPEN_CASE)

        return MaterializationResult(
            written=tuple(written), deferred=tuple(deferred), held=tuple(held_kinds)
        )

    async def _write(
        self, fact: Fact, effect: ProposedEffect, *, actor: UUID, source_ref: UUID
    ) -> EffectKind | None:
        """Renvoie le type écrit, ou None si cet effet n'est pas encore matérialisable."""
        if isinstance(effect, ExcludeForever):
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
            )
            return EffectKind.OPEN_CASE

        if isinstance(effect, EnrichCase) and self._signals is not None:
            await self._signals.enrich_case(
                subject_id=effect.subject_id,
                tenant_id=fact.tenant_id,
                source_ref=source_ref,
                extend_to=effect.extend_to,
            )
            return EffectKind.ENRICH_CASE

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


_KIND_OF: dict[str, EffectKind] = {
    "OpenCase": EffectKind.OPEN_CASE,
    "EnrichCase": EffectKind.ENRICH_CASE,
    "Neutralise": EffectKind.NEUTRALISE,
    "Extinguish": EffectKind.EXTINGUISH,
    "ExcludeForever": EffectKind.EXCLUDE_FOREVER,
    "RecordMemory": EffectKind.RECORD_MEMORY,
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
