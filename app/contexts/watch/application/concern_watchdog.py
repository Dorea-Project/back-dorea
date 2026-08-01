"""Ce qui veille sur le signalement par un tiers : l'escalade, le déversoir, la calibration.

Trois services, un seul fil : **une intuition non suivie d'un contact est un problème de
responsable, pas de membre.**

---

**L'escalade change de sujet**, et c'est propre à cette source. Escalader vers le pasteur *à
propos du membre* n'aurait aucun sens : il n'a aucune base pour agir, il sait seulement que
quelqu'un a ressenti quelque chose. Ce qui doit remonter, c'est l'**engagement non tenu** — et
l'action du pasteur est d'appeler le responsable, pas la personne.

Formulé comme un besoin d'aide, jamais comme un reproche : un responsable qui ne tient pas ses
engagements est le plus souvent un responsable débordé.

---

**Le déversoir.** Un responsable débordé peut taper sur dix personnes en trente secondes ; sa
conscience est tranquille, il n'a appelé personne.

| Comportement | Lecture |
|---|---|
| 10 intuitions, 10 contacts | **excellent responsable — ne jamais le freiner** |
| 10 intuitions, 0 contact | il se décharge |

> Le tell est le **ratio**, jamais le volume. Un seuil sur le volume punirait exactement les
> meilleurs.

---

**La calibration.** L'intuition est la seule source qui se vérifie : l'émetteur a une croyance
préalable, et la résolution dit si elle était juste. Ce signal n'existe nulle part ailleurs dans
le produit — et il reste **agrégé au tenant**. Un taux de justesse attaché à une personne serait
un score sur un responsable, c'est-à-dire exactement la frontière que le moteur s'interdit : on
apprend sur les seuils d'une église, jamais sur quelqu'un.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID, uuid4

from app.contexts.watch.application.ports import SignalStore
from app.contexts.watch.application.referent_ports import (
    CoverageGapStore,
    WatchParameterRepository,
)
from app.contexts.watch.domain.coverage import CoverageGapRecord
from app.contexts.watch.domain.effects import CasePriority, CoverageGap, CoverageScope
from app.contexts.watch.domain.parameters import WatchParam
from app.contexts.watch.domain.signal import SignalOutcome


class EscalateStaleConcerns:
    """Bloc 6 — ce qui a été promis et jamais commencé remonte au pasteur, sur le responsable."""

    def __init__(
        self,
        signals: SignalStore,
        gaps: CoverageGapStore,
        params: WatchParameterRepository,
        *,
        clock,
        id_factory=uuid4,
    ) -> None:
        self._signals = signals
        self._gaps = gaps
        self._params = params
        self._clock = clock
        self._new_id = id_factory

    async def execute(self, *, tenant_id: UUID) -> list[UUID]:
        """Renvoie les responsables sur lesquels un défaut vient d'être consigné."""
        now = self._clock()
        days = await self._params.get_int(tenant_id, WatchParam.CONCERN_ESCALATION_DAYS)
        stale = await self._signals.stale_concerns(
            tenant_id=tenant_id, opened_before=now - timedelta(days=days)
        )

        escalated: list[UUID] = []
        for _signal_id, owner_id, opened_at in stale:
            # Sans propriétaire, il n'y a pas d'engagement à ne pas tenir : ce cas relève du
            # défaut de couverture, déjà consigné à la résolution. Escalader ici accuserait
            # personne et noierait l'écran du pasteur d'un bruit qu'il ne peut pas traiter.
            if owner_id is None:
                continue
            waited = max((now - opened_at).days, days)
            created = await self._gaps.record_once(
                CoverageGapRecord(
                    id=self._new_id(),
                    tenant_id=tenant_id,
                    scope=CoverageScope.PERSON,
                    subject_id=owner_id,  # **le responsable** — jamais le membre
                    gap=CoverageGap.ENGAGEMENT_NOT_KEPT,
                    reason=(
                        f"Une inquiétude signalée il y a {waited} jours n'a donné lieu à "
                        "aucun contact. Cette personne a peut-être besoin d'aide."
                    ),
                    observed_at=now,
                )
            )
            if created:
                escalated.append(owner_id)
        return escalated


@dataclass(frozen=True)
class ConcernRatio:
    """Ce qu'un responsable a signalé, et ce qu'il a effectivement commencé."""

    owner_id: UUID
    raised: int
    contacted: int

    @property
    def contact_rate(self) -> float:
        return self.contacted / self.raised if self.raised else 0.0


class GuardAgainstDumping:
    """Bloc 7 — surveiller le ratio, **jamais le volume**.

    Celui qui demande de l'aide passe devant tout ; celui qui s'organise reste dans la file. Le
    plafond de débit s'applique donc à cette origine — contrairement au déclaré du membre — et
    ce garde-fou est ce qui le rend juste : il distingue le responsable prolifique et fidèle du
    responsable qui se décharge, là où un compteur les confondrait.
    """

    def __init__(
        self,
        signals: SignalStore,
        gaps: CoverageGapStore,
        params: WatchParameterRepository,
        *,
        clock,
        id_factory=uuid4,
    ) -> None:
        self._signals = signals
        self._gaps = gaps
        self._params = params
        self._clock = clock
        self._new_id = id_factory

    async def ratios(self, *, tenant_id: UUID) -> list[ConcernRatio]:
        now = self._clock()
        window = await self._params.get_int(tenant_id, WatchParam.CONCERN_WINDOW_DAYS)
        rows = await self._signals.concern_activity(
            tenant_id=tenant_id, since=now - timedelta(days=window)
        )
        tally: dict[UUID, list[int]] = {}
        for owner_id, contacted in rows:
            if owner_id is None:
                continue
            counts = tally.setdefault(owner_id, [0, 0])
            counts[0] += 1
            counts[1] += 1 if contacted else 0
        return [
            ConcernRatio(owner_id=owner, raised=raised, contacted=contacted)
            for owner, (raised, contacted) in tally.items()
        ]

    async def execute(self, *, tenant_id: UUID) -> list[UUID]:
        now = self._clock()
        floor = await self._params.get_int(tenant_id, WatchParam.CONCERN_VOLUME_FLOOR)
        rate_floor = (
            await self._params.get_int(
                tenant_id, WatchParam.CONCERN_CONTACT_RATE_FLOOR_PERCENT
            )
            / 100
        )

        flagged: list[UUID] = []
        for ratio in await self.ratios(tenant_id=tenant_id):
            # Le volume seul ne dit **rien** : il n'est ici qu'un seuil de lisibilité. En
            # dessous, le ratio porte sur trop peu de cas pour vouloir dire quelque chose.
            if ratio.raised < floor or ratio.contact_rate >= rate_floor:
                continue
            created = await self._gaps.record_once(
                CoverageGapRecord(
                    id=self._new_id(),
                    tenant_id=tenant_id,
                    scope=CoverageScope.PERSON,
                    subject_id=ratio.owner_id,
                    gap=CoverageGap.LEADER_OVERLOADED,
                    reason=(
                        f"Signale beaucoup et contacte peu : {ratio.raised} inquiétudes, "
                        f"{ratio.contacted} contacts. A probablement besoin d'aide."
                    ),
                    observed_at=now,
                )
            )
            if created:
                flagged.append(ratio.owner_id)
        return flagged


# Une intuition s'est révélée **juste** dès lors que le cas s'est clos sur autre chose que « j'ai
# pris contact, tout allait bien ». C'est la seule issue du vocabulaire qui dit que la croyance
# préalable était fausse ; toutes les autres décrivent une situation réelle qu'il a fallu porter.
UNCONFIRMED_OUTCOMES: frozenset[SignalOutcome] = frozenset(
    {SignalOutcome.NOTHING_TO_REPORT}
)


@dataclass(frozen=True)
class ConcernPrecision:
    """La calibration d'une **église**. Aucun champ ne descend à la personne, et c'est le sujet.

    À 80 % de justesse, c'est la source la plus précieuse du produit ; à 20 %, c'est un déversoir
    et le plafond doit se resserrer. Dans les deux cas la décision porte sur un seuil, pas sur
    quelqu'un."""

    tenant_id: UUID
    closed: int
    confirmed: int

    @property
    def precision(self) -> float | None:
        """None tant qu'aucune inquiétude n'est close : un taux sur zéro cas est un mensonge."""
        return self.confirmed / self.closed if self.closed else None


class MeasureConcernPrecision:
    def __init__(self, signals: SignalStore, params: WatchParameterRepository, *, clock) -> None:
        self._signals = signals
        self._params = params
        self._clock = clock

    async def execute(self, *, tenant_id: UUID) -> ConcernPrecision:
        """Le cas particulier de `OutcomeJudge` — **même requête, même filtre**.

        Les deux lectures de « précision » ne peuvent pas diverger, parce qu'il n'y a qu'une
        source. Deux nombres qui portent le même nom et se contredisent finissent toujours par
        être arbitrés par celui qui arrange."""
        now = self._clock()
        window = await self._params.get_int(tenant_id, WatchParam.CONCERN_WINDOW_DAYS)
        rows = await self._signals.closed_cases_since(
            tenant_id=tenant_id, since=now - timedelta(days=window)
        )
        outcomes = [
            outcome
            for origin, outcome in rows
            if CasePriority(origin) is CasePriority.CONCERN
        ]
        confirmed = sum(
            1 for o in outcomes if SignalOutcome(o) not in UNCONFIRMED_OUTCOMES
        )
        return ConcernPrecision(
            tenant_id=tenant_id, closed=len(outcomes), confirmed=confirmed
        )
