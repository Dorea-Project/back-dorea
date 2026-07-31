"""« Voici ce que Dorea aurait signalé cette semaine. »

La sortie du rodage. Pendant que l'église observe, tout est détecté et rien n'est émis — mais le
silence ne suffirait pas : une église qui ne voit rien pendant six semaines conclut que le produit
ne fonctionne pas, et elle a raison de le conclure. Le rapport est ce qui rend le rodage lisible.

**À qui, et pourquoi lui.** Au pasteur, pas aux responsables. C'est justement le point du rodage :
personne n'est encore chargé de rien. Le pasteur regarde ce que le moteur aurait dit, décide si ça
lui ressemble, et c'est lui qui décidera de laisser Dorea parler.

**Ce que le rapport ne fait pas.** Il ne classe pas les personnes, il ne note rien, il ne propose
aucune action. Il rend ce qui a été détecté, dans l'ordre de l'arbitrage — c'est-à-dire l'ordre où
ces cas seraient sortis si l'église parlait. Rien de plus : le rodage sert à décider si le moteur
voit juste, pas à faire du soin en cachette.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.contexts.watch.application.ports import RegimeStore, SignalStore
from app.contexts.watch.domain.regime import HeldReason, TenantRegime
from app.contexts.watch.domain.signal import priority_rank


@dataclass(frozen=True)
class WouldHaveSignalled:
    """Un cas que l'église aurait reçu. Sa **raison** est celle qui aurait été affichée."""

    subject_id: UUID
    reason: str
    origin: str
    detected_at: datetime
    owner_account_id: UUID | None


@dataclass(frozen=True)
class ShadowReport:
    regime: TenantRegime
    cases: tuple[WouldHaveSignalled, ...] = ()

    @property
    def is_observing(self) -> bool:
        return self.regime is TenantRegime.SHADOW

    @property
    def count(self) -> int:
        return len(self.cases)


class BuildShadowReport:
    def __init__(self, signals: SignalStore, regimes: RegimeStore) -> None:
        self._signals = signals
        self._regimes = regimes

    async def execute(self, *, tenant_id: UUID) -> ShadowReport:
        regime = await self._regimes.regime_of(tenant_id)
        if regime is not TenantRegime.SHADOW:
            # Une église qui parle n'a pas de rapport d'ombre : ses cas sont sur des écrans.
            return ShadowReport(regime=regime)

        held = [
            case
            for case in await self._signals.held_cases(tenant_id=tenant_id)
            if case.held_reason == HeldReason.SHADOW.value
        ]
        # L'ordre de l'arbitrage : celui dans lequel ces cas seraient sortis. Le pasteur lit donc
        # la file telle qu'elle aurait été, pas un tas trié par date d'insertion.
        held.sort(key=lambda case: (priority_rank(case.priority), case.opened_at))
        return ShadowReport(
            regime=regime,
            cases=tuple(
                WouldHaveSignalled(
                    subject_id=case.subject_id,
                    reason=case.reason,
                    origin=case.origin.value,
                    detected_at=case.opened_at,
                    owner_account_id=case.owner_account_id,
                )
                for case in held
            ),
        )
