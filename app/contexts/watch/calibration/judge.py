"""La **vérité terrain** — ce que les humains ont constaté, lu sans rien interpréter de neuf.

Le moteur ne peut pas savoir tout seul s'il a eu raison. Ce sont les responsables qui le lui
disent, en fermant leurs cas avec une issue **choisie** — et c'est pour ça qu'aucune issue n'est
pré-cochée : une valeur par défaut deviendrait le rangement automatique, et la mesure ne mesurerait
plus que la paresse du formulaire.

Trois verdicts, et chacun pointe vers un réglage différent :

| Ce qu'on observe | Ce que ça dit | Ce que ça décide |
| :-- | :-- | :-- |
| « contact pris, rien à signaler » | la détection s'est **trompée** | seuil trop sensible |
| inquiétude d'un tiers **confirmée** | un humain a vu **avant** le moteur | seuil trop lent |
| cas jamais ouvert par son destinataire | il est **débordé**, pas indifférent | plafond trop haut |

**Ce troisième est le seul qui anticipe.** `first_contact_at` est la métrique reine, mais elle est
retardée : elle confirme après coup. Le taux d'ignorés se lit dès la deuxième semaine, et c'est le
seul indicateur qui voit venir l'abandon avant qu'il soit consommé.

**Aucun de ces nombres ne descend à la personne.** Ils sont par église et par origine du dire — ce
qui est déjà le grain le plus fin qui ait du sens : on calibre une détection, pas des gens.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from app.contexts.watch.application.concern_watchdog import UNCONFIRMED_OUTCOMES
from app.contexts.watch.application.ports import SignalStore
from app.contexts.watch.application.referent_ports import WatchParameterRepository
from app.contexts.watch.domain.effects import CasePriority
from app.contexts.watch.domain.parameters import WatchParam
from app.contexts.watch.domain.signal import SignalOutcome

# Au-delà, un cas qu'aucun destinataire n'a ouvert est un cas ignoré, pas un cas récent.
IGNORED_AFTER_DAYS = 7


@dataclass(frozen=True)
class OriginVerdict:
    """Ce que le terrain dit d'une **origine de détection**. Jamais de quelqu'un."""

    origin: CasePriority
    closed: int = 0
    confirmed: int = 0  # la détection avait vu juste
    false_positives: int = 0  # « contact pris, rien à signaler »

    @property
    def precision(self) -> float | None:
        """`None` quand il n'y a rien à mesurer — et c'est une réponse, pas un zéro.

        Zéro cas fermé ne veut pas dire zéro justesse : ça veut dire qu'on ne sait pas encore.
        Rendre `0.0` ferait descendre une moyenne et déclencherait des propositions sur du vide."""
        return None if self.closed == 0 else self.confirmed / self.closed


@dataclass(frozen=True)
class GroundTruth:
    """Ce qu'une église a réellement constaté sur une fenêtre. Agrégé, jamais nominatif."""

    tenant_id: UUID
    window_days: int
    # Le début de la fenêtre, calculé **une fois**. Tout ce qui suit dans la passe — la simulation
    # comprise — travaille sur le même instant : deux lectures d'horloge à quelques secondes
    # d'écart suffiraient à ce que le contrefactuel ne porte pas sur les mêmes cas que la mesure.
    since: datetime
    by_origin: tuple[OriginVerdict, ...] = ()
    missed_detections: int = 0  # un tiers a vu avant le moteur
    ignored: int = 0  # jamais ouverts par leur destinataire
    on_shoulders: int = 0  # ce qui pesait sur quelqu'un pendant la fenêtre

    def verdict_for(self, origin: CasePriority) -> OriginVerdict | None:
        return next((v for v in self.by_origin if v.origin is origin), None)

    @property
    def ignored_rate(self) -> float | None:
        return None if self.on_shoulders == 0 else self.ignored / self.on_shoulders


class OutcomeJudge:
    """Lit les issues et les dates. **N'écrit rien, ne juge personne.**"""

    def __init__(
        self, signals: SignalStore, params: WatchParameterRepository, *, clock
    ) -> None:
        self._signals = signals
        self._params = params
        self._clock = clock

    async def execute(self, *, tenant_id: UUID) -> GroundTruth:
        now = self._clock()
        window = await self._params.get_int(tenant_id, WatchParam.CONCERN_WINDOW_DAYS)
        since = now - timedelta(days=window)
        rows = await self._signals.closed_cases_since(tenant_id=tenant_id, since=since)

        tallies: dict[CasePriority, list[int]] = {}
        missed = 0
        for raw_origin, raw_outcome in rows:
            origin = CasePriority(raw_origin)
            outcome = SignalOutcome(raw_outcome)
            counts = tallies.setdefault(origin, [0, 0, 0])
            counts[0] += 1
            if outcome in UNCONFIRMED_OUTCOMES:
                counts[2] += 1
            else:
                counts[1] += 1
                if origin is CasePriority.CONCERN:
                    # **Un humain a vu avant le moteur.** Une inquiétude signalée qui se confirme
                    # est, littéralement, une détection que les seuils ont manquée — la seule
                    # mesure du produit qui dise « tu étais trop lent » plutôt que « tu criais ».
                    missed += 1

        ignored, on_shoulders = await self._signals.ignored_ratio(
            tenant_id=tenant_id, older_than=now - timedelta(days=IGNORED_AFTER_DAYS)
        )
        return GroundTruth(
            tenant_id=tenant_id,
            window_days=window,
            since=since,
            by_origin=tuple(
                OriginVerdict(
                    origin=origin, closed=c[0], confirmed=c[1], false_positives=c[2]
                )
                for origin, c in sorted(tallies.items(), key=lambda kv: kv[0].value)
            ),
            missed_detections=missed,
            ignored=ignored,
            on_shoulders=on_shoulders,
        )
