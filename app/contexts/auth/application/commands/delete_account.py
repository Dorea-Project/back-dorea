"""Supprimer son compte — l'opération irréversible du lot.

La politique de confidentialité d'Urim l'écrit sous une mention de la loi ivoirienne
n° 2013-450 : « Tu peux supprimer ton compte et tout son contenu à tout moment. » Rien
ne la tenait côté serveur ; l'application ne pouvait qu'effacer son propre téléphone.

## Deux temps, comme les autres opérations sensibles

`request` envoie un OTP au numéro du compte, `confirm` l'exige. Un téléphone
déverrouillé oublié sur une table suffirait sinon à détruire des années de
préparations, et c'est la seule de ces opérations qu'on ne peut pas défaire.

## Ce que « supprimer » veut dire ici

**Le contenu part vraiment.** Les préparations, les captures, les retours, les
réservations : effacés, pas marqués. C'est le travail de la personne, il n'appartient
à personne d'autre.

**La ligne du compte reste, vidée de son identité.** Elle est référencée par la vie
d'église — présences, dons, groupes — et la détruire emporterait les registres d'une
communauté avec le compte d'une personne. Ce que la loi exige est qu'elle ne soit plus
identifiable : numéro remplacé par une pierre tombale, noms, e-mail et empreintes de
code effacés, statut `closed`. Personne ne peut plus s'y connecter, et le vrai numéro
redevient libre — se réinscrire plus tard crée un compte neuf, sans rien retrouver.

**Les appareils sont révoqués.** Sans cela, un jeton encore valide continuerait
d'ouvrir la porte d'un compte fermé jusqu'à son expiration.
"""

from __future__ import annotations

from uuid import UUID

from app.contexts.auth.application.otp_service import OtpService
from app.contexts.auth.application.ports import AccountContentEraser
from app.contexts.auth.domain.errors import InvalidCredentialsError
from app.contexts.auth.domain.otp import OtpChannel, OtpPurpose
from app.contexts.auth.domain.repositories import (
    AccountSecurityRepository,
    CredentialsRepository,
    DeviceRepository,
)


def tombstone_phone(account_id: UUID) -> str:
    """Le numéro qui ne désigne plus personne.

    Unique — la colonne l'exige — et reconnaissable : un `NULL` était impossible, et un
    numéro inventé risquerait de tomber sur celui de quelqu'un.
    """
    return f"deleted:{account_id}"


class DeleteAccount:
    def __init__(
        self,
        credentials: CredentialsRepository,
        security: AccountSecurityRepository,
        devices: DeviceRepository,
        otp: OtpService,
        erasers: tuple[AccountContentEraser, ...],
        clock,
    ) -> None:
        self._credentials = credentials
        self._security = security
        self._devices = devices
        self._otp = otp
        self._erasers = erasers
        self._clock = clock

    async def request(self, *, account_id: UUID) -> None:
        cred = await self._require(account_id)
        await self._otp.issue(
            purpose=OtpPurpose.DELETE_ACCOUNT,
            channel=OtpChannel.SMS,
            target=cred.phone_number,
            account_id=account_id,
        )

    async def confirm(self, *, account_id: UUID, otp: str) -> None:
        cred = await self._require(account_id)
        await self._otp.verify(
            purpose=OtpPurpose.DELETE_ACCOUNT, target=cred.phone_number, code=otp
        )

        # Le contenu d'abord, l'identité ensuite. Si la transaction casse en chemin, le
        # compte est encore là pour recommencer ; l'inverse laisserait du contenu sans
        # propriétaire nommable, que plus personne ne saurait réclamer ni retrouver.
        for eraser in self._erasers:
            await eraser.erase(account_id)

        await self._devices.revoke_all(account_id, self._clock())
        await self._security.close(account_id, tombstone_phone=tombstone_phone(account_id))

    async def _require(self, account_id: UUID):
        cred = await self._credentials.get_by_account_id(account_id)
        if cred is None or not cred.is_active:
            # Un compte déjà fermé n'est plus joignable : il n'a plus de numéro à qui
            # envoyer un code, et plus rien à effacer.
            raise InvalidCredentialsError("Compte introuvable.")
        return cred
