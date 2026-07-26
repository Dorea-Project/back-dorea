"""Route **Plateforme** — le dispatcher du fan-out asynchrone (appelé par un cron externe).

Envoie les notifications planifiées dont l'heure est venue. Gardée par le **jeton de service
Plateforme** (`require_platform_token`) — c'est de l'infrastructure, pas une action d'église.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.contexts.notifications.interface.dependencies import DispatchDep
from app.contexts.tenant.interface.dependencies import require_platform_token

router = APIRouter(dependencies=[Depends(require_platform_token)])


class DispatchResult(BaseModel):
    dispatched: int


@router.post(
    "/notifications/dispatch",
    response_model=DispatchResult,
    summary="Dispatcher les notifications planifiées dues (appelé périodiquement par un cron)",
)
async def dispatch(command: DispatchDep) -> DispatchResult:
    return DispatchResult(dispatched=await command.run())
