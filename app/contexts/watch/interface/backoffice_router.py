"""La surface du **rodage** — ce que le pasteur voit, et la décision qu'il pose.

Deux routes, et elles forment le parcours entier d'une église qui découvre Dorea :

1. *« Voici ce que Dorea aurait signalé »* — pendant l'observation, tout est détecté et rien
   n'atteint un responsable. Sans cet écran, le rodage serait indiscernable d'un produit en panne ;
2. *« Laissez Dorea parler »* — le moment où l'église accepte de recevoir des cas sur ses membres,
   et d'en répondre. Un acte de gouvernance, daté et signé.

Cookie de session backoffice ; l'autorité est vérifiée **dans les use cases**, comme partout
ailleurs — église-entière pour lire, propriété de l'église pour décider.
"""

from uuid import UUID

from fastapi import APIRouter

from app.contexts.auth.interface.backoffice_dependencies import CurrentBackofficeUser
from app.contexts.watch.interface.dependencies import (
    BuildShadowReportDep,
    LetDoreaSpeakDep,
)
from app.contexts.watch.interface.schemas import (
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
