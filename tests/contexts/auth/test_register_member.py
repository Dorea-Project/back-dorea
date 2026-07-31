"""M-1 — auto-inscription mobile : OTP SMS → PIN → connexion (création ou revendication)."""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.contexts.auth.application.ports import CodeGenerator
from app.contexts.auth.infrastructure.hashing import HASH_ALGO_VERSION, Argon2PasswordHasher
from app.contexts.auth.interface.otp_dependencies import get_code_generator
from app.contexts.iam.infrastructure.persistence.models import (
    AccountModel,
    MembershipModel,
    RoleAssignmentModel,
)
from app.core.database import Base, get_db_session
from app.main import create_app

_PHONE = "+2250700000001"
_PIN = "1234"
_OTP = "000000"
_DEVICE = "device-m1"


class _FixedCode(CodeGenerator):
    def generate(self):
        return _OTP


@pytest.fixture
async def ctx() -> AsyncGenerator[tuple[AsyncClient, async_sessionmaker]]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

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
        yield ac, factory
    app.dependency_overrides.clear()
    await engine.dispose()


async def _seed_account(factory, *, phone, pin_hash=None, created_by="owner"):
    account_id = uuid4()
    async with factory() as s:
        s.add(
            AccountModel(
                id=account_id,
                phone_number=phone,
                email=None,
                password_hash=None,
                pin_hash=pin_hash,
                hash_algo_version=HASH_ALGO_VERSION if pin_hash else None,
                is_phone_verified=False,
                is_email_verified=False,
                created_at=datetime.now(UTC),
                created_by_type=created_by,
                status="active",
            )
        )
        await s.commit()
    return account_id


async def _count_accounts(factory, phone) -> int:
    stmt = (
        select(func.count()).select_from(AccountModel).where(AccountModel.phone_number == phone)
    )
    async with factory() as s:
        return (await s.execute(stmt)).scalar_one()


async def _register(client, *, phone=_PHONE, pin=_PIN, otp=_OTP, device=_DEVICE):
    req = await client.post("/api/mobile/auth/register", json={"phone_number": phone})
    conf = await client.post(
        "/api/mobile/auth/verify-registration",
        json={"phone_number": phone, "otp": otp, "secret_code": pin, "device_id": device},
    )
    return req, conf


async def _login(client, *, phone=_PHONE, pin=_PIN, device=_DEVICE):
    return await client.post(
        "/api/mobile/auth/login",
        json={"phone_number": phone, "secret_code": pin, "device_id": device},
    )


async def test_fresh_registration_creates_account_and_logs_in(ctx):
    client, factory = ctx
    req, conf = await _register(client)

    assert req.status_code == 202
    assert conf.status_code == 200
    assert conf.json()["access_token"] and conf.json()["refresh_token"]
    # Le compte auto-inscrit peut se connecter avec son PIN.
    assert (await _login(client)).status_code == 200
    assert await _count_accounts(factory, _PHONE) == 1


async def test_registration_claims_enrolled_account_without_duplicate(ctx):
    client, factory = ctx
    # Compte enrôlé par une église, jamais activé (pas de PIN).
    seeded = await _seed_account(factory, phone=_PHONE, pin_hash=None)

    _, conf = await _register(client)
    assert conf.status_code == 200
    assert (await _login(client)).status_code == 200
    # Aucun doublon : le compte global existant a été REVENDIQUÉ (M-2).
    assert await _count_accounts(factory, _PHONE) == 1
    async with factory() as s:
        row = await s.get(AccountModel, seeded)
        assert row is not None and row.pin_hash is not None  # même compte, PIN posé


async def test_already_registered_phone_is_conflict(ctx):
    client, factory = ctx
    await _seed_account(factory, phone=_PHONE, pin_hash=Argon2PasswordHasher().hash(_PIN))

    _, conf = await _register(client)
    assert conf.status_code == 409
    assert conf.json()["error"]["code"] == "AUTH_PHONE_ALREADY_REGISTERED"


async def test_wrong_otp_is_rejected(ctx):
    client, _ = ctx
    await client.post("/api/mobile/auth/register", json={"phone_number": _PHONE})
    conf = await client.post(
        "/api/mobile/auth/verify-registration",
        json={"phone_number": _PHONE, "otp": "999999", "secret_code": _PIN, "device_id": _DEVICE},
    )
    assert conf.status_code == 401
    assert conf.json()["error"]["code"] == "AUTH_OTP_INVALID"


async def test_bad_pin_format_is_422(ctx):
    client, _ = ctx
    await client.post("/api/mobile/auth/register", json={"phone_number": _PHONE})
    conf = await client.post(
        "/api/mobile/auth/verify-registration",
        json={"phone_number": _PHONE, "otp": _OTP, "secret_code": "abc", "device_id": _DEVICE},
    )
    assert conf.status_code == 422
    assert conf.json()["error"]["code"] == "AUTH_INVALID_SECRET_CODE_FORMAT"


async def _seed_pastor_membership(factory, account_id):
    """Rattache un compte à un tenant avec le rôle pastor (lecture seule)."""
    tenant_id, membership_id = uuid4(), uuid4()
    async with factory() as s:
        s.add(
            MembershipModel(
                id=membership_id,
                account_id=account_id,
                tenant_id=tenant_id,
                status="confirmed_member",
                last_transition_at=datetime.now(UTC),
                created_at=datetime.now(UTC),
                created_by_account_id=uuid4(),
            )
        )
        s.add(
            RoleAssignmentModel(
                id=uuid4(),
                membership_id=membership_id,
                tenant_id=tenant_id,
                role="pastor",
                group_id=None,
                assigned_at=datetime.now(UTC),
                assigned_by_account_id=uuid4(),
            )
        )
        await s.commit()
    return tenant_id


async def test_me_endpoint_exposes_resolved_permissions_after_claim(ctx):
    """M-3 : après revendication mobile, `/me` renvoie is_owner + permissions résolues."""
    client, factory = ctx
    account_id = await _seed_account(factory, phone=_PHONE, pin_hash=None)
    tenant_id = await _seed_pastor_membership(factory, account_id)

    _, conf = await _register(client)  # revendique le compte, pose le PIN, connecte
    token = conf.json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}

    resp = await client.get("/api/mobile/iam/me/memberships", headers=auth)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    entry = body[0]
    assert entry["tenant_id"] == str(tenant_id)
    assert entry["is_owner"] is False
    assert [r["role"] for r in entry["active_roles"]] == ["pastor"]
    # Pasteur = lecture seule sur les **personnes** (spec §5.6). Ses actes d'écriture portent sur
    # ses propres objets : agenda, sermons, et les collectes qu'il lance — dont il ne verra
    # jamais le détail nominatif.
    assert set(entry["permissions"]) == {
        "view_member_directory",
        "view_pastoral_alerts",
        "manage_appointments",
        "publish_sermon",
        "launch_collection",
        # Diffuser au-delà de l'église est un acte **institutionnel** : c'est sa voix qui engage
        # l'église au-dehors. Le compte Business reste exigé en plus — l'un est le droit de
        # payer, l'autre celui de parler au nom d'un corps.
        "broadcast_wider",
    }


async def test_login_from_new_device_needs_otp_then_verifies(ctx):
    """M-4 : l'appareil d'inscription est de confiance ; un AUTRE appareil repasse par un OTP."""
    client, _ = ctx
    await _register(client)  # device _DEVICE devient de confiance

    # Appareil inconnu → OTP requis (202), pas de jetons.
    login = await _login(client, device="autre-appareil")
    assert login.status_code == 202
    assert login.json()["status"] == "otp_required"

    # verify-device avec l'OTP → appareil de confiance + jetons.
    verify = await client.post(
        "/api/mobile/auth/verify-device",
        json={"phone_number": _PHONE, "otp": _OTP, "device_id": "autre-appareil"},
    )
    assert verify.status_code == 200
    assert verify.json()["access_token"]

    # Désormais l'appareil est connu → login direct (200).
    assert (await _login(client, device="autre-appareil")).status_code == 200
