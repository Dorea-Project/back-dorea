"""Tests des use cases Auth avec des doubles en mémoire (sans base ni JWT réel)."""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.contexts.auth.application.commands.login import Login
from app.contexts.auth.application.commands.refresh_token import RefreshToken
from app.contexts.auth.application.commands.verify_device_login import VerifyDeviceLogin
from app.contexts.auth.application.dtos import TokenPair
from app.contexts.auth.application.login_throttle import LoginThrottle
from app.contexts.auth.application.ports import PasswordHasher, TokenService
from app.contexts.auth.domain.credentials import AuthCredentials
from app.contexts.auth.domain.errors import (
    AccountInactiveError,
    InvalidCredentialsError,
    InvalidTokenError,
    OtpInvalidError,
    TooManyLoginAttemptsError,
)
from app.contexts.auth.domain.otp import OtpPurpose
from app.contexts.auth.domain.repositories import (
    CredentialsRepository,
    DeviceRepository,
    LoginAttemptRepository,
)
from app.contexts.auth.domain.secret_code import SecretCode

_DEVICE = "device-abc"
_NOW = datetime(2026, 1, 1, tzinfo=UTC)
_PHONE = "+2250700000001"


class FakeLoginAttempts(LoginAttemptRepository):
    def __init__(self):
        self._d = {}

    async def get(self, identifier):
        return self._d.get(identifier)

    async def save(self, attempt):
        self._d[attempt.identifier] = attempt


class FakeDevices(DeviceRepository):
    def __init__(self, trusted=()) -> None:
        self._trusted = set(trusted)  # {(account_id, device_id)}
        self.trusted_calls = []

    async def is_trusted(self, account_id, device_id):
        return (account_id, device_id) in self._trusted

    async def trust(self, account_id, device_id, trusted_at):
        self._trusted.add((account_id, device_id))
        self.trusted_calls.append((account_id, device_id))


class FakeOtp:
    """Double d'`OtpService` (classe concrète) — enregistre les émissions, scripte la vérif."""

    def __init__(self, challenge=None) -> None:
        self.issued = []
        self._challenge = challenge

    async def issue(self, **kwargs):
        self.issued.append(kwargs)

    async def verify(self, *, purpose, target, code):
        if self._challenge is None:
            raise OtpInvalidError("Code invalide.")
        return self._challenge


class FakeCredentialsRepository(CredentialsRepository):
    def __init__(self, creds: AuthCredentials | None) -> None:
        self._creds = creds

    async def get_by_phone(self, phone_number):
        if self._creds and self._creds.phone_number == phone_number:
            return self._creds
        return None

    async def get_by_email(self, email):
        if self._creds and self._creds.email == email:
            return self._creds
        return None

    async def get_by_account_id(self, account_id):
        if self._creds and self._creds.account_id == account_id:
            return self._creds
        return None


class FakeHasher(PasswordHasher):
    def verify(self, hashed, plain):
        return hashed == f"hash::{plain}"

    def hash(self, plain):
        return f"hash::{plain}"


class FakeTokens(TokenService):
    def issue_pair(self, account_id):
        return TokenPair(f"access::{account_id}", f"refresh::{account_id}", 3600)

    def decode_access(self, token):
        return self._parse("access", token)

    def decode_refresh(self, token):
        return self._parse("refresh", token)

    def issue_session(self, account_id):
        return f"session::{account_id}"

    def decode_session(self, token):
        return self._parse("session", token)

    @staticmethod
    def _parse(kind, token):
        prefix = f"{kind}::"
        if not token.startswith(prefix):
            raise InvalidTokenError("mauvais type de jeton")
        return UUID(token[len(prefix) :])


def _creds(account_id, *, phone="+2250700000001", secret="1234", active=True, has_hash=True):
    # Login MOBILE → slot PIN (pin_hash), pas le mot de passe backoffice.
    return AuthCredentials(
        account_id=account_id,
        phone_number=phone,
        password_hash=None,
        pin_hash=f"hash::{secret}" if has_hash else None,
        hash_algo_version=1,
        is_active=active,
    )


def _login(creds, *, devices=None, otp=None) -> Login:
    return Login(
        FakeCredentialsRepository(creds),
        devices or FakeDevices(),
        otp or FakeOtp(),
        FakeHasher(),
        FakeTokens(),
    )


async def test_login_trusted_device_issues_pair():
    account = uuid4()
    devices = FakeDevices({(account, _DEVICE)})  # appareil déjà de confiance
    login = _login(_creds(account), devices=devices)

    outcome = await login.execute(
        phone_number="+2250700000001", secret_code=SecretCode("1234"), device_id=_DEVICE
    )

    assert outcome.otp_required is False
    assert outcome.tokens.access_token == f"access::{account}"


async def test_login_new_device_sends_otp_and_withholds_tokens():
    account = uuid4()
    otp = FakeOtp()
    login = _login(_creds(account), devices=FakeDevices(), otp=otp)  # appareil inconnu

    outcome = await login.execute(
        phone_number="+2250700000001", secret_code=SecretCode("1234"), device_id=_DEVICE
    )

    assert outcome.otp_required is True
    assert outcome.tokens is None
    # Un OTP NEW_DEVICE a bien été émis, ciblé sur ce numéro et cet appareil.
    assert otp.issued[0]["purpose"] is OtpPurpose.NEW_DEVICE
    assert otp.issued[0]["target"] == "+2250700000001"
    assert otp.issued[0]["device_id"] == _DEVICE


async def test_login_wrong_code_is_invalid_credentials():
    with pytest.raises(InvalidCredentialsError):
        await _login(_creds(uuid4())).execute(
            phone_number="+2250700000001", secret_code=SecretCode("9999"), device_id=_DEVICE
        )


async def test_login_unknown_phone_is_invalid_credentials():
    with pytest.raises(InvalidCredentialsError):
        await _login(None).execute(
            phone_number="+2250700000001", secret_code=SecretCode("1234"), device_id=_DEVICE
        )


async def test_login_suspended_account_is_rejected():
    # DOREA-015 : la suspension n'est révélée qu'avec le BON secret (ici « 1234 »).
    with pytest.raises(AccountInactiveError):
        await _login(_creds(uuid4(), active=False)).execute(
            phone_number="+2250700000001", secret_code=SecretCode("1234"), device_id=_DEVICE
        )


async def test_suspended_account_with_wrong_secret_stays_generic():
    # DOREA-015 : mauvais secret sur compte suspendu → erreur GÉNÉRIQUE (pas d'oracle d'existence).
    with pytest.raises(InvalidCredentialsError):
        await _login(_creds(uuid4(), active=False)).execute(
            phone_number="+2250700000001", secret_code=SecretCode("9999"), device_id=_DEVICE
        )


# --- DOREA-004 : verrou anti-brute-force ---


def _throttled_login(creds, attempts, *, devices=None):
    return Login(
        FakeCredentialsRepository(creds), devices or FakeDevices(), FakeOtp(),
        FakeHasher(), FakeTokens(), LoginThrottle(attempts, clock=lambda: _NOW),
    )


async def test_login_locks_after_five_failures():
    attempts = FakeLoginAttempts()
    login = _throttled_login(_creds(uuid4()), attempts)
    for _ in range(5):  # 5 mauvais PIN
        with pytest.raises(InvalidCredentialsError):
            await login.execute(
                phone_number=_PHONE, secret_code=SecretCode("9999"), device_id=_DEVICE
            )
    # 6ᵉ tentative, MÊME avec le bon PIN → verrouillé (l'oracle est masqué)
    with pytest.raises(TooManyLoginAttemptsError):
        await login.execute(
            phone_number=_PHONE, secret_code=SecretCode("1234"), device_id=_DEVICE
        )


async def test_a_successful_login_resets_the_counter():
    attempts = FakeLoginAttempts()
    login = _throttled_login(_creds(uuid4()), attempts)
    for _ in range(3):
        with pytest.raises(InvalidCredentialsError):
            await login.execute(
                phone_number=_PHONE, secret_code=SecretCode("9999"), device_id=_DEVICE
            )
    assert attempts._d[_PHONE].failed_count == 3
    await login.execute(  # bon PIN → succès (branche OTP nouvel appareil) → purge
        phone_number=_PHONE, secret_code=SecretCode("1234"), device_id=_DEVICE
    )
    assert attempts._d[_PHONE].failed_count == 0


async def test_login_without_secret_set_is_invalid_credentials():
    with pytest.raises(InvalidCredentialsError):
        await _login(_creds(uuid4(), has_hash=False)).execute(
            phone_number="+2250700000001", secret_code=SecretCode("1234"), device_id=_DEVICE
        )


async def test_verify_device_trusts_and_issues_pair():
    account = uuid4()
    challenge = SimpleNamespace(account_id=account, device_id=_DEVICE)
    devices = FakeDevices()
    verify = VerifyDeviceLogin(
        devices, FakeOtp(challenge), FakeTokens(), clock=lambda: datetime.now(UTC)
    )

    pair = await verify.execute(phone_number="+2250700000001", otp="000000", device_id=_DEVICE)

    assert pair.access_token == f"access::{account}"
    assert (account, _DEVICE) in devices.trusted_calls  # appareil devenu de confiance


async def test_verify_device_rejects_mismatched_device():
    challenge = SimpleNamespace(account_id=uuid4(), device_id="another-device")
    verify = VerifyDeviceLogin(
        FakeDevices(), FakeOtp(challenge), FakeTokens(), clock=lambda: datetime.now(UTC)
    )
    with pytest.raises(OtpInvalidError):
        await verify.execute(phone_number="+2250700000001", otp="000000", device_id=_DEVICE)


async def test_refresh_rotates_pair():
    account = uuid4()
    pair = await RefreshToken(FakeTokens()).execute(refresh_token=f"refresh::{account}")
    assert pair.access_token == f"access::{account}"


async def test_refresh_rejects_access_token():
    with pytest.raises(InvalidTokenError):
        await RefreshToken(FakeTokens()).execute(refresh_token=f"access::{uuid4()}")
