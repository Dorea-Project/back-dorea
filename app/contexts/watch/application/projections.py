"""La reprojection — reconstruire l'état à partir du seul journal.

C'est ce que le ledger achète. On n'a jamais à rattraper un état incohérent : on l'efface et on
rejoue. Une saisie tardive, une règle corrigée, un interpreter nouveau qui donne enfin du sens à
des faits vieux de six mois — trois fois la même opération.

Deux garanties portées ici :

- **l'ordre total.** Le rejeu suit `seq`, pas les dates. `recorded_at` peut être à égalité, et
  `occurred_at` peut remonter le temps ; seule la séquence d'écriture donne un ordre reproductible.
  C'est la condition de l'invariant de déterminisme ;
- **la purge est scopée.** On n'efface que ce que le moteur a projeté. Ce qu'un membre a déclaré
  lui-même n'est pas une projection : une reconstruction ne doit pas pouvoir effacer sa parole.

L'intake n'est **pas** rejoué : le journal ne contient déjà que des faits admis. On repart de
l'interprétation.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.contexts.watch.application.arbitration import ArbitrationPolicy, arbitrate
from app.contexts.watch.application.intake import FactLedger, load_state
from app.contexts.watch.application.interpretation import InterpreterRegistry
from app.contexts.watch.application.materialization import Materializer
from app.contexts.watch.application.owner_assignment import ResolveOwners
from app.contexts.watch.application.ports import NeutralizationStore, SignalStore


@dataclass(frozen=True)
class ReplayReport:
    facts: int = 0
    written: int = 0
    deferred: int = 0  # proposés, pas encore matérialisables
    held: int = 0  # retenus par le plafond
    dropped: int = 0


class RebuildProjections:
    def __init__(
        self,
        ledger: FactLedger,
        interpreters: InterpreterRegistry,
        store: NeutralizationStore,
        signals: SignalStore | None = None,
        owners: ResolveOwners | None = None,
        *,
        policy: ArbitrationPolicy | None = None,
    ) -> None:
        self._ledger = ledger
        self._interpreters = interpreters
        self._store = store
        self._signals = signals
        # Le même étage 02bis qu'en direct. Sans lui, le rejeu réécrirait des propriétaires nuls
        # sur une colonne NOT NULL : la reprojection, qu'on lance précisément quand quelque chose
        # est déjà cassé, échouerait là où elle doit réparer.
        self._owners = owners
        self._materializer = Materializer(store, signals)
        self._policy = policy or ArbitrationPolicy()

    async def execute(self, *, tenant_id: UUID) -> ReplayReport:
        await self._store.purge_projected_neutralizations(tenant_id)
        if self._signals is not None:
            await self._signals.purge_projected(tenant_id)

        facts = await self._ledger.stream(tenant_id)
        facts.sort(key=lambda f: f.seq if f.seq is not None else 0)

        report = ReplayReport()
        for fact in facts:
            # L'état est relu à chaque pas : un effet posé par le fait n éclaire le fait n+1,
            # exactement comme en direct.
            state = await load_state(self._store, self._signals, tenant_id)
            proposed = self._interpreters.interpret(fact, state)
            undeliverable = ()
            if self._owners is not None:
                proposed, undeliverable = await self._owners.execute(
                    proposed, tenant_id=tenant_id, at=fact.occurred_at
                )
            decided = arbitrate(proposed, state, policy=self._policy)
            written = await self._materializer.apply(fact, decided.admitted, decided.held)
            report = ReplayReport(
                facts=report.facts + 1,
                written=report.written + len(written.written),
                deferred=report.deferred + len(written.deferred),
                held=report.held + len(written.held),
                dropped=report.dropped + len(decided.dropped) + len(undeliverable),
            )
        return report
