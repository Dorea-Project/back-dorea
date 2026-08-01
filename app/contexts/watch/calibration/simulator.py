"""Chiffrer une proposition **avant** de la poser — et dire ce qu'elle coûterait.

Une proposition qui ne dit que ce qu'elle fait gagner est une publicité. Celle-ci dit les deux :

> *« À 4 rencontres, 19 des 31 cas ne se seraient pas ouverts : 5 des 6 fermés sur "rien à
> signaler" — et 1 qui s'est confirmé. »*

Cette dernière phrase est la seule qui compte. Un seuil plus haut fait toujours moins de bruit ;
la question n'a jamais été là. La question est **qui on ne va plus voir**, et personne ne peut y
répondre à la place du pasteur.

---

**Le simulateur qu'on n'a pas eu à construire.** Le plan de chantier en prévoyait un lourd :
rejouer le journal entier contre des seuils alternatifs, avec des dépôts en mémoire de qualité
production. Il s'est avéré inutile — `CheckFiredV1` écrit `occurrences` et `threshold` **dans le
payload du fait**, précisément pour rester pur et déterministe. Le contrefactuel se lit donc dans
le journal, sans rejouer quoi que ce soit. La discipline d'un interpreter sans I/O a payé une
seconde fois, là où on ne l'attendait pas.

---

**Ce qu'il sait exactement, et ce dont il ne fait qu'une borne.** L'ouverture réelle a trois
conditions : un seuil atteint, et aucune neutralisation en cours. Le payload porte les deux
premières ; la neutralisation, non.

- **seuil plus haut → exact.** Le nouvel ensemble est un sous-ensemble de ce qui s'est ouvert, et
  pour ceux-là on sait déjà qu'aucune neutralisation ne courait.
- **seuil plus bas → une borne haute.** Il ouvrirait *au plus* tant de cas : certains auraient été
  étouffés par un deuil ou un voyage qu'on ne relit pas ici.

Le champ `exact` porte cette différence jusqu'à l'écran. Un nombre dont on ne sait plus s'il est
une mesure ou une estimation finit toujours par être lu comme une mesure.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.contexts.watch.application.concern_watchdog import UNCONFIRMED_OUTCOMES
from app.contexts.watch.calibration.ports import AbsenceEvidenceReader
from app.contexts.watch.domain.signal import SignalOutcome


@dataclass(frozen=True)
class SimulationResult:
    """Ce qu'un seuil aurait donné. **Deux nombres, et le second est le prix.**"""

    threshold: int
    opened_now: int = 0
    opened_then: int = 0
    spared_noise: int = 0  # cas fermés sur « rien à signaler » qui ne se seraient pas ouverts
    missed_real: int = 0  # cas confirmés qu'on n'aurait **pas** vus — le coût
    exact: bool = True

    @property
    def sentence(self) -> str:
        """La phrase que le pasteur lit. Elle **finit** par ce qu'on perd, jamais par ce qu'on
        gagne : l'ordre d'une phrase est ce qu'on en retient."""
        avoided = self.opened_now - self.opened_then
        about = "" if self.exact else "au plus "
        head = (
            f"À {self.threshold}, {about}{avoided} des {self.opened_now} cas ne se seraient "
            "pas ouverts"
        )
        if self.missed_real == 0:
            return (
                f"{head} — dont {self.spared_noise} fermés sur « rien à signaler », "
                "et aucun cas confirmé."
            )
        return (
            f"{head} : {self.spared_noise} fermés sur « rien à signaler », "
            f"mais {self.missed_real} qui se sont confirmés."
        )


class Simulator:
    """Lit le journal et les issues. **N'écrit rien**, et ne choisit rien non plus.

    Il chiffre ; c'est le `Proposer` qui propose et un humain qui tranche. Un simulateur qui
    choisirait serait un optimiseur, et un optimiseur sur trois entiers arbitrerait en silence un
    compromis — moins de bruit contre des gens qu'on ne voit plus — qui n'est pas le sien."""

    def __init__(self, evidence: AbsenceEvidenceReader) -> None:
        self._evidence = evidence

    async def execute(
        self, *, tenant_id: UUID, candidate: int, since: datetime
    ) -> SimulationResult:
        rows = await self._evidence.absence_evidence(tenant_id=tenant_id, since=since)
        if not rows:
            return SimulationResult(threshold=candidate)

        # Le seuil en vigueur au moment du tir, tel que le fait le porte. On ne relit pas la
        # valeur d'aujourd'hui : elle a pu bouger depuis, et le contrefactuel porterait alors sur
        # une histoire qui n'a pas eu lieu.
        lowering = any(candidate < row.threshold for row in rows)

        opened_then = spared = missed = 0
        for row in rows:
            if row.occurrences >= candidate:
                opened_then += 1
                continue
            # Ce cas ne se serait pas ouvert. Reste à savoir ce qu'il valait.
            if row.outcome is None:
                continue  # encore vivant : personne ne sait encore, et on ne devine pas
            if SignalOutcome(row.outcome) in UNCONFIRMED_OUTCOMES:
                spared += 1
            else:
                missed += 1

        return SimulationResult(
            threshold=candidate,
            opened_now=len(rows),
            opened_then=opened_then,
            spared_noise=spared,
            missed_real=missed,
            exact=not lowering,
        )
