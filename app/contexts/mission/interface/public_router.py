"""Routes **publiques** de la Mission (M9) — la carte, sans compte.

Celui qui reçoit le lien n'est pas (encore) membre : le **code EST l'entrée**. Il voit la carte,
réagit (touché/édifié/Amen, anonyme) et peut **accepter** (laisser un contact → devient Seeker).
"""

from fastapi import APIRouter, status

from app.contexts.mission.interface.dependencies import (
    AcceptInvitationDep,
    GetCardDep,
    ReactToCardDep,
)
from app.contexts.mission.interface.schemas import (
    AcceptRequest,
    AcceptResponse,
    MissionCardResponse,
    ReactRequest,
)

router = APIRouter()


@router.get(
    "/link/{code}",
    response_model=MissionCardResponse,
    summary="Voir la carte d'invitation (public) — qui invite, l'église, le message, le lieu",
)
async def get_card(code: str, query: GetCardDep) -> MissionCardResponse:
    dto = await query.execute(code=code)
    return MissionCardResponse.from_dto(dto)


@router.post(
    "/link/{code}/react",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Réagir à la carte (touché / édifié / Amen) — léger, anonyme",
)
async def react(code: str, payload: ReactRequest, command: ReactToCardDep) -> None:
    await command.execute(code=code, kind=payload.kind)


@router.post(
    "/link/{code}/accept",
    response_model=AcceptResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Accepter l'invitation (laisser un contact) → devient un chercheur accompagné",
)
async def accept(
    code: str, payload: AcceptRequest, command: AcceptInvitationDep
) -> AcceptResponse:
    seeker_id = await command.execute(code=code, name=payload.name, phone=payload.phone)
    return AcceptResponse(seeker_id=seeker_id)
