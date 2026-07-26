"""Sprint 2/P2 — provisionnement (persistance atomique) + parcours backoffice e2e.

Contre SQLite in-memory (StaticPool). L'Owner se connecte en **email + mot de passe**
et, sur un nouvel appareil, via **OTP** (code déterministe en test).
"""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.contexts.auth.application.ports import CodeGenerator
from app.contexts.auth.infrastructure.hashing import HASH_ALGO_VERSION, Argon2PasswordHasher
from app.contexts.auth.interface.backoffice_dependencies import get_code_generator
from app.contexts.iam.infrastructure.persistence.models import (
    AccountModel,
    MembershipModel,
    RoleAssignmentModel,
)
from app.contexts.tenant.application.commands.provision_tenant import ProvisionTenant
from app.contexts.tenant.application.dtos import ProvisionTenantRequest
from app.contexts.tenant.infrastructure.persistence.models import OwnershipModel, TenantModel
from app.contexts.tenant.infrastructure.persistence.store import SqlProvisioningStore
from app.contexts.tenant.infrastructure.persistence.tenant_repo import SqlTenantRepository
from app.core.config import get_settings
from app.core.database import Base, get_db_session
from app.main import create_app

_NOW = datetime(2026, 1, 1, tzinfo=UTC)
_PLATFORM = get_settings().platform_account_id
_TOKEN = {"X-Service-Token": get_settings().backoffice_service_token}
_PWD = "MotDePasse#2026"
_OTP = "000000"


class _FixedCode(CodeGenerator):
    def generate(self):
        return _OTP


def _sqlite_engine():
    return create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


async def _create_schema(engine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# --- Tests de persistance (store direct) ---


@pytest.fixture
async def session() -> AsyncGenerator[AsyncSession]:
    engine = _sqlite_engine()
    await _create_schema(engine)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


def _command(session: AsyncSession) -> ProvisionTenant:
    return ProvisionTenant(
        SqlProvisioningStore(session),
        SqlTenantRepository(session),
        platform_account_id=_PLATFORM,
        clock=lambda: _NOW,
        hasher=Argon2PasswordHasher(),
        hash_algo_version=HASH_ALGO_VERSION,
    )


def _request(**over) -> ProvisionTenantRequest:
    base = {
        "tenant_name": "Église Bethel",
        "owner_phone": "+2250700000001",
        "owner_email": "owner@bethel.ci",
        "owner_password": _PWD,
    }
    base.update(over)
    return ProvisionTenantRequest(**base)


async def test_provision_writes_the_four_rows_atomically(session: AsyncSession):
    result = await _command(session).execute(_request(owner_first_name="Emmanuel"))
    await session.commit()

    tenant = await session.get(TenantModel, result.tenant_id)
    assert tenant is not None and tenant.name == "Église Bethel"

    account = await session.get(AccountModel, result.owner_account_id)
    assert account.created_by_type == "owner"
    assert account.email == "owner@bethel.ci"  # identifiant de connexion

    membership = await session.get(MembershipModel, result.owner_membership_id)
    assert membership.status == "confirmed_member"
    assert membership.created_by_account_id == _PLATFORM

    # L'Owner n'a PAS de rôle : la gouvernance est portée par l'Ownership.
    roles = (await session.execute(select(RoleAssignmentModel))).scalars().all()
    assert roles == []

    ownerships = (await session.execute(select(OwnershipModel))).scalars().all()
    assert len(ownerships) == 1
    assert ownerships[0].status == "active" and ownerships[0].mode == "bootstrap"


async def test_partial_unique_index_blocks_a_second_active_ownership(session: AsyncSession):
    result = await _command(session).execute(_request(owner_phone="+2250700000002"))
    await session.commit()

    session.add(
        OwnershipModel(
            id=uuid4(),
            account_id=uuid4(),
            tenant_id=result.tenant_id,
            status="active",
            mode="succession",
            started_at=_NOW,
            ended_at=None,
        )
    )
    with pytest.raises(IntegrityError):
        await session.commit()


# --- Endpoint backoffice + parcours e2e ---


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient]:
    engine = _sqlite_engine()
    await _create_schema(engine)
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
        yield ac
    app.dependency_overrides.clear()
    await engine.dispose()


async def _provision(client: AsyncClient, *, email, phone, password=_PWD, **over):
    body = {
        "tenant_name": "Bethel",
        "owner_phone": phone,
        "owner_email": email,
        "owner_password": password,
        **over,
    }
    return await client.post("/api/backoffice/tenants", headers=_TOKEN, json=body)


async def _login_owner(client: AsyncClient, email, password=_PWD, device_id="dev-1"):
    """Login backoffice complet : email+password, puis OTP si nouvel appareil."""
    r = await client.post(
        "/api/backoffice/auth/login",
        json={"email": email, "password": password, "device_id": device_id},
    )
    if r.status_code == 202:  # nouvel appareil → vérifier l'OTP
        await client.post(
            "/api/backoffice/auth/verify",
            json={"email": email, "otp": _OTP, "device_id": device_id},
        )


async def test_provision_endpoint_creates_tenant(client: AsyncClient):
    resp = await _provision(client, email="a@bethel.ci", phone="+2250700000009")
    assert resp.status_code == 201
    body = resp.json()
    assert body["tenant_id"] and body["owner_account_id"] and body["owner_membership_id"]


async def test_provisioned_owner_can_log_into_backoffice(client: AsyncClient):
    prov = await _provision(client, email="owner21@bethel.ci", phone="+2250700000021")
    owner_id = prov.json()["owner_account_id"]

    await _login_owner(client, "owner21@bethel.ci")
    me = await client.get("/api/backoffice/auth/me")
    assert me.status_code == 200
    assert me.json()["account_id"] == owner_id


async def test_owner_enrolls_a_pastor_end_to_end(client: AsyncClient):
    prov = await _provision(client, email="owner31@bethel.ci", phone="+2250700000031")
    tenant_id = prov.json()["tenant_id"]
    await _login_owner(client, "owner31@bethel.ci")

    enroll = await client.post(
        f"/api/backoffice/iam/tenants/{tenant_id}/members",
        json={
            "role": "pastor",
            "phone_number": "+2250700000032",
            "first_name": "Paul",
        },
    )
    assert enroll.status_code == 201
    assert enroll.json()["role"] == "pastor"


async def test_enroll_without_session_is_401(client: AsyncClient):
    resp = await client.post(
        f"/api/backoffice/iam/tenants/{uuid4()}/members",
        json={"role": "admin", "phone_number": "+2250700000040"},
    )
    assert resp.status_code == 401


async def test_transition_without_session_is_401(client: AsyncClient):
    resp = await client.post(
        f"/api/backoffice/iam/tenants/{uuid4()}/members/{uuid4()}/transitions",
        json={"event": "confirm_member"},
    )
    assert resp.status_code == 401


async def test_owner_closes_a_membership_and_account_survives(client: AsyncClient):
    prov = await _provision(client, email="owner41@bethel.ci", phone="+2250700000041")
    tenant_id = prov.json()["tenant_id"]
    await _login_owner(client, "owner41@bethel.ci")

    enroll = await client.post(
        f"/api/backoffice/iam/tenants/{tenant_id}/members",
        json={"role": "pastor", "phone_number": "+2250700000042"},
    )
    pastor_id = enroll.json()["account_id"]

    close = await client.post(
        f"/api/backoffice/iam/tenants/{tenant_id}/members/{pastor_id}/close",
        json={"closure_reason": "changed_church"},
    )
    assert close.status_code == 200
    assert close.json()["status"] == "closed"

    # Le compte GLOBAL survit à la clôture : ré-enrôler le même téléphone RÉUTILISE
    # le compte (M-2) au lieu d'en recréer un → même account_id.
    re_enroll = await client.post(
        f"/api/backoffice/iam/tenants/{tenant_id}/members",
        json={"role": "pastor", "phone_number": "+2250700000042"},
    )
    assert re_enroll.status_code == 201
    assert re_enroll.json()["account_id"] == pastor_id


async def test_full_status_journey_end_to_end(client: AsyncClient):
    prov = await _provision(client, email="owner43@bethel.ci", phone="+2250700000043")
    tenant_id = prov.json()["tenant_id"]
    await _login_owner(client, "owner43@bethel.ci")

    invited = await client.post(
        f"/api/backoffice/iam/tenants/{tenant_id}/invited-members",
        json={"phone_number": "+2250700000044", "first_name": "Awa"},
    )
    assert invited.status_code == 201
    member_id = invited.json()["account_id"]

    async def _transition(event: str):
        return await client.post(
            f"/api/backoffice/iam/tenants/{tenant_id}/members/{member_id}/transitions",
            json={"event": event},
        )

    steps = [
        ("first_attendance_recorded", "visitor"),
        ("qualify_sympathizer", "sympathizer"),
        ("qualify_newcomer", "newcomer"),
        ("confirm_member", "confirmed_member"),
    ]
    for event, expected in steps:
        resp = await _transition(event)
        assert resp.status_code == 200
        assert resp.json()["status"] == expected


async def test_member_import_end_to_end(client: AsyncClient):
    prov = await _provision(client, email="owner45@bethel.ci", phone="+2250700000045")
    tenant_id = prov.json()["tenant_id"]
    await _login_owner(client, "owner45@bethel.ci")

    imp = await client.post(
        f"/api/backoffice/iam/tenants/{tenant_id}/members/import",
        json={
            "members": [
                {"phone_number": "+2250700000046", "first_name": "Awa"},
                {"phone_number": "+2250700000047", "first_name": "Koffi"},
                {"phone_number": "+2250700000045"},  # = l'Owner → déjà existant
            ]
        },
    )
    assert imp.status_code == 200
    body = imp.json()
    assert body["enrolled_count"] == 2
    assert body["failed_count"] == 1


async def test_close_and_revoke_without_session_are_401(client: AsyncClient):
    close = await client.post(
        f"/api/backoffice/iam/tenants/{uuid4()}/members/{uuid4()}/close",
        json={"closure_reason": "other"},
    )
    assert close.status_code == 401
    revoke = await client.post(
        f"/api/backoffice/iam/tenants/{uuid4()}/members/{uuid4()}/revoke-role",
        json={"role": "welcome_team"},
    )
    assert revoke.status_code == 401


async def test_provision_endpoint_without_token_is_401(client: AsyncClient):
    resp = await client.post(
        "/api/backoffice/tenants",
        json={
            "tenant_name": "Bethel",
            "owner_phone": "+2250700000010",
            "owner_email": "x@bethel.ci",
            "owner_password": _PWD,
        },
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "TENANT_PLATFORM_AUTH_REQUIRED"
