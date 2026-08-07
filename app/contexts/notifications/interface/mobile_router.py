"""Routes **mobile** du module Notifications — la personne gère ses appareils. JWT mobile."""

from fastapi import APIRouter, status

from app.contexts.auth.interface.dependencies import CurrentActor
from app.contexts.notifications.interface.dependencies import (
    DeviceRepositoryDep,
    RegisterDeviceDep,
    UnregisterDeviceDep,
)
from app.contexts.notifications.interface.schemas import (
    DeviceListView,
    RegisterDeviceBody,
    UnregisterDeviceBody,
)

router = APIRouter()


@router.post(
    "/devices",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Enregistrer mon appareil (jeton push) pour recevoir les notifications",
)
async def register_device(
    payload: RegisterDeviceBody,
    actor: CurrentActor,
    command: RegisterDeviceDep,
) -> None:
    await command.execute(
        actor_account_id=actor.account_id, token=payload.token, platform=payload.platform
    )


@router.post(
    "/devices/remove",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Oublier un appareil (déconnexion / désinscription)",
)
async def unregister_device(
    payload: UnregisterDeviceBody,
    actor: CurrentActor,
    command: UnregisterDeviceDep,
) -> None:
    await command.execute(token=payload.token, account_id=actor.account_id)


@router.get(
    "/devices",
    response_model=DeviceListView,
    summary="Mes appareils enregistrés",
)
async def my_devices(
    actor: CurrentActor,
    devices: DeviceRepositoryDep,
) -> DeviceListView:
    return DeviceListView.from_domain(await devices.list_by_account(actor.account_id))
