"""La passe froide, et l'écran où un humain tranche.

Trois services, et l'ordre entre eux est tout le régime hybride :

1. **`RunCalibrationPass`** — lit la vérité terrain, propose, enregistre, et applique **ce que le
   régime lui permet d'appliquer**. En `SHADOW` et `ASSISTED`, elle ne fait qu'écrire des
   propositions en attente ; en `STEADY`, celles qui tiennent dans les bornes passent seules.
2. **`ListProposals`** — ce que le pasteur lit : un paramètre, sa valeur, celle qu'on propose, et
   la phrase qui le justifie. Il peut contester chaque proposition parce qu'il peut la relire.
3. **`DecideOnProposal`** — accepter ou refuser. **Un refus vaut autant qu'une acceptation** : il
   est enregistré, daté, signé, et la proposition ne revient pas le lendemain.

**Pourquoi le refus compte.** Une proposition rejetée qui se represente chaque nuit transforme
l'écran en harcèlement, et le pasteur apprend à tout accepter pour que ça s'arrête. Une passe ne
propose donc rien tant qu'une proposition en attente existe sur le même paramètre, et une
proposition décidée ne redevient jamais en attente : c'est la prochaine mesure qui en produira une
neuve, avec des nombres neufs.

**L'autorité, c'est `MANAGE_STAFF`** — la même que pour laisser Dorea parler. Changer un seuil de
détection engage l'église entière : ce n'est pas une lecture pastorale, c'est un acte de
gouvernance, du même ordre que celui qui a autorisé le moteur à s'adresser aux responsables.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from uuid import UUID

from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.iam.domain.permissions import Permission
from app.contexts.watch.calibration.judge import OutcomeJudge
from app.contexts.watch.calibration.ports import CalibrationProposalStore
from app.contexts.watch.calibration.proposal import (
    ApplyProposal,
    CalibrationProposal,
    ProposalStatus,
    Proposer,
)
from app.contexts.watch.domain.errors import WatchError


class ProposalNotFoundError(WatchError):
    """Introuvable, ou déjà tranchée. On ne décide pas deux fois de la même chose."""

    code = "WATCH_PROPOSAL_NOT_FOUND"
    http_status = 404


class ProposalOutOfBoundsError(WatchError):
    """Approuvée, et refusée quand même — par les bornes dures.

    Elle **reste en attente** au lieu de disparaître en silence : ce que le pasteur a demandé n'a
    pas eu lieu, et un écran qui range sans rien changer est pire qu'un écran qui dit non."""

    code = "WATCH_PROPOSAL_OUT_OF_BOUNDS"
    http_status = 409


@dataclass(frozen=True)
class PassResult:
    proposed: int = 0
    applied: int = 0  # ce que le régime a laissé passer tout seul


class RunCalibrationPass:
    """La passe. **Rien de ce qu'elle fait n'atteint une personne** — que des seuils d'église."""

    def __init__(
        self,
        judge: OutcomeJudge,
        proposer: Proposer,
        proposals: CalibrationProposalStore,
        apply: ApplyProposal,
    ) -> None:
        self._judge = judge
        self._proposer = proposer
        self._proposals = proposals
        self._apply = apply

    async def execute(self, *, tenant_id: UUID) -> PassResult:
        truth = await self._judge.execute(tenant_id=tenant_id)
        fresh = await self._proposals.add_all(
            await self._proposer.execute(truth=truth)
        )
        applied = 0
        for proposal in fresh:
            # Sans `approved_by` : seule une église en `STEADY`, et seulement dans les bornes,
            # verra quelque chose bouger ici. Partout ailleurs la proposition reste en attente.
            result = await self._apply.execute(proposal=proposal)
            applied += 1 if result.applied else 0
        return PassResult(proposed=len(fresh), applied=applied)


class ListProposals:
    def __init__(
        self, proposals: CalibrationProposalStore, access: GroupAccessPolicy
    ) -> None:
        self._proposals = proposals
        self._access = access

    async def execute(
        self, *, tenant_id: UUID, actor_account_id: UUID
    ) -> list[CalibrationProposal]:
        await self._access.ensure_church_wide(
            actor_account_id=actor_account_id,
            tenant_id=tenant_id,
            permission=Permission.MANAGE_STAFF,
        )
        return await self._proposals.pending(tenant_id)


class DecideOnProposal:
    """Accepter, ou refuser. Les deux se valent, les deux sont signées."""

    def __init__(
        self,
        proposals: CalibrationProposalStore,
        apply: ApplyProposal,
        access: GroupAccessPolicy,
        *,
        clock,
    ) -> None:
        self._proposals = proposals
        self._apply = apply
        self._access = access
        self._clock = clock

    async def execute(
        self,
        *,
        proposal_id: UUID,
        tenant_id: UUID,
        actor_account_id: UUID,
        accept: bool,
    ) -> CalibrationProposal:
        await self._access.ensure_church_wide(
            actor_account_id=actor_account_id,
            tenant_id=tenant_id,
            permission=Permission.MANAGE_STAFF,
        )
        proposal = await self._proposals.get(
            proposal_id=proposal_id, tenant_id=tenant_id
        )
        if proposal is None or proposal.status is not ProposalStatus.PENDING:
            raise ProposalNotFoundError(
                "Cette proposition n'existe pas, ou a déjà été tranchée."
            )

        if not accept:
            decided = replace(
                proposal,
                status=ProposalStatus.REJECTED,
                decided_by_account_id=actor_account_id,
                decided_at=self._clock(),
            )
            await self._proposals.save(decided)
            return decided

        result = await self._apply.execute(
            proposal=proposal, approved_by=actor_account_id
        )
        if not result.applied:
            raise ProposalOutOfBoundsError(
                f"Cette proposition ne peut pas être appliquée : {result.reason}."
            )
        return replace(
            proposal,
            status=ProposalStatus.APPLIED,
            decided_by_account_id=actor_account_id,
            decided_at=self._clock(),
        )
