"""P4 — Gestion du Tenant : Owner lit/édite SON église ; Dorea liste/suspend."""

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.contexts.auth.application.ports import CodeGenerator
from app.contexts.auth.interface.backoffice_dependencies import get_code_generator
from app.core.config import get_settings
from app.core.database import Base, get_db_session
from app.main import create_app

_TOKEN = {"X-Service-Token": get_settings().backoffice_service_token}
_OTP = "000000"
_PWD = "MotDePasse#2026"


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


async def _provision(client, *, email, phone):
    r = await client.post(
        "/api/backoffice/tenants",
        headers=_TOKEN,
        json={
            "tenant_name": "Bethel",
            "owner_phone": phone,
            "owner_email": email,
            "owner_password": _PWD,
            "country": "CI",
        },
    )
    return r.json()["tenant_id"]


async def _login_owner(client, email, device_id):
    r = await client.post(
        "/api/backoffice/auth/login",
        json={"email": email, "password": _PWD, "device_id": device_id},
    )
    if r.status_code == 202:
        await client.post(
            "/api/backoffice/auth/verify",
            json={"email": email, "otp": _OTP, "device_id": device_id},
        )


async def test_owner_reads_and_edits_own_tenant(client: AsyncClient):
    tenant_id = await _provision(client, email="o1@bethel.ci", phone="+2250700000001")
    await _login_owner(client, "o1@bethel.ci", "dev-1")

    read = await client.get(f"/api/backoffice/tenants/{tenant_id}")
    assert read.status_code == 200
    assert read.json()["country"] == "CI"
    assert read.json()["status"] == "active"

    patch = await client.patch(
        f"/api/backoffice/tenants/{tenant_id}",
        json={
            "denomination": "Assemblées de Dieu",
            "city": "Abidjan",
            "estimated_member_count": 200,
        },
    )
    assert patch.status_code == 200
    assert patch.json()["denomination"] == "Assemblées de Dieu"
    assert patch.json()["city"] == "Abidjan"
    assert patch.json()["estimated_member_count"] == 200


async def test_non_owner_cannot_read_tenant(client: AsyncClient):
    t1 = await _provision(client, email="a@x.ci", phone="+2250700000010")
    await _provision(client, email="b@x.ci", phone="+2250700000011")
    # b se connecte et tente de lire l'église de a → 403.
    await _login_owner(client, "b@x.ci", "dev-b")
    resp = await client.get(f"/api/backoffice/tenants/{t1}")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "TENANT_FORBIDDEN"


async def test_read_without_session_is_401(client: AsyncClient):
    t1 = await _provision(client, email="c@x.ci", phone="+2250700000020")
    assert (await client.get(f"/api/backoffice/tenants/{t1}")).status_code == 401


async def test_dorea_lists_and_suspends(client: AsyncClient):
    t1 = await _provision(client, email="d@x.ci", phone="+2250700000030")

    listing = await client.get("/api/backoffice/tenants", headers=_TOKEN)
    assert listing.status_code == 200
    assert any(t["tenant_id"] == t1 for t in listing.json())

    susp = await client.post(f"/api/backoffice/tenants/{t1}/suspend", headers=_TOKEN)
    assert susp.status_code == 200
    assert susp.json()["status"] == "suspended"

    react = await client.post(f"/api/backoffice/tenants/{t1}/reactivate", headers=_TOKEN)
    assert react.json()["status"] == "active"


async def test_list_requires_platform_token(client: AsyncClient):
    assert (await client.get("/api/backoffice/tenants")).status_code == 401


async def test_transfer_ownership_removes_old_owner(client: AsyncClient):
    tenant_id = await _provision(client, email="succ@x.ci", phone="+2250700000050")
    await _login_owner(client, "succ@x.ci", "dev-s")
    assert (await client.get(f"/api/backoffice/tenants/{tenant_id}")).status_code == 200  # owner

    # Le futur titulaire doit être un membre confirmé de CETTE église.
    enroll = await client.post(
        f"/api/backoffice/iam/tenants/{tenant_id}/members",
        headers=_TOKEN,
        json={"role": "pastor", "phone_number": "+2250700000051"},
    )
    assert enroll.status_code == 201
    new_owner = enroll.json()["account_id"]

    transfer = await client.post(
        f"/api/backoffice/tenants/{tenant_id}/transfer-ownership",
        headers=_TOKEN,
        json={"new_owner_account_id": new_owner},
    )
    assert transfer.status_code == 200
    assert transfer.json()["new_owner_account_id"] == new_owner

    # L'ancien Owner n'est plus propriétaire → lecture refusée.
    assert (await client.get(f"/api/backoffice/tenants/{tenant_id}")).status_code == 403


async def test_transfer_ownership_rejects_non_member(client: AsyncClient):
    """On ne confie pas une église à un compte étranger/inexistant : rejet AVANT
    de clôturer l'ancien siège (pas de tenant orphelin)."""
    from uuid import uuid4

    tenant_id = await _provision(client, email="succ2@x.ci", phone="+2250700000060")

    resp = await client.post(
        f"/api/backoffice/tenants/{tenant_id}/transfer-ownership",
        headers=_TOKEN,
        json={"new_owner_account_id": str(uuid4())},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "TENANT_NEW_OWNER_NOT_ELIGIBLE"

    # L'ancien Owner garde son siège (le transfert a échoué avant toute mutation).
    await _login_owner(client, "succ2@x.ci", "dev-s2")
    assert (await client.get(f"/api/backoffice/tenants/{tenant_id}")).status_code == 200
