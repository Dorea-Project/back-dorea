"""Ce que la boucle froide **propose** — et ce qu'elle n'a jamais le droit de faire seule.

Une proposition dit : *pour cette église, ce paramètre devrait valoir tant, et voici ce qui me le
fait dire.* Rien de plus. Elle n'écrit aucun cas, ne touche à aucune personne, et son application
dépend du régime de l'église.

**L'interprétation du terrain est contre-intuitive, et c'est le cœur de ce fichier :**

> Si huit signaux arrivent par semaine pour une capacité de traitement de trois, le problème n'est
> pas que le plafond est trop bas. C'est que **les seuils de détection sont trop sensibles.**

Un arriéré permanent est le symptôme d'une détection trop bavarde. On remonte alors le seuil — on
ne remonte **pas** le plafond, sinon on noie le responsable pour faire disparaître un indicateur.

**Les bornes sont dures.** Une proposition hors bornes n'est jamais appliquée seule, quel que soit
le régime : elle attend un humain. C'est ce qui empêche une dérive lente de mener quelque part où
personne n'aurait accepté d'aller d'un coup.

Un **balayage borné**, pas un optimiseur : l'espace de paramètres est minuscule, et une descente de
gradient sur trois entiers serait de la mise en scène.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from app.contexts.watch.application.ports import RegimeStore
from app.contexts.watch.application.referent_ports import WatchParameterRepository
from app.contexts.watch.calibration.judge import GroundTruth
from app.contexts.watch.calibration.ports import (
    CalibrationProposalStore,
    WatchParameterWriter,
)
from app.contexts.watch.domain.effects import CasePriority
from app.contexts.watch.domain.parameters import WatchParam
from app.contexts.watch.domain.regime import TenantRegime


class ProposalStatus(StrEnum):
    PENDING = "pending"  # attend un humain
    APPLIED = "applied"
    REJECTED = "rejected"


# Les bornes dures, par paramètre. Même patron que `DEFAULTS` : la valeur vit en code, une église
# pourra la surcharger en table le jour où l'une d'elles aura une raison de différer.
#
# Elles ne sont pas décoratives : `ABSENCE_OCCURRENCES_THRESHOLD` à 1 ferait crier le moteur sur
# une seule absence, à 12 il ne dirait plus jamais rien. `OPEN_CASES_CAP` à 20 noierait le
# responsable que le plafond existe pour protéger.
BOUNDS: dict[WatchParam, tuple[int, int]] = {
    WatchParam.ABSENCE_OCCURRENCES_THRESHOLD: (2, 6),
    WatchParam.OPEN_CASES_CAP: (3, 10),
}

# En dessous, il n'y a rien à lire : proposer sur trois cas fermés, c'est calibrer du bruit.
MIN_EVIDENCE = 5
# Une détection qui se trompe plus d'une fois sur deux crie trop fort.
PRECISION_FLOOR = 0.5
# Un cas sur trois jamais ouvert : le responsable est débordé, pas indifférent.
IGNORED_CEILING = 0.33


@dataclass(frozen=True)
class CalibrationProposal:
    """Un paramètre, sa valeur actuelle, celle qu'on propose — et **pourquoi**, en clair.

    `evidence` est une phrase que le pasteur lit et peut contester. Une proposition qu'on ne sait
    pas justifier est une proposition qu'on applique par confiance, et la confiance ne se calibre
    pas."""

    id: UUID
    tenant_id: UUID
    param: WatchParam
    current: int
    proposed: int
    evidence: str
    status: ProposalStatus = ProposalStatus.PENDING
    # **Le seul identifiant de personne de tout ce paquet**, et il ne mesure rien : c'est la
    # signature d'une décision, pas l'observation de quelqu'un. La frontière du module est là —
    # une personne peut être l'*auteur* d'un réglage, jamais son *sujet*. Un test la tient.
    decided_by_account_id: UUID | None = None
    decided_at: datetime | None = None

    @property
    def within_bounds(self) -> bool:
        low, high = BOUNDS.get(self.param, (self.proposed, self.proposed))
        return low <= self.proposed <= high

    def auto_appliable(self, regime: TenantRegime) -> bool:
        """Seul `STEADY` applique seul, et seulement dans les bornes.

        En `SHADOW` l'église n'a pas encore accepté que Dorea parle — lui changer ses seuils dans
        le dos serait pire qu'inutile. En `ASSISTED`, chaque proposition attend une approbation."""
        return regime is TenantRegime.STEADY and self.within_bounds


class Proposer:
    """Croise la vérité terrain et les seuils courants. **Trois règles, pas un modèle.**"""

    def __init__(self, params: WatchParameterRepository, *, id_factory=uuid4) -> None:
        self._params = params
        self._new_id = id_factory

    async def execute(self, *, truth: GroundTruth) -> list[CalibrationProposal]:
        tenant_id = truth.tenant_id
        threshold = await self._params.get_int(
            tenant_id, WatchParam.ABSENCE_OCCURRENCES_THRESHOLD
        )
        cap = await self._params.get_int(tenant_id, WatchParam.OPEN_CASES_CAP)

        proposals: list[CalibrationProposal] = []
        absence = truth.verdict_for(CasePriority.ABSENCE)

        # 1 — la détection crie trop fort : plus d'un cas d'absence sur deux ne tenait pas.
        if (
            absence is not None
            and absence.closed >= MIN_EVIDENCE
            and (absence.precision or 0) < PRECISION_FLOOR
        ):
            proposals.append(
                self._proposal(
                    tenant_id,
                    WatchParam.ABSENCE_OCCURRENCES_THRESHOLD,
                    threshold,
                    threshold + 1,
                    f"{absence.false_positives} cas d'absence sur {absence.closed} se sont "
                    "fermés sur « contact pris, rien à signaler ».",
                )
            )

        # 2 — le moteur arrive après les humains : ils signalent ce qu'il n'a pas vu.
        elif truth.missed_detections >= MIN_EVIDENCE:
            proposals.append(
                self._proposal(
                    tenant_id,
                    WatchParam.ABSENCE_OCCURRENCES_THRESHOLD,
                    threshold,
                    threshold - 1,
                    f"{truth.missed_detections} inquiétudes signalées par des tiers se sont "
                    "confirmées : quelqu'un a vu avant le moteur.",
                )
            )

        # 3 — le débit, et **seulement** quand la détection est juste. Sinon on remonterait le
        # plafond pour absorber du bruit, c'est-à-dire qu'on noierait le responsable pour faire
        # disparaître un indicateur.
        rate = truth.ignored_rate
        if (
            rate is not None
            and rate > IGNORED_CEILING
            and truth.on_shoulders >= MIN_EVIDENCE
            and not proposals
        ):
            proposals.append(
                self._proposal(
                    tenant_id,
                    WatchParam.OPEN_CASES_CAP,
                    cap,
                    cap - 1,
                    f"{truth.ignored} cas sur {truth.on_shoulders} n'ont jamais été ouverts "
                    "par leur destinataire.",
                )
            )
        return proposals

    def _proposal(
        self, tenant_id: UUID, param: WatchParam, current: int, proposed: int, why: str
    ) -> CalibrationProposal:
        return CalibrationProposal(
            id=self._new_id(),
            tenant_id=tenant_id,
            param=param,
            current=current,
            proposed=proposed,
            evidence=why,
        )


@dataclass(frozen=True)
class AppliedProposal:
    applied: bool
    reason: str


class ApplyProposal:
    """L'écriture du `WatchParam` — après approbation, ou seule dans les bornes en `STEADY`.

    Le **seul** endroit du produit où la boucle froide touche à quelque chose."""

    def __init__(
        self,
        params: WatchParameterWriter,
        regimes: RegimeStore,
        proposals: CalibrationProposalStore | None = None,
        *,
        clock=None,
    ) -> None:
        self._params = params
        self._regimes = regimes
        self._proposals = proposals
        self._clock = clock

    async def execute(
        self, *, proposal: CalibrationProposal, approved_by: UUID | None = None
    ) -> AppliedProposal:
        if not proposal.within_bounds:
            # Hors bornes : jamais appliquée seule, **même approuvée par le régime**. Un humain
            # peut toujours écrire la valeur à la main — mais il le fera en le sachant.
            return AppliedProposal(False, "hors des bornes dures")

        regime = await self._regimes.regime_of(proposal.tenant_id)
        if approved_by is None and not proposal.auto_appliable(regime):
            return AppliedProposal(False, "attend une approbation")

        await self._params.set_int(
            tenant_id=proposal.tenant_id, param=proposal.param, value=proposal.proposed
        )
        if self._proposals is not None:
            await self._proposals.save(
                replace(
                    proposal,
                    status=ProposalStatus.APPLIED,
                    decided_by_account_id=approved_by,
                    decided_at=self._clock() if self._clock else None,
                )
            )
        return AppliedProposal(True, "appliquée")
