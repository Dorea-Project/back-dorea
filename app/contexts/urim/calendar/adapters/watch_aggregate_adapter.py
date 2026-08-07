"""Le seul endroit d'Urim autorisé à importer hors d'Urim (Structure §1).

Cet adaptateur traduit la lecture non nominative de la veille en `AggregateSignal`. Il ne
franchit la frontière que dans **un sens** : Urim lit, Urim n'écrit jamais dans la veille —
une préparation ne crée ni fait, ni cas, ni signal.

⚠️ Ce qui traverse ici est destiné à **l'affichage seul**. Aucun étage du moteur ne lit
`deps.context` : un texte se choisit sur le texte, pas sur les tourments de l'assemblée. Le
test bytecode (`test_aucun_etage_ne_lit_le_contexte_ecclesial`) l'interdit par programme.

**Le signal informe l'homme. L'homme commande la machine. Jamais le signal ne commande la
machine.**
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from app.contexts.urim.calendar.domain.models import AggregateSignal, EcclesialEvent
from app.contexts.watch.application.aggregates import AggregateReader

#: L'origine d'un cas est un code interne à la veille ; l'écran du pasteur lit du français.
_LIBELLES: dict[str, str] = {
    "declared": "personnes qui se sont signalées elles-mêmes",
    "concern": "personnes signalées par un proche",
    "absence": "personnes sans nouvelles",
    "announcement": "personnes touchées par une annonce",
    "deadline": "échéances de suivi",
    "returned": "personnes revenues",
    "deceased": "deuils",
}


class WatchAggregateContext:
    """`EcclesialContextPort` adossé à la veille — **comptes seuls**.

    Les événements déclarés ne viennent pas d'ici : le calendrier vit hors de `watch`
    (`attendance`, `events`), donc l'adaptateur d'événements de la spec n'a pas lieu d'être.
    """

    def __init__(self, aggregates: AggregateReader, *, window_days: int = 30) -> None:
        self._aggregates = aggregates
        self._window_days = window_days

    def events_between(
        self, church_id: UUID, start: date, end: date
    ) -> tuple[EcclesialEvent, ...]:
        return ()

    async def aggregate_signals(self, church_id: UUID) -> tuple[AggregateSignal, ...]:
        counts = await self._aggregates.counts_by_origin(
            church_id, window_days=self._window_days
        )
        # `AggregateSignal` refuse lui-même tout compte sous le seuil : deux gardes
        # indépendantes (le `HAVING` en base, l'invariant du domaine) plutôt qu'une.
        return tuple(
            AggregateSignal(
                topic=_LIBELLES.get(count.topic, count.topic),
                headcount=count.headcount,
                window_days=count.window_days,
            )
            for count in counts
        )
