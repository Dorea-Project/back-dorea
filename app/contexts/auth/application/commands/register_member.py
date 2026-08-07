"""Use case `RegisterMember` — auto-inscription mobile d'un membre (M-1).

Flux en deux temps (preuve de possession du numéro) :
- `request(phone)` : émet un OTP SMS (purpose `mobile_registration`).
- `confirm(phone, otp, secret_code)` : vérifie l'OTP puis pose le PIN et connecte.

Deux cas au `confirm`, transparents pour le mobile (§ member-model, scénarios 1/3) :
- **Compte déjà présent sans PIN** (enrôlé par une église, jamais activé) → on le
  **revendique** : on pose son PIN (le compte global est réutilisé, pas dupliqué).
- **Aucun compte** → on crée un compte global `self_service` avec son PIN.

Un numéro possédant **déjà** un PIN relève de la connexion, pas de l'inscription → 409.
"""

from __future__ import annotations

from uuid import uuid4

from app.contexts.auth.application.dtos import TokenPair
from app.contexts.auth.application.otp_service import OtpService
from app.contexts.auth.application.ports import PasswordHasher, TokenService
from app.contexts.auth.domain.errors import PhoneAlreadyRegisteredError
from app.contexts.auth.domain.otp import OtpChannel, OtpPurpose
from app.contexts.auth.domain.repositories import (
    AccountSecurityRepository,
    CredentialsRepository,
    DeviceRepository,
)
from app.contexts.auth.domain.secret_code import SecretCode


class RegisterMember:
    def __init__(
        self,
        credentials: CredentialsRepository,
        security: AccountSecurityRepository,
        devices: DeviceRepository,
        otp: OtpService,
        hasher: PasswordHasher,
        tokens: TokenService,
        *,
        clock,
        hash_algo_version: int,
    ) -> None:
        self._credentials = credentials
        self._security = security
        self._devices = devices
        self._otp = otp
        self._hasher = hasher
        self._tokens = tokens
        self._clock = clock
        self._hash_algo_version = hash_algo_version

    async def request(self, *, phone_number: str) -> None:
        await self._otp.issue(
            purpose=OtpPurpose.MOBILE_REGISTRATION,
            channel=OtpChannel.SMS,
            target=phone_number,
        )

    async def confirm(
        self, *, phone_number: str, otp: str, secret_code: str, device_id: str
    ) -> TokenPair:
        # Valide le PIN AVANT de consommer l'OTP (un format invalide ne « brûle » pas le code).
        pin_hash = self._hasher.hash(SecretCode(secret_code).value)
        await self._otp.verify(
            purpose=OtpPurpose.MOBILE_REGISTRATION, target=phone_number, code=otp
        )

        cred = await self._credentials.get_by_phone(phone_number)
        if cred is None:
            account_id = uuid4()
            await self._security.create_self_registered(
                account_id=account_id,
                phone_number=phone_number,
                pin_hash=pin_hash,
                hash_algo_version=self._hash_algo_version,
                created_at=self._clock(),
            )
        else:
            if cred.pin_hash is not None:
                raise PhoneAlreadyRegisteredError(
                    "Ce numéro est déjà inscrit — connectez-vous.",
                    details={"phone_number": phone_number},
                )
            # Compte enrôlé par une église, jamais activé → on le revendique (M-2).
            await self._security.set_pin(cred.account_id, pin_hash, self._hash_algo_version)
            account_id = cred.account_id

        # L'inscription prouve déjà la possession du numéro (OTP) → l'appareil
        # d'inscription est de confiance : pas de nouvel OTP au premier login (M-4).
        await self._devices.trust(account_id, device_id, self._clock())
        return self._tokens.issue_pair(account_id, device_id)
