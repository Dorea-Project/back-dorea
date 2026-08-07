"""Use case : 2ᵉ étape du login backoffice — vérifier l'OTP d'un nouvel appareil.

OTP valide → l'appareil devient **de confiance** (plus d'OTP la prochaine fois) et
la session est émise.
"""

from __future__ import annotations

from app.contexts.auth.application.otp_service import OtpService
from app.contexts.auth.application.ports import TokenService
from app.contexts.auth.domain.errors import OtpInvalidError
from app.contexts.auth.domain.otp import OtpPurpose
from app.contexts.auth.domain.repositories import DeviceRepository


class BackofficeVerifyDevice:
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

    async def execute(self, *, email: str, otp: str, device_id: str) -> str:
        """Retourne le jeton de session si l'OTP est bon (sinon lève)."""
        challenge = await self._otp.verify(
            purpose=OtpPurpose.NEW_DEVICE, target=email, code=otp
        )
        if challenge.account_id is None or challenge.device_id != device_id:
            # Le défi doit correspondre à l'appareil qui l'a demandé.
            raise OtpInvalidError("Code invalide pour cet appareil.")

        await self._devices.trust(challenge.account_id, device_id, self._clock())
        return self._tokens.issue_session(challenge.account_id, device_id)
