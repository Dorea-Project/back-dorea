"""P5 — opérations sensibles membre : changement code secret / numéro via OTP (mobile)."""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.contexts.auth.application.ports import CodeGenerator
from app.contexts.auth.infrastructure.hashing import HASH_ALGO_VERSION, Argon2PasswordHasher
from app.contexts.auth.interface.otp_dependencies import get_code_generator
from app.contexts.iam.infrastructure.persistence.models import AccountModel
from app.core.database import Base, get_db_session
from app.main import create_app

_PHONE = "+2250700000001"
_PIN = "1234"
_OTP = "000000"
_DEVICE = "device-p5"


class _FixedCode(CodeGenerator):
    def generate(self):
        return _OTP


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        s.add(
            AccountModel(
                id=uuid4(),
                phone_number=_PHONE,
                email=None,
                password_hash=None,
                pin_hash=Argon2PasswordHasher().hash(_PIN),  # login MOBILE → slot PIN
                hash_algo_version=HASH_ALGO_VERSION,
                is_phone_verified=True,
                is_email_verified=False,
                created_at=datetime.now(UTC),
                created_by_type="self_service",
                status="active",
            )
        )
        await s.commit()

    async def _override() -> AsyncGenerator[AsyncSession]:
        async with factory() as s:
            try:
                yield s
                await s.commit()
            except Exception:
                await s.rollback()
                raise

    app = create_app()
    app.dependency_overrides[get_db_session] = _override
    app.dependency_overrides[get_code_generator] = lambda: _FixedCode()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
    await engine.dispose()


async def _token(client, phone=_PHONE, pin=_PIN, device=_DEVICE):
    # 1er login sur un appareil inconnu → OTP (202), puis verify-device → jetons (M-4).
    login = await client.post(
        "/api/mobile/auth/login",
        json={"phone_number": phone, "secret_code": pin, "device_id": device},
    )
    assert login.status_code == 202
    verify = await client.post(
        "/api/mobile/auth/verify-device",
        json={"phone_number": phone, "otp": _OTP, "device_id": device},
    )
    return verify.json()["access_token"]


async def test_change_password_via_otp(client: AsyncClient):
    auth = {"Authorization": f"Bearer {await _token(client)}"}

    req = await client.post("/api/mobile/account/change-password/request", headers=auth)
    assert req.status_code == 202

    conf = await client.post(
        "/api/mobile/account/change-password/confirm",
        headers=auth,
        json={"otp": _OTP, "new_secret_code": "4321"},
    )
    assert conf.status_code == 204

    # Nouveau PIN accepté (appareil déjà de confiance → 200 direct), ancien refusé.
    assert (
        await client.post(
            "/api/mobile/auth/login",
            json={"phone_number": _PHONE, "secret_code": "4321", "device_id": _DEVICE},
        )
    ).status_code == 200
    assert (
        await client.post(
            "/api/mobile/auth/login",
            json={"phone_number": _PHONE, "secret_code": _PIN, "device_id": _DEVICE},
        )
    ).status_code == 401


async def test_change_phone_via_otp(client: AsyncClient):
    auth = {"Authorization": f"Bearer {await _token(client)}"}
    new_phone = "+2250700000099"

    await client.post(
        "/api/mobile/account/change-phone/request", headers=auth, json={"new_phone": new_phone}
    )
    conf = await client.post(
        "/api/mobile/account/change-phone/confirm",
        headers=auth,
        json={"new_phone": new_phone, "otp": _OTP},
    )
    assert conf.status_code == 204

    # Connexion au NOUVEAU numéro OK (même compte, appareil déjà de confiance).
    assert (
        await client.post(
            "/api/mobile/auth/login",
            json={"phone_number": new_phone, "secret_code": _PIN, "device_id": _DEVICE},
        )
    ).status_code == 200


async def test_wrong_otp_blocks_password_change(client: AsyncClient):
    auth = {"Authorization": f"Bearer {await _token(client)}"}
    await client.post("/api/mobile/account/change-password/request", headers=auth)
    conf = await client.post(
        "/api/mobile/account/change-password/confirm",
        headers=auth,
        json={"otp": "999999", "new_secret_code": "4321"},
    )
    assert conf.status_code == 401


async def test_sensitive_ops_require_auth(client: AsyncClient):
    assert (
        await client.post("/api/mobile/account/change-password/request")
    ).status_code == 401
