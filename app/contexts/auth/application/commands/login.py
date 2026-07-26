"""Use case : connexion mobile **device-aware** (téléphone + PIN + appareil, M-4).

- Appareil **de confiance** → paire de jetons émise directement.
- Appareil **inconnu** → OTP SMS envoyé (sur le numéro), pas de jetons → l'appelant
  doit passer par `VerifyDeviceLogin`. Même patron que le login backoffice (P2).
"""

from __future__ import annotations

from app.contexts.auth.application.credential_check import verify_credentials
from app.contexts.auth.application.dtos import MobileAuthOutcome
from app.contexts.auth.application.login_throttle import LoginThrottle
from app.contexts.auth.application.otp_service import OtpService
from app.contexts.auth.application.ports import PasswordHasher, TokenService
from app.contexts.auth.domain.errors import InvalidCredentialsError
from app.contexts.auth.domain.otp import OtpChannel, OtpPurpose
from app.contexts.auth.domain.repositories import CredentialsRepository, DeviceRepository
from app.contexts.auth.domain.secret_code import SecretCode


class Login:
    def __init__(
        self,
        credentials: CredentialsRepository,
        devices: DeviceRepository,
        otp: OtpService,
        hasher: PasswordHasher,
        tokens: TokenService,
        throttle: LoginThrottle | None = None,
    ) -> None:
        self._credentials = credentials
        self._devices = devices
        self._otp = otp
        self._hasher = hasher
        self._tokens = tokens
        self._throttle = throttle

    async def execute(
        self, *, phone_number: str, secret_code: SecretCode, device_id: str
    ) -> MobileAuthOutcome:
        # Anti-brute-force : refuse si verrouillé, compte l'échec, purge au succès.
        if self._throttle is not None:
            await self._throttle.ensure_not_locked(phone_number)
        cred = await self._credentials.get_by_phone(phone_number)
        try:
            cred = verify_credentials(cred, secret_code.value, self._hasher, use_pin=True)
        except InvalidCredentialsError:
            if self._throttle is not None:
                await self._throttle.record_failure(phone_number)
            raise
        if self._throttle is not None:
            await self._throttle.clear(phone_number)

        if await self._devices.is_trusted(cred.account_id, device_id):
            pair = self._tokens.issue_pair(cred.account_id)
            return MobileAuthOutcome(tokens=pair, otp_required=False)

        # Nouvel appareil → défi OTP (SMS sur le numéro), pas de jetons encore.
        await self._otp.issue(
            purpose=OtpPurpose.NEW_DEVICE,
            channel=OtpChannel.SMS,
            target=phone_number,
            account_id=cred.account_id,
            device_id=device_id,
        )
        return MobileAuthOutcome(tokens=None, otp_required=True)
