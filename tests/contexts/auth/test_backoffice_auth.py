"""P2 — Auth backoffice : email + mot de passe + OTP nouvel appareil (contre SQLite)."""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.contexts.auth.application.ports import CodeGenerator
from app.contexts.auth.infrastructure.hashing import HASH_ALGO_VERSION, Argon2PasswordHasher
from app.contexts.auth.interface.backoffice_dependencies import (
    BACKOFFICE_SESSION_COOKIE,
    get_code_generator,
)
from app.contexts.iam.infrastructure.persistence.models import AccountModel
from app.core.database import Base, get_db_session
from app.main import create_app

_EMAIL = "owner@bethel.ci"
_PASSWORD = "MotDePasse#2026"
_ACCOUNT = uuid4()
_OTP = "000000"


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

    # Seed d'un compte owner (email + mot de passe hashé).
    async with factory() as s:
        s.add(
            AccountModel(
                id=_ACCOUNT,
                phone_number="+2250700000001",
                email=_EMAIL,
                password_hash=Argon2PasswordHasher().hash(_PASSWORD),
                hash_algo_version=HASH_ALGO_VERSION,
                is_phone_verified=False,
                is_email_verified=True,
                created_at=datetime.now(UTC),
                created_by_type="owner",
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


async def test_new_device_requires_otp_then_verify_opens_session(client: AsyncClient):
    # 1. Login depuis un appareil inconnu → 202 OTP requis (pas de session).
    login = await client.post(
        "/api/backoffice/auth/login",
        json={"email": _EMAIL, "password": _PASSWORD, "device_id": "dev-1"},
    )
    assert login.status_code == 202
    assert login.json()["status"] == "otp_required"
    assert login.cookies.get(BACKOFFICE_SESSION_COOKIE) is None

    # 2. Vérifier l'OTP → appareil de confiance + session.
    verify = await client.post(
        "/api/backoffice/auth/verify",
        json={"email": _EMAIL, "otp": _OTP, "device_id": "dev-1"},
    )
    assert verify.status_code == 204
    assert verify.cookies.get(BACKOFFICE_SESSION_COOKIE) is not None

    # 3. /me fonctionne avec la session.
    me = await client.get("/api/backoffice/auth/me")
    assert me.status_code == 200
    assert me.json()["account_id"] == str(_ACCOUNT)


async def test_trusted_device_skips_otp(client: AsyncClient):
    # Vérifier l'appareil une fois…
    await client.post(
        "/api/backoffice/auth/login",
        json={"email": _EMAIL, "password": _PASSWORD, "device_id": "dev-2"},
    )
    await client.post(
        "/api/backoffice/auth/verify",
        json={"email": _EMAIL, "otp": _OTP, "device_id": "dev-2"},
    )
    # …puis un nouveau login depuis CE MÊME appareil → session directe (204), pas d'OTP.
    relogin = await client.post(
        "/api/backoffice/auth/login",
        json={"email": _EMAIL, "password": _PASSWORD, "device_id": "dev-2"},
    )
    assert relogin.status_code == 204


async def test_wrong_password_is_401(client: AsyncClient):
    resp = await client.post(
        "/api/backoffice/auth/login",
        json={"email": _EMAIL, "password": "wrong-password", "device_id": "dev-3"},
    )
    assert resp.status_code == 401


async def test_wrong_otp_is_rejected(client: AsyncClient):
    await client.post(
        "/api/backoffice/auth/login",
        json={"email": _EMAIL, "password": _PASSWORD, "device_id": "dev-4"},
    )
    resp = await client.post(
        "/api/backoffice/auth/verify",
        json={"email": _EMAIL, "otp": "999999", "device_id": "dev-4"},
    )
    assert resp.status_code == 401


async def test_me_without_session_is_401(client: AsyncClient):
    assert (await client.get("/api/backoffice/auth/me")).status_code == 401
