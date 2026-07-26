"""Test HTTP du flux d'authentification mobile (device-aware, doubles injectés)."""

from collections.abc import AsyncGenerator
from datetime import datetime
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.contexts.auth.application.commands.login import Login
from app.contexts.auth.application.dtos import TokenPair
from app.contexts.auth.application.ports import PasswordHasher, TokenService
from app.contexts.auth.domain.credentials import AuthCredentials
from app.contexts.auth.domain.otp import OtpChallenge
from app.contexts.auth.domain.repositories import CredentialsRepository, DeviceRepository
from app.contexts.auth.interface.dependencies import get_login_command
from app.main import create_app

_ACCOUNT = uuid4()
_PHONE = "+2250700000001"
_TRUSTED_DEVICE = "trusted-device"


class _Repo(CredentialsRepository):
    async def get_by_phone(self, phone_number):
        if phone_number != _PHONE:
            return None
        return AuthCredentials(
            account_id=_ACCOUNT,
            phone_number=_PHONE,
            password_hash=None,
            pin_hash="stored",  # login MOBILE → slot PIN
            hash_algo_version=1,
            is_active=True,
        )

    async def get_by_email(self, email):
        return None

    async def get_by_account_id(self, account_id):
        return None


class _Hasher(PasswordHasher):
    def verify(self, hashed, plain):
        return hashed == "stored" and plain == "1234"

    def hash(self, plain):
        return "stored"


class _Devices(DeviceRepository):
    """Seul `_TRUSTED_DEVICE` est de confiance ; tout autre déclenche un OTP."""

    async def is_trusted(self, account_id, device_id):
        return device_id == _TRUSTED_DEVICE

    async def trust(self, account_id, device_id, trusted_at: datetime):
        return None


class _Otp:
    def __init__(self) -> None:
        self.issued = []

    async def issue(self, **kwargs):
        self.issued.append(kwargs)

    async def verify(self, **kwargs) -> OtpChallenge:  # pragma: no cover - non utilisé ici
        raise AssertionError("verify inattendu dans ce test")


class _Tokens(TokenService):
    def issue_pair(self, account_id):
        return TokenPair("access-token", "refresh-token", 3600)

    def issue_session(self, account_id):
        return "session"

    def decode_access(self, token):
        return _ACCOUNT

    def decode_refresh(self, token):
        return _ACCOUNT

    def decode_session(self, token):
        return _ACCOUNT


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient]:
    app = create_app()
    app.dependency_overrides[get_login_command] = lambda: Login(
        _Repo(), _Devices(), _Otp(), _Hasher(), _Tokens()
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


async def test_login_trusted_device_returns_tokens(client: AsyncClient):
    resp = await client.post(
        "/api/mobile/auth/login",
        json={"phone_number": _PHONE, "secret_code": "1234", "device_id": _TRUSTED_DEVICE},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"] and body["refresh_token"]


async def test_login_new_device_requires_otp(client: AsyncClient):
    resp = await client.post(
        "/api/mobile/auth/login",
        json={"phone_number": _PHONE, "secret_code": "1234", "device_id": "new-device"},
    )
    assert resp.status_code == 202
    assert resp.json()["status"] == "otp_required"


async def test_login_wrong_code_is_401(client: AsyncClient):
    resp = await client.post(
        "/api/mobile/auth/login",
        json={"phone_number": _PHONE, "secret_code": "0000", "device_id": _TRUSTED_DEVICE},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTH_INVALID_CREDENTIALS"


async def test_login_bad_pin_format_is_422(client: AsyncClient):
    resp = await client.post(
        "/api/mobile/auth/login",
        json={"phone_number": _PHONE, "secret_code": "abc", "device_id": _TRUSTED_DEVICE},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "AUTH_INVALID_SECRET_CODE_FORMAT"


async def test_access_protected_route_without_token_is_401(client: AsyncClient):
    # Sans en-tête Authorization, la garde renvoie 401.
    resp = await client.get(f"/api/mobile/iam/me/tenants/{uuid4()}/membership")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTH_INVALID_TOKEN"
