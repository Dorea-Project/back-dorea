"""La reprojection — reconstruire l'état à partir du seul journal.

C'est ce que le ledger achète. On n'a jamais à rattraper un état incohérent : on l'efface et on
rejoue. Une saisie tardive, une règle corrigée, un interpreter nouveau qui donne enfin du sens à
des faits vieux de six mois — trois fois la même opération.

**Cette promesse ne couvre que ce qui dérive des faits** — et depuis le lot 3bis, elle en couvre
beaucoup plus : l'avoir ouvert, avoir tenté de joindre, avoir dit ce qui s'est passé, avoir fermé
avec une issue sont désormais des **faits au journal**. Un rejeu les reconstruit, avec les deux
métriques du pilote et la chaîne d'épisode.

Le garde-fou `_guard_human_acts` a donc rétréci à ce qui reste hors du journal : les consolations
déjà **remises** (leur remise est un acte, et la remettre deux fois serait pire que ne rien
remettre) et les gestes comptés. Il disparaîtra quand ces deux-là suivront le même chemin.

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
from app.contexts.watch.application.intake import (
    FactLedger,
    load_state,
    with_owner_budgets,
)
from app.contexts.watch.application.interpretation import InterpreterRegistry
from app.contexts.watch.application.materialization import Materializer
from app.contexts.watch.application.owner_assignment import ResolveOwners
from app.contexts.watch.application.ports import (
    ContactAttemptStore,
    NeutralizationStore,
    ScheduledCheckStore,
    SignalStore,
)
from app.contexts.watch.domain.errors import ReplayWouldEraseHumanActsError


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
        checks: ScheduledCheckStore | None = None,
        attempts: ContactAttemptStore | None = None,
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
        # **La matérialisation complète, échéances comprises.** Sans le store d'échéances, tout
        # `ScheduleCheck` retombait en « différé » — et différé était jeté sans un mot. Une
        # reprojection effaçait donc toutes les échéances d'une église et n'en reposait aucune :
        # plus rien ne serait jamais revenu relancer personne, et on l'aurait découvert des
        # semaines plus tard, sur les gens dont on n'a plus de nouvelles.
        self._checks = checks
        # Les tentatives de contact sont des projections depuis le lot 3bis : elles se
        # reconstruisent depuis le journal, donc elles se purgent avant de rejouer.
        self._attempts = attempts
        self._materializer = Materializer(store, signals, checks, attempts=attempts)
        self._policy = policy or ArbitrationPolicy()

    async def execute(self, *, tenant_id: UUID, force: bool = False) -> ReplayReport:
        """Rejoue le journal de cette église.

        `force=True` accepte explicitement de **perdre les actes humains** (voir le garde-fou
        ci-dessous). Ce n'est pas un drapeau de commodité : c'est une signature."""
        await self._guard_human_acts(tenant_id, force=force)
        await self._store.purge_projected_neutralizations(tenant_id)
        if self._signals is not None:
            await self._signals.purge_projected(tenant_id)
        if self._attempts is not None:
            await self._attempts.purge_projected(tenant_id)
        if self._checks is not None:
            # Les échéances **en attente** seulement : celles qui ont tiré sont de l'histoire, et
            # les reposer ferait retomber deux fois le même silence sur la même personne.
            await self._checks.purge_projected(tenant_id)

        report = ReplayReport()
        # Le flux vient déjà trié par `seq` — l'ordre total, celui de l'écriture. On ne le refait
        # pas en mémoire : trier suppose d'avoir tout chargé, ce que le flux existe pour éviter.
        async for fact in self._ledger.stream(tenant_id):
            # L'état est relu à chaque pas : un effet posé par le fait n éclaire le fait n+1,
            # exactement comme en direct.
            state = await load_state(self._store, self._signals, fact)
            proposed = self._interpreters.interpret(fact, state)
            undeliverable = ()
            if self._owners is not None:
                proposed, undeliverable = await self._owners.execute(
                    proposed, tenant_id=tenant_id, at=fact.occurred_at
                )
            state = await with_owner_budgets(state, proposed, self._signals, tenant_id)
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

    async def _guard_human_acts(self, tenant_id: UUID, *, force: bool) -> None:
        """Refuse de rejouer si un acte humain que le journal **ne contient pas** serait effacé.

        Le garde a rétréci avec le lot 3bis : le regard, les tentatives, les issues sont entrés au
        ledger, donc un rejeu les reconstruit. Ce qui reste hors du journal, et qu'aucune
        reconstruction ne rendrait : les consolations **déjà remises** — leur remise est un acte, et
        la refaire serait pire que ne rien remettre — et les gestes comptés.

        Il disparaîtra quand ces deux-là suivront le même chemin. D'ici là il empêche une commande
        de maintenance de faire, en une seconde, un dégât qu'aucune sauvegarde ne répare."""
        if force or self._signals is None:
            return
        traces = await self._signals.human_traces(tenant_id)
        # Seul ce qui n'est **pas** reconstructible bloque désormais.
        if traces.delivered_memories == 0 and traces.gestures == 0:
            return
        raise ReplayWouldEraseHumanActsError(
            "Rejouer effacerait des gestes que le journal ne contient pas : des consolations "
            "déjà remises, des gestes comptés. Les faire entrer au ledger, ou forcer en sachant "
            "ce qui est perdu.",
            details={"tenant_id": str(tenant_id), **traces.as_details()},
        )
