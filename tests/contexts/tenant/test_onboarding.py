"""P3 — Onboarding : soumission → vérif email (OTP) → validation Dorea → l'Owner se connecte."""

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


def _submission(**over):
    base = {
        "tenant_name": "Église Bethel",
        "owner_email": "pasteur@bethel.ci",
        "owner_phone": "+2250700000001",
        "owner_password": _PWD,
        "owner_years_of_experience": 12,
        "denomination": "Assemblées de Dieu",
        "country": "CI",
        "city": "Abidjan",
    }
    base.update(over)
    return base


async def test_full_onboarding_to_owner_login(client: AsyncClient):
    # 1. Soumission (aspirant owner, public) → statut submitted + OTP email.
    sub = await client.post("/api/onboarding/submit", json=_submission())
    assert sub.status_code == 201
    assert sub.json()["status"] == "submitted"
    request_id = sub.json()["request_id"]

    # 2. Vérification de l'email par OTP → email_verified.
    ver = await client.post(
        "/api/onboarding/verify-email", json={"request_id": request_id, "otp": _OTP}
    )
    assert ver.status_code == 200
    assert ver.json()["status"] == "email_verified"

    # 3. Validation par Dorea → matérialise le tenant + owner.
    appr = await client.post(f"/api/backoffice/onboarding/{request_id}/approve", headers=_TOKEN)
    assert appr.status_code == 200
    owner_id = appr.json()["owner_account_id"]

    # 4. L'Owner se connecte au backoffice (email+password, nouvel appareil → OTP).
    login = await client.post(
        "/api/backoffice/auth/login",
        json={"email": "pasteur@bethel.ci", "password": _PWD, "device_id": "dev-1"},
    )
    assert login.status_code == 202  # OTP requis
    await client.post(
        "/api/backoffice/auth/verify",
        json={"email": "pasteur@bethel.ci", "otp": _OTP, "device_id": "dev-1"},
    )
    me = await client.get("/api/backoffice/auth/me")
    assert me.status_code == 200
    assert me.json()["account_id"] == owner_id


async def test_onboarding_carries_church_os_fields_to_materialization(client: AsyncClient):
    # Les champs M0 §2.2 saisis à la soumission survivent jusqu'au tenant matérialisé.
    sub = await client.post(
        "/api/onboarding/submit",
        json=_submission(
            owner_email="multi@pays.cm",
            owner_phone="+2370700000001",
            timezone="Africa/Douala",
            language="fr",
            currency="XAF",
            operates_annexes=True,
            contact_name="Frère Jean",
            short_description="Une église de la grâce",
        ),
    )
    request_id = sub.json()["request_id"]
    await client.post(
        "/api/onboarding/verify-email", json={"request_id": request_id, "otp": _OTP}
    )
    appr = await client.post(f"/api/backoffice/onboarding/{request_id}/approve", headers=_TOKEN)
    assert appr.status_code == 200
    tenant_id = appr.json()["tenant_id"]

    # Lu via l'annuaire Dorea (jeton de service) → les champs sont bien portés.
    listing = await client.get("/api/backoffice/tenants", headers=_TOKEN)
    tenant = next(t for t in listing.json() if t["tenant_id"] == tenant_id)
    assert tenant["timezone"] == "Africa/Douala"
    assert tenant["currency"] == "XAF"
    assert tenant["operates_annexes"] is True
    assert tenant["contact_name"] == "Frère Jean"
    assert tenant["short_description"] == "Une église de la grâce"
    assert tenant["slug"] is not None  # auto-généré à la genèse


async def test_resend_otp_lets_the_applicant_finish(client: AsyncClient):
    """F3 — le mail se perd ; la candidature ne doit pas mourir avec lui."""
    sub = await client.post("/api/onboarding/submit", json=_submission(owner_email="re@t.ci"))
    request_id = sub.json()["request_id"]

    again = await client.post(f"/api/onboarding/{request_id}/resend-otp")
    assert again.status_code == 200
    assert again.json()["status"] == "submitted"  # toujours en attente de vérification

    # Le code renvoyé vérifie bien la demande.
    ver = await client.post(
        "/api/onboarding/verify-email", json={"request_id": request_id, "otp": _OTP}
    )
    assert ver.status_code == 200
    assert ver.json()["status"] == "email_verified"


async def test_resend_otp_is_refused_once_verified(client: AsyncClient):
    """Une demande qui n'attend plus de vérification n'a plus de code à recevoir."""
    sub = await client.post("/api/onboarding/submit", json=_submission(owner_email="rv@t.ci"))
    request_id = sub.json()["request_id"]
    await client.post(
        "/api/onboarding/verify-email", json={"request_id": request_id, "otp": _OTP}
    )
    resp = await client.post(f"/api/onboarding/{request_id}/resend-otp")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "ONBOARDING_INVALID_TRANSITION"


async def test_resend_otp_on_unknown_request_is_404(client: AsyncClient):
    from uuid import uuid4

    assert (await client.post(f"/api/onboarding/{uuid4()}/resend-otp")).status_code == 404


async def test_onboarding_status_is_publicly_followable(client: AsyncClient):
    """F2 — l'écran « en attente » suit sa candidature sans compte, sans fuite du brouillon."""
    sub = await client.post("/api/onboarding/submit", json=_submission(owner_email="s@t.ci"))
    request_id = sub.json()["request_id"]

    st = await client.get(f"/api/onboarding/{request_id}")
    assert st.status_code == 200
    assert st.json()["status"] == "submitted"
    assert st.json()["submitted_at"] is not None
    # Aucune donnée sensible du brouillon n'est exposée.
    for leaked in ("owner_email", "owner_password_hash", "owner_phone", "tenant_name"):
        assert leaked not in st.json()

    await client.post(
        "/api/onboarding/verify-email", json={"request_id": request_id, "otp": _OTP}
    )
    assert (await client.get(f"/api/onboarding/{request_id}")).json()["status"] == "email_verified"


async def test_onboarding_status_exposes_rejection_reason(client: AsyncClient):
    sub = await client.post("/api/onboarding/submit", json=_submission(owner_email="r@t.ci"))
    request_id = sub.json()["request_id"]
    await client.post(
        f"/api/backoffice/onboarding/{request_id}/reject",
        headers=_TOKEN,
        json={"reason": "Église non vérifiable"},
    )
    body = (await client.get(f"/api/onboarding/{request_id}")).json()
    assert body["status"] == "rejected"
    assert body["rejection_reason"] == "Église non vérifiable"
    assert body["decided_at"] is not None


async def test_unknown_onboarding_status_is_404(client: AsyncClient):
    from uuid import uuid4

    assert (await client.get(f"/api/onboarding/{uuid4()}")).status_code == 404


async def test_approve_before_email_verified_is_rejected(client: AsyncClient):
    sub = await client.post("/api/onboarding/submit", json=_submission(owner_email="a@b.ci"))
    request_id = sub.json()["request_id"]
    # Pas de vérif email → approbation refusée (transition invalide).
    appr = await client.post(f"/api/backoffice/onboarding/{request_id}/approve", headers=_TOKEN)
    assert appr.status_code == 409
    assert appr.json()["error"]["code"] == "ONBOARDING_INVALID_TRANSITION"


async def test_reject_flow(client: AsyncClient):
    sub = await client.post("/api/onboarding/submit", json=_submission(owner_email="c@d.ci"))
    request_id = sub.json()["request_id"]
    rej = await client.post(
        f"/api/backoffice/onboarding/{request_id}/reject",
        headers=_TOKEN,
        json={"reason": "Église non vérifiable"},
    )
    assert rej.status_code == 200
    assert rej.json()["status"] == "rejected"


async def test_approve_requires_platform_token(client: AsyncClient):
    rid = get_settings().platform_account_id
    resp = await client.post(f"/api/backoffice/onboarding/{rid}/approve")
    assert resp.status_code == 401


async def test_wrong_email_otp_is_rejected(client: AsyncClient):
    sub = await client.post("/api/onboarding/submit", json=_submission(owner_email="e@f.ci"))
    request_id = sub.json()["request_id"]
    ver = await client.post(
        "/api/onboarding/verify-email", json={"request_id": request_id, "otp": "999999"}
    )
    assert ver.status_code == 401
