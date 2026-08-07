"""Use case : 2ᵉ étape du login mobile — vérifier l'OTP d'un nouvel appareil (M-4).

OTP valide → l'appareil devient **de confiance** (plus d'OTP la prochaine fois) et
la paire de jetons est émise. Mirroir mobile de `BackofficeVerifyDevice`.
"""

from __future__ import annotations

from app.contexts.auth.application.dtos import TokenPair
from app.contexts.auth.application.otp_service import OtpService
from app.contexts.auth.application.ports import TokenService
from app.contexts.auth.domain.errors import OtpInvalidError
from app.contexts.auth.domain.otp import OtpPurpose
from app.contexts.auth.domain.repositories import DeviceRepository


class VerifyDeviceLogin:
    def __init__(
        self,
        devices: DeviceRepository,
        otp: OtpService,
        tokens: TokenService,
        *,
        clock,
    ) -> None:
        self._devices = devices
        self._otp = otp
        self._tokens = tokens
        self._clock = clock

    async def execute(self, *, phone_number: str, otp: str, device_id: str) -> TokenPair:
        challenge = await self._otp.verify(
            purpose=OtpPurpose.NEW_DEVICE, target=phone_number, code=otp
        )
        if challenge.account_id is None or challenge.device_id != device_id:
            # Le défi doit correspondre à l'appareil qui l'a demandé.
            raise OtpInvalidError("Code invalide pour cet appareil.")

        await self._devices.trust(challenge.account_id, device_id, self._clock())
        return self._tokens.issue_pair(challenge.account_id, device_id)
