"""Use cases **appareil** — enregistrer / oublier un jeton push (la personne, mobile)."""

from __future__ import annotations

from uuid import UUID, uuid4

from app.contexts.notifications.domain.aggregates import Device
from app.contexts.notifications.domain.enums import DevicePlatform
from app.contexts.notifications.domain.repositories import DeviceRepository


class RegisterDevice:
    def __init__(self, devices: DeviceRepository, *, clock) -> None:
        self._devices = devices
        self._clock = clock

    async def execute(
        self, *, actor_account_id: UUID, token: str, platform: DevicePlatform
    ) -> None:
        now = self._clock()
        existing = await self._devices.get_by_token(token.strip())
        if existing is not None:
            # Même jeton déjà connu : on le rattache à ce compte et on le rafraîchit.
            existing.touch(account_id=actor_account_id, platform=platform, now=now)
            await self._devices.save(existing)
            return
        await self._devices.add(
            Device.register(
                id=uuid4(),
                account_id=actor_account_id,
                token=token,
                platform=platform,
                now=now,
            )
        )


class UnregisterDevice:
    def __init__(self, devices: DeviceRepository) -> None:
        self._devices = devices

    async def execute(self, *, token: str, account_id: UUID) -> None:
        # Tolérant si absent — mais **jamais** hors de son propre compte (DOREA-023).
        await self._devices.remove_by_token(token.strip(), account_id=account_id)
