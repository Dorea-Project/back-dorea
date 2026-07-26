"""Routes **mobile** du module Billing — la personne gère son propre compte de facturation.

Enregistrer une carte prépayée Visa ouvre le tier Business (non facturé) ; la retirer revient au
gratuit ; consulter son statut. JWT mobile.
"""

from fastapi import APIRouter

from app.contexts.auth.interface.dependencies import CurrentActor
from app.contexts.billing.interface.dependencies import (
    AddPaymentCardDep,
    GetBusinessStatusDep,
    RemovePaymentCardDep,
)
from app.contexts.billing.interface.schemas import AddCardBody, BusinessStatusView

router = APIRouter()


@router.get(
    "/status",
    response_model=BusinessStatusView,
    summary="Mon tier de compte (gratuit / business)",
)
async def status(
    actor: CurrentActor,
    query: GetBusinessStatusDep,
) -> BusinessStatusView:
    dto = await query.execute(actor_account_id=actor.account_id)
    return BusinessStatusView.from_dto(dto)


@router.post(
    "/card",
    response_model=BusinessStatusView,
    summary="Enregistrer ma carte prépayée Visa → activer le compte Business (non facturé)",
)
async def add_card(
    payload: AddCardBody,
    actor: CurrentActor,
    command: AddPaymentCardDep,
) -> BusinessStatusView:
    dto = await command.execute(
        actor_account_id=actor.account_id,
        brand=payload.brand,
        last4=payload.last4,
        prepaid=payload.prepaid,
        exp_month=payload.exp_month,
        exp_year=payload.exp_year,
        provider_token=payload.provider_token,
    )
    return BusinessStatusView.from_dto(dto)


@router.post(
    "/card/remove",
    response_model=BusinessStatusView,
    summary="Retirer ma carte → revenir au tier gratuit",
)
async def remove_card(
    actor: CurrentActor,
    command: RemovePaymentCardDep,
) -> BusinessStatusView:
    dto = await command.execute(actor_account_id=actor.account_id)
    return BusinessStatusView.from_dto(dto)
