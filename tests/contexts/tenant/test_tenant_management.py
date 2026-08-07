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


async def _provision(client, *, email, phone, estimated_member_count=None):
    body = {
        "tenant_name": "Bethel",
        "owner_phone": phone,
        "owner_email": email,
        "owner_password": _PWD,
        "country": "CI",
    }
    if estimated_member_count is not None:
        body["estimated_member_count"] = estimated_member_count
    r = await client.post("/api/backoffice/tenants", headers=_TOKEN, json=body)
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


async def test_me_tenants_lists_only_my_churches(client: AsyncClient):
    """F1 — après login, le front découvre SES églises (l'`account_id` seul ne suffit pas)."""
    mine = await _provision(client, email="mine@x.ci", phone="+2250700000070")
    await _provision(client, email="other@x.ci", phone="+2250700000071")  # église d'un tiers

    await _login_owner(client, "mine@x.ci", "dev-mine")
    resp = await client.get("/api/backoffice/me/tenants")
    assert resp.status_code == 200
    ids = [t["tenant_id"] for t in resp.json()]
    assert ids == [mine]  # la sienne, et elle seule
    assert resp.json()[0]["slug"] is not None


async def _annexe(client, *, parent, email, phone, size=None):
    """Crée une annexe (église-fille) sous un principal — acte Plateforme."""
    body = {
        "tenant_name": "Annexe",
        "owner_phone": phone,
        "owner_email": email,
        "owner_password": _PWD,
        "parent_id": parent,
    }
    if size is not None:
        body["estimated_member_count"] = size
    r = await client.post("/api/backoffice/tenants", headers=_TOKEN, json=body)
    assert r.status_code == 201, r.text
    return r.json()["tenant_id"]


async def test_annexes_endpoint_creates_a_daughter_church(client: AsyncClient):
    """③ — l'endpoint dédié : le `parent_id` vient du CHEMIN, et l'annexe a SON owner."""
    principal = await _provision(client, email="mere@x.ci", phone="+2250700000100")
    resp = await client.post(
        f"/api/backoffice/tenants/{principal}/annexes",
        headers=_TOKEN,
        json={
            "tenant_name": "Bethel — Annexe Cocody",
            "owner_phone": "+2250700000101",
            "owner_email": "cocody@x.ci",
            "owner_password": _PWD,
            "estimated_member_count": 250,
        },
    )
    assert resp.status_code == 201
    annexe_id = resp.json()["tenant_id"]
    assert resp.json()["owner_account_id"]  # gouvernance propre

    # L'annexe est bien filiée, et son owner à elle y accède.
    await _login_owner(client, "cocody@x.ci", "dev-cocody")
    body = (await client.get(f"/api/backoffice/tenants/{annexe_id}")).json()
    assert body["is_independent"] is False
    assert body["operates_annexes"] is False  # filiation plate


async def test_annexes_endpoint_refuses_an_unknown_mother(client: AsyncClient):
    from uuid import uuid4

    resp = await client.post(
        f"/api/backoffice/tenants/{uuid4()}/annexes",
        headers=_TOKEN,
        json={
            "tenant_name": "Orpheline",
            "owner_phone": "+2250700000105",
            "owner_email": "orph@x.ci",
            "owner_password": _PWD,
        },
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "TENANT_INVALID_PARENT"


async def test_an_annexe_cannot_have_its_own_annexe(client: AsyncClient):
    """Filiation **plate** en V1 : la mère d'une annexe doit être un principal."""
    principal = await _provision(client, email="m2@x.ci", phone="+2250700000110")
    annexe = await _annexe(client, parent=principal, email="a3@x.ci", phone="+2250700000111")
    resp = await client.post(
        f"/api/backoffice/tenants/{annexe}/annexes",
        headers=_TOKEN,
        json={
            "tenant_name": "Petite-fille",
            "owner_phone": "+2250700000112",
            "owner_email": "pf@x.ci",
            "owner_password": _PWD,
        },
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "TENANT_INVALID_PARENT"


async def test_annexes_endpoint_requires_platform_token(client: AsyncClient):
    principal = await _provision(client, email="m3@x.ci", phone="+2250700000115")
    resp = await client.post(
        f"/api/backoffice/tenants/{principal}/annexes",
        json={
            "tenant_name": "X",
            "owner_phone": "+2250700000116",
            "owner_email": "x@x.ci",
            "owner_password": _PWD,
        },
    )
    assert resp.status_code == 401


async def test_family_reads_the_principal_and_its_annexes(client: AsyncClient):
    """La brique de consolidation du Church OS : le principal VOIT sa famille."""
    principal = await _provision(
        client, email="fam@x.ci", phone="+2250700000080", estimated_member_count=300
    )
    a1 = await _annexe(client, parent=principal, email="a1@x.ci", phone="+2250700000081", size=250)
    a2 = await _annexe(client, parent=principal, email="a2@x.ci", phone="+2250700000082", size=600)

    await _login_owner(client, "fam@x.ci", "dev-fam")
    resp = await client.get(f"/api/backoffice/tenants/{principal}/family")
    assert resp.status_code == 200
    body = resp.json()

    assert body["principal"]["tenant_id"] == principal
    assert {a["tenant_id"] for a in body["annexes"]} == {a1, a2}
    # Assiette d'abonnement : Σ des tailles DÉCLARÉES sur la famille (300+250+600).
    assert body["family_member_count"] == 1150
    assert body["active_annexe_count"] == 2


async def test_family_of_a_lone_church_is_itself(client: AsyncClient):
    solo = await _provision(
        client, email="solo@x.ci", phone="+2250700000085", estimated_member_count=120
    )
    await _login_owner(client, "solo@x.ci", "dev-solo")
    body = (await client.get(f"/api/backoffice/tenants/{solo}/family")).json()
    assert body["annexes"] == []
    assert body["family_member_count"] == 120
    assert body["active_annexe_count"] == 0


async def test_a_suspended_annexe_leaves_the_plan_but_stays_visible(client: AsyncClient):
    """Une annexe suspendue ne compte plus dans le plan — mais le principal la voit encore."""
    principal = await _provision(
        client, email="susp@x.ci", phone="+2250700000090", estimated_member_count=100
    )
    annexe = await _annexe(
        client, parent=principal, email="sa@x.ci", phone="+2250700000091", size=50
    )
    await client.post(f"/api/backoffice/tenants/{annexe}/suspend", headers=_TOKEN)

    await _login_owner(client, "susp@x.ci", "dev-susp")
    body = (await client.get(f"/api/backoffice/tenants/{principal}/family")).json()
    assert len(body["annexes"]) == 1  # toujours visible
    assert body["active_annexe_count"] == 0  # mais hors du plan


async def test_family_is_refused_to_a_non_owner(client: AsyncClient):
    """Subsidiarité : on ne lit pas la famille d'une église qu'on ne possède pas."""
    principal = await _provision(client, email="p1@x.ci", phone="+2250700000095")
    await _provision(client, email="p2@x.ci", phone="+2250700000096")
    await _login_owner(client, "p2@x.ci", "dev-p2")
    resp = await client.get(f"/api/backoffice/tenants/{principal}/family")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "TENANT_FORBIDDEN"


async def test_family_without_session_is_401(client: AsyncClient):
    principal = await _provision(client, email="p3@x.ci", phone="+2250700000097")
    assert (await client.get(f"/api/backoffice/tenants/{principal}/family")).status_code == 401


async def test_logout_really_kills_the_session(client: AsyncClient):
    """DOREA-016 — avant, `logout` effaçait le cookie et le jeton restait valable 12 h.

    Ici on **garde le cookie** après la déconnexion et on rejoue une requête : elle doit
    être refusée. C'est le seul test qui prouve la révocation — effacer un cookie côté
    client ne prouve rien du tout."""
    tenant = await _provision(client, email="rev@x.ci", phone="+2250700000120")
    await _login_owner(client, "rev@x.ci", "dev-rev")
    assert (await client.get(f"/api/backoffice/tenants/{tenant}")).status_code == 200

    cookie = client.cookies.get("dorea_backoffice_session")
    assert cookie is not None
    await client.post("/api/backoffice/auth/logout")

    # On rejoue le jeton **volé** : l'appareil est révoqué → refusé.
    client.cookies.set("dorea_backoffice_session", cookie)
    assert (await client.get(f"/api/backoffice/tenants/{tenant}")).status_code == 401
    assert (await client.get("/api/backoffice/auth/me")).status_code == 401


async def test_a_revoked_device_asks_for_an_otp_again(client: AsyncClient):
    """Se reconnecter après déconnexion redemande un OTP : l'appareil n'est plus de
    confiance. Et il redevient de confiance ensuite, sans buter sur l'unicité."""
    await _provision(client, email="reo@x.ci", phone="+2250700000125")
    await _login_owner(client, "reo@x.ci", "dev-reo")
    await client.post("/api/backoffice/auth/logout")

    again = await client.post(
        "/api/backoffice/auth/login",
        json={"email": "reo@x.ci", "password": _PWD, "device_id": "dev-reo"},
    )
    assert again.status_code == 202  # OTP redemandé sur le MÊME appareil
    verified = await client.post(
        "/api/backoffice/auth/verify",
        json={"email": "reo@x.ci", "otp": _OTP, "device_id": "dev-reo"},
    )
    assert verified.status_code == 204  # il redevient de confiance
    assert (await client.get("/api/backoffice/auth/me")).status_code == 200


async def test_me_tenants_without_session_is_401(client: AsyncClient):
    assert (await client.get("/api/backoffice/me/tenants")).status_code == 401


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
