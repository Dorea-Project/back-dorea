"""Le code secret oublié — **la seule porte qui ne demande pas d'être déjà entré**.

🔴 `ChangePassword` existait depuis longtemps et ne servait à personne dans ce cas : elle se
clé sur `account_id`, donc elle exige d'être connecté. Or quelqu'un qui a oublié son code ne
peut pas se connecter. Le produit avait un changement de code et **aucune récupération** —
et aucune boutique n'accepte une application où l'on ne peut pas rentrer chez soi.

Ce banc tient les trois propriétés de sécurité, pas la forme des réponses.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.contexts.auth.application.commands.account_security import ResetSecretCode
from app.contexts.auth.application.dtos import TokenPair
from app.contexts.auth.domain.errors import (
    InvalidCredentialsError,
    InvalidSecretCodeFormatError,
)
from app.contexts.auth.domain.otp import OtpPurpose


class _Cred:
    def __init__(self, account_id, phone: str, pin_hash: str | None) -> None:
        self.account_id = account_id
        self.phone_number = phone
        self.pin_hash = pin_hash


class _Credentials:
    def __init__(self, cred: _Cred | None) -> None:
        self._cred = cred

    async def get_by_phone(self, phone: str):
        return self._cred if self._cred and self._cred.phone_number == phone else None


class _Security:
    def __init__(self) -> None:
        self.poses: list[tuple] = []

    async def set_pin(self, account_id, pin_hash, version) -> None:
        self.poses.append((account_id, pin_hash, version))


class _Devices:
    def __init__(self) -> None:
        self.revoques: list = []
        self.confies: list = []

    async def revoke_all(self, account_id, at) -> int:
        self.revoques.append(account_id)
        return 1

    async def trust(self, account_id, device_id, at) -> None:
        self.confies.append((account_id, device_id))


class _Otp:
    def __init__(self) -> None:
        self.emis: list[tuple] = []
        self.verifies: list[tuple] = []

    async def issue(self, *, purpose, channel, target, account_id) -> None:
        self.emis.append((purpose, target))

    async def verify(self, *, purpose, target, code):
        self.verifies.append((purpose, target, code))
        return object()


class _Hasher:
    def hash(self, valeur: str) -> str:
        return f"hache:{valeur}"


class _Tokens:
    def issue_pair(self, account_id, device_id) -> TokenPair:
        return TokenPair(access_token="a", refresh_token="r", expires_in=900)


def _commande(cred: _Cred | None):
    otp, devices, security = _Otp(), _Devices(), _Security()
    return (
        ResetSecretCode(
            _Credentials(cred), security, devices, otp, _Hasher(), _Tokens(),
            clock=lambda: datetime.now(UTC), hash_algo_version=1,
        ),
        otp, devices, security,
    )


# -- l'énumération, qui est la propriété la plus facile à perdre ---------------------


async def test_un_numero_inconnu_ne_recoit_rien_et_ne_leve_rien() -> None:
    """🔴 **Le silence est la réponse.**

    Une erreur sur un numéro inconnu ferait de cette route un annuaire : on saurait qui est
    inscrit chez Dorea en essayant des numéros."""
    commande, otp, _, _ = _commande(None)
    await commande.request(phone_number="+2250700000099")
    assert otp.emis == []


async def test_un_compte_jamais_active_ne_recoit_rien_non_plus() -> None:
    """Un compte enrôlé par une église et jamais revendiqué n'a pas de code à réinitialiser —
    il doit passer par l'inscription. Et l'appelant ne doit pas pouvoir faire la différence."""
    commande, otp, _, _ = _commande(_Cred(uuid4(), "+2250700000001", pin_hash=None))
    await commande.request(phone_number="+2250700000001")
    assert otp.emis == []


async def test_un_numero_connu_recoit_son_otp() -> None:
    commande, otp, _, _ = _commande(_Cred(uuid4(), "+2250700000001", pin_hash="x"))
    await commande.request(phone_number="+2250700000001")
    assert otp.emis == [(OtpPurpose.RESET_SECRET_CODE, "+2250700000001")]


# -- le motif, qui empêche un OTP de voyager d'une porte à l'autre --------------------


async def test_le_motif_est_distinct_du_changement_de_code() -> None:
    """⚠️ Réutiliser `CHANGE_PASSWORD` laisserait rejouer dans un contexte **anonyme** un code
    émis pour un porteur déjà authentifié."""
    commande, otp, _, _ = _commande(_Cred(uuid4(), "+2250700000001", pin_hash="x"))
    await commande.confirm(
        phone_number="+2250700000001", otp="123456",
        new_secret_code="4321", device_id="dev-1",
    )
    assert otp.verifies[0][0] is OtpPurpose.RESET_SECRET_CODE


# -- ce que la confirmation fait, et dans quel ordre ----------------------------------


async def test_un_code_malforme_ne_brule_pas_l_otp() -> None:
    """Même discipline qu'à l'inscription : on ne fait pas repayer un SMS pour une faute de
    frappe. Le format se valide **avant** de consommer le code reçu."""
    commande, otp, _, _ = _commande(_Cred(uuid4(), "+2250700000001", pin_hash="x"))
    with pytest.raises(InvalidSecretCodeFormatError):
        await commande.confirm(
            phone_number="+2250700000001", otp="123456",
            new_secret_code="pas-un-pin", device_id="dev-1",
        )
    assert otp.verifies == []


async def test_les_autres_appareils_meurent_et_celui_ci_reste() -> None:
    """🔴 Changer la serrure laisse rarement les anciennes clés en circulation.

    Mais l'appareil qui vient de prouver sa possession du numéro est gardé — sans quoi on
    renverrait dehors celui qu'on vient de faire entrer."""
    compte = uuid4()
    commande, _, devices, _ = _commande(_Cred(compte, "+2250700000001", pin_hash="x"))
    await commande.confirm(
        phone_number="+2250700000001", otp="123456",
        new_secret_code="4321", device_id="dev-1",
    )
    assert devices.revoques == [compte]
    assert devices.confies == [(compte, "dev-1")]


async def test_le_nouveau_code_est_pose() -> None:
    compte = uuid4()
    commande, _, _, security = _commande(_Cred(compte, "+2250700000001", pin_hash="ancien"))
    await commande.confirm(
        phone_number="+2250700000001", otp="123456",
        new_secret_code="4321", device_id="dev-1",
    )
    assert security.poses == [(compte, "hache:4321", 1)]


async def test_la_confirmation_rend_des_jetons() -> None:
    """Il vient de prouver sa possession du numéro : le renvoyer vers l'écran de connexion
    serait lui redemander le code qu'il vient de poser."""
    commande, _, _, _ = _commande(_Cred(uuid4(), "+2250700000001", pin_hash="x"))
    paire = await commande.confirm(
        phone_number="+2250700000001", otp="123456",
        new_secret_code="4321", device_id="dev-1",
    )
    assert paire.access_token and paire.refresh_token


async def test_un_numero_disparu_entre_la_demande_et_la_confirmation_est_refuse() -> None:
    commande, _, _, _ = _commande(None)
    with pytest.raises(InvalidCredentialsError):
        await commande.confirm(
            phone_number="+2250700000001", otp="123456",
            new_secret_code="4321", device_id="dev-1",
        )
