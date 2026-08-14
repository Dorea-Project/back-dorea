"""Opérations sensibles **membre** (P5) — changement de code secret / de numéro.

Chaque opération est en deux temps : `request` (envoie un OTP) puis `confirm`
(vérifie l'OTP et applique). Protège contre le vol de téléphone : sans le code
reçu, impossible de changer le PIN ou le numéro.
"""

from __future__ import annotations

from uuid import UUID

from app.contexts.auth.application.dtos import TokenPair
from app.contexts.auth.application.otp_service import OtpService
from app.contexts.auth.application.ports import PasswordHasher, TokenService
from app.contexts.auth.domain.errors import InvalidCredentialsError
from app.contexts.auth.domain.otp import OtpChannel, OtpPurpose
from app.contexts.auth.domain.repositories import (
    AccountSecurityRepository,
    CredentialsRepository,
    DeviceRepository,
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


class ResetSecretCode:
    """**Le code secret oublié** — la seule porte qui ne demande pas d'être déjà entré.

    🔴 `ChangePassword` existait depuis longtemps et ne servait à personne dans ce cas : elle
    se clé sur `account_id`, donc elle exige d'être **connecté**. Or quelqu'un qui a oublié son
    code ne peut pas se connecter. Le produit avait un changement de code et aucune
    récupération — et aucune boutique n'accepte une application où l'on ne peut pas rentrer
    chez soi.

    Celle-ci se clé sur le **numéro**, parce que c'est tout ce qu'un utilisateur enfermé
    dehors possède encore.

    ## Trois propriétés qu'il faut tenir ensemble

    **Aucune énumération.** `request` se comporte exactement pareil que le numéro existe ou
    non. Un 404 sur un numéro inconnu transformerait cette route en annuaire : on saurait qui
    est inscrit chez Dorea en essayant des numéros.

    **Un motif d'OTP distinct.** Voir `OtpPurpose.RESET_SECRET_CODE`.

    **Les autres sessions meurent.** Réinitialiser un code veut dire *« je n'en avais plus le
    contrôle »* ; laisser vivre les appareils déjà connus reviendrait à changer la serrure en
    laissant les anciennes clés en circulation. L'appareil qui vient de prouver sa possession
    du numéro, lui, est gardé — sans quoi on renverrait dehors celui qu'on vient de faire
    entrer.
    """

    def __init__(
        self,
        credentials: CredentialsRepository,
        security: AccountSecurityRepository,
        devices: DeviceRepository,
        otp: OtpService,
        hasher: PasswordHasher,
        tokens: TokenService,
        clock,
        *,
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
        cred = await self._credentials.get_by_phone(phone_number)
        # ⚠️ Le silence est la réponse. Un numéro inconnu, ou connu mais jamais activé, ne
        # reçoit rien — et l'appelant ne peut pas faire la différence.
        if cred is None or cred.pin_hash is None:
            return
        await self._otp.issue(
            purpose=OtpPurpose.RESET_SECRET_CODE,
            channel=OtpChannel.SMS,
            target=phone_number,
            account_id=cred.account_id,
        )

    async def confirm(
        self, *, phone_number: str, otp: str, new_secret_code: str, device_id: str
    ) -> TokenPair:
        # Le format du nouveau code est validé AVANT de consommer l'OTP : une saisie
        # malformée ne doit pas brûler le code reçu par SMS. Même discipline qu'à
        # l'inscription — on ne fait pas repayer un SMS pour une faute de frappe.
        pin_hash = self._hasher.hash(SecretCode(new_secret_code).value)
        await self._otp.verify(
            purpose=OtpPurpose.RESET_SECRET_CODE, target=phone_number, code=otp
        )

        cred = await self._credentials.get_by_phone(phone_number)
        if cred is None:
            raise InvalidCredentialsError("Compte introuvable.")

        await self._security.set_pin(cred.account_id, pin_hash, self._hash_algo_version)
        maintenant = self._clock()
        await self._devices.revoke_all(cred.account_id, maintenant)
        await self._devices.trust(cred.account_id, device_id, maintenant)
        return self._tokens.issue_pair(cred.account_id, device_id)


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
