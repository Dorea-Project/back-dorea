"""Use case : 1ʳᵉ étape du login **backoffice** (email + mot de passe + appareil).

- Appareil **de confiance** → session émise directement.
- Appareil **inconnu** → OTP envoyé (email), session **non** émise → l'appelant doit
  passer par `BackofficeVerifyDevice`.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.contexts.auth.application.credential_check import verify_credentials
from app.contexts.auth.application.login_throttle import LoginThrottle
from app.contexts.auth.application.otp_service import OtpService
from app.contexts.auth.application.ports import PasswordHasher, TokenService
from app.contexts.auth.domain.errors import InvalidCredentialsError
from app.contexts.auth.domain.otp import OtpChannel, OtpPurpose
from app.contexts.auth.domain.repositories import CredentialsRepository, DeviceRepository


@dataclass(frozen=True)
class AuthOutcome:
    session_token: str | None  # présent si l'appareil est de confiance
    otp_required: bool  # True si un OTP a été envoyé (nouvel appareil)


class BackofficeAuthenticate:
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

    async def execute(self, *, email: str, password: str, device_id: str) -> AuthOutcome:
        if self._throttle is not None:
            await self._throttle.ensure_not_locked(email)
        cred = await self._credentials.get_by_email(email)
        try:
            cred = verify_credentials(cred, password, self._hasher)
        except InvalidCredentialsError:
            if self._throttle is not None:
                await self._throttle.record_failure(email)
            raise
        if self._throttle is not None:
            await self._throttle.clear(email)

        if await self._devices.is_trusted(cred.account_id, device_id):
            token = self._tokens.issue_session(cred.account_id, device_id)
            return AuthOutcome(session_token=token, otp_required=False)

        # Nouvel appareil → défi OTP (email), pas de session encore.
        await self._otp.issue(
            purpose=OtpPurpose.NEW_DEVICE,
            channel=OtpChannel.EMAIL,
            target=email,
            account_id=cred.account_id,
            device_id=device_id,
        )
        return AuthOutcome(session_token=None, otp_required=True)
