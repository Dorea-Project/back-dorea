"""Opérations sensibles **membre** (P5) — changement de code secret / de numéro.

Chaque opération est en deux temps : `request` (envoie un OTP) puis `confirm`
(vérifie l'OTP et applique). Protège contre le vol de téléphone : sans le code
reçu, impossible de changer le PIN ou le numéro.
"""

from __future__ import annotations

from uuid import UUID

from app.contexts.auth.application.otp_service import OtpService
from app.contexts.auth.application.ports import PasswordHasher
from app.contexts.auth.domain.errors import InvalidCredentialsError
from app.contexts.auth.domain.otp import OtpChannel, OtpPurpose
from app.contexts.auth.domain.repositories import (
    AccountSecurityRepository,
    CredentialsRepository,
)
from app.contexts.auth.domain.secret_code import SecretCode


class ChangePassword:
    def __init__(
        self,
        credentials: CredentialsRepository,
        security: AccountSecurityRepository,
        otp: OtpService,
        hasher: PasswordHasher,
        *,
        hash_algo_version: int,
    ) -> None:
        self._credentials = credentials
        self._security = security
        self._otp = otp
        self._hasher = hasher
        self._hash_algo_version = hash_algo_version

    async def request(self, *, account_id: UUID) -> None:
        cred = await self._require(account_id)
        await self._otp.issue(
            purpose=OtpPurpose.CHANGE_PASSWORD,
            channel=OtpChannel.SMS,
            target=cred.phone_number,
            account_id=account_id,
        )

    async def confirm(self, *, account_id: UUID, otp: str, new_secret_code: str) -> None:
        cred = await self._require(account_id)
        await self._otp.verify(
            purpose=OtpPurpose.CHANGE_PASSWORD, target=cred.phone_number, code=otp
        )
        # Le « code secret » mobile EST le PIN → slot pin_hash (décision C).
        new_hash = self._hasher.hash(SecretCode(new_secret_code).value)
        await self._security.set_pin(account_id, new_hash, self._hash_algo_version)

    async def _require(self, account_id: UUID):
        cred = await self._credentials.get_by_account_id(account_id)
        if cred is None:
            raise InvalidCredentialsError("Compte introuvable.")
        return cred


class ChangePhone:
    def __init__(
        self,
        security: AccountSecurityRepository,
        otp: OtpService,
    ) -> None:
        self._security = security
        self._otp = otp

    async def request(self, *, account_id: UUID, new_phone: str) -> None:
        # L'OTP part sur le NOUVEAU numéro (prouve qu'il appartient au membre).
        await self._otp.issue(
            purpose=OtpPurpose.CHANGE_PHONE,
            channel=OtpChannel.SMS,
            target=new_phone,
            account_id=account_id,
        )

    async def confirm(self, *, account_id: UUID, new_phone: str, otp: str) -> None:
        await self._otp.verify(purpose=OtpPurpose.CHANGE_PHONE, target=new_phone, code=otp)
        await self._security.set_phone(account_id, new_phone)
