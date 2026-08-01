"""La surface du **rodage et du calibrage** — ce que le pasteur voit, et les décisions qu'il pose.

Quatre routes, et elles forment le parcours entier d'une église qui découvre Dorea :

1. *« Voici ce que Dorea aurait signalé »* — pendant l'observation, tout est détecté et rien
   n'atteint un responsable. Sans cet écran, le rodage serait indiscernable d'un produit en panne ;
2. *« Laissez Dorea parler »* — le moment où l'église accepte de recevoir des cas sur ses membres,
   et d'en répondre. Un acte de gouvernance, daté et signé ;
3. *« Voici ce que la mesure suggère »* — les propositions de seuil en attente, chacune avec la
   phrase qui la justifie, donc contestable ;
4. *« J'accepte »* ou *« je refuse »* — et **le refus vaut autant** : il est enregistré, et la
   proposition ne revient pas le lendemain.

Cookie de session backoffice ; l'autorité est vérifiée **dans les use cases**, comme partout
ailleurs — église-entière pour lire, propriété de l'église pour décider.
"""

from uuid import UUID

from fastapi import APIRouter

from app.contexts.auth.interface.backoffice_dependencies import CurrentBackofficeUser
from app.contexts.watch.interface.dependencies import (
    BuildShadowReportDep,
    DecideOnProposalDep,
    LetDoreaSpeakDep,
    ListProposalsDep,
)
from app.contexts.watch.interface.schemas import (
    CalibrationProposalView,
    DecideOnProposalBody,
    LetDoreaSpeakBody,
    RegimeView,
    ShadowReportView,
)

router = APIRouter()


@router.get(
    "/tenants/{tenant_id}/watch/shadow-report",
    response_model=ShadowReportView,
    summary="Voici ce que Dorea aurait signalé — pendant que l'église observe",
)
async def shadow_report(
    tenant_id: UUID,
    actor: CurrentBackofficeUser,
    query: BuildShadowReportDep,
) -> ShadowReportView:
    return ShadowReportView.of(
        await query.execute(tenant_id=tenant_id, actor_account_id=actor.account_id)
    )


@router.post(
    "/tenants/{tenant_id}/watch/regime",
    response_model=RegimeView,
    summary="Laisser Dorea parler — l'église accepte de recevoir des cas sur ses membres",
)
async def set_regime(
    tenant_id: UUID,
    payload: LetDoreaSpeakBody,
    actor: CurrentBackofficeUser,
    command: LetDoreaSpeakDep,
) -> RegimeView:
    regime = await command.execute(
        tenant_id=tenant_id,
        actor_account_id=actor.account_id,
        regime=payload.regime,
    )
    return RegimeView(regime=regime.value, emits=regime.emits)


@router.get(
    "/tenants/{tenant_id}/watch/calibration/proposals",
    response_model=list[CalibrationProposalView],
    summary="Ce que la mesure suggère de changer — avec ce qui le lui fait dire",
)
async def pending_proposals(
    tenant_id: UUID,
    actor: CurrentBackofficeUser,
    query: ListProposalsDep,
) -> list[CalibrationProposalView]:
    return [
        CalibrationProposalView.of(p)
        for p in await query.execute(
            tenant_id=tenant_id, actor_account_id=actor.account_id
        )
    ]


@router.post(
    "/tenants/{tenant_id}/watch/calibration/proposals/{proposal_id}",
    response_model=CalibrationProposalView,
    summary="Accepter ou refuser une proposition de seuil",
)
async def decide_on_proposal(
    tenant_id: UUID,
    proposal_id: UUID,
    payload: DecideOnProposalBody,
    actor: CurrentBackofficeUser,
    command: DecideOnProposalDep,
) -> CalibrationProposalView:
    return CalibrationProposalView.of(
        await command.execute(
            proposal_id=proposal_id,
            tenant_id=tenant_id,
            actor_account_id=actor.account_id,
            accept=payload.accept,
        )
    )
