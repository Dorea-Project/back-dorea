"""Supprimer son compte — ce que la politique de confidentialité promettait.

Loi ivoirienne n° 2013-450, reprise mot pour mot dans l'application : « Tu peux
supprimer ton compte et tout son contenu à tout moment. » Le contenu part vraiment ;
la ligne du compte reste, vidée de ce qui désignait quelqu'un.
"""

from collections.abc import AsyncGenerator
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.contexts.auth.application.ports import CodeGenerator
from app.contexts.auth.infrastructure.hashing import HASH_ALGO_VERSION, Argon2PasswordHasher
from app.contexts.auth.interface.otp_dependencies import get_code_generator
from app.contexts.iam.infrastructure.persistence.models import AccountModel
from app.contexts.urim.infrastructure.persistence.models import (
    UrimCaptureModel,
    UrimDeliverableModel,
    UrimPreachedModel,
    UrimPreparationModel,
    UrimTranscriptSegmentModel,
)
from app.core.database import Base, get_db_session
from app.main import create_app

_PHONE = "+2250700000042"
_PIN = "1234"
_OTP = "000000"
_DEVICE = "device-suppression"

_ACCOUNT = UUID("11111111-1111-1111-1111-111111111111")
_AUTRE = UUID("22222222-2222-2222-2222-222222222222")


class _FixedCode(CodeGenerator):
    def generate(self):
        return _OTP


def _preparation(author_id: UUID) -> UrimPreparationModel:
    return UrimPreparationModel(
        id=uuid4(),
        church_id=None,
        author_id=author_id,
        raw_input="Marc 10.46-52",
        service_timezone="Africa/Abidjan",
        status="ouverte",
        opened_at=datetime.now(UTC),
    )


def _capture(author_id: UUID) -> UrimCaptureModel:
    return UrimCaptureModel(
        id=uuid4(),
        church_id=uuid4(),
        author_id=author_id,
        preached_on=date(2026, 8, 16),
        service_timezone="Africa/Abidjan",
        audio_purge_at=datetime.now(UTC),
        state="transcrite",
        created_at=datetime.now(UTC),
    )


@pytest.fixture
async def factory():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async with maker() as s:
        s.add(
            AccountModel(
                id=_ACCOUNT,
                phone_number=_PHONE,
                email="pasteur@example.ci",
                first_name="Kouassi",
                last_name="Yao",
                password_hash=None,
                pin_hash=Argon2PasswordHasher().hash(_PIN),
                hash_algo_version=HASH_ALGO_VERSION,
                is_phone_verified=True,
                is_email_verified=False,
                created_at=datetime.now(UTC),
                created_by_type="self_service",
                status="active",
            )
        )

        # Le contenu du titulaire : une préparation, son livrable, une archive de
        # prédication, une capture et son transcript. Les deux premières relations
        # n'ont pas de cascade — c'est ce que l'ordre d'effacement doit tenir.
        preparation = _preparation(_ACCOUNT)
        capture = _capture(_ACCOUNT)
        s.add_all([preparation, capture])
        s.add_all(
            [
                UrimDeliverableModel(
                    id=uuid4(),
                    preparation_id=preparation.id,
                    kind="note",
                    format="docx",
                    generated_at=datetime.now(UTC),
                ),
                UrimPreachedModel(
                    id=uuid4(),
                    preparation_id=preparation.id,
                    church_id=None,
                    author_id=_ACCOUNT,
                    preached_on=date(2026, 8, 16),
                ),
                UrimTranscriptSegmentModel(
                    capture_id=capture.id,
                    ordinal=1,
                    body="Que veux-tu que je fasse pour toi ?",
                    started_ms=0,
                    ended_ms=2400,
                    confidence=0.94,
                ),
            ]
        )

        # Le contenu d'un autre pasteur, qui ne doit pas bouger d'un pouce.
        s.add(_preparation(_AUTRE))
        await s.commit()

    yield maker
    await engine.dispose()


@pytest.fixture
async def client(factory) -> AsyncGenerator[AsyncClient]:
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


async def _token(client: AsyncClient) -> str:
    login = await client.post(
        "/api/mobile/auth/login",
        json={"phone_number": _PHONE, "secret_code": _PIN, "device_id": _DEVICE},
    )
    assert login.status_code == 202
    verify = await client.post(
        "/api/mobile/auth/verify-device",
        json={"phone_number": _PHONE, "otp": _OTP, "device_id": _DEVICE},
    )
    return verify.json()["access_token"]


async def _compter(factory, model, **critere) -> int:
    async with factory() as s:
        rows = (await s.scalars(select(model))).all()
        return len([r for r in rows if all(getattr(r, k) == v for k, v in critere.items())])


async def test_suppression_efface_le_contenu_et_ferme_le_compte(client, factory):
    auth = {"Authorization": f"Bearer {await _token(client)}"}

    assert (
        await client.post("/api/mobile/account/delete/request", headers=auth)
    ).status_code == 202

    confirm = await client.post(
        "/api/mobile/account/delete/confirm", headers=auth, json={"otp": _OTP}
    )
    assert confirm.status_code == 204

    # Le contenu du titulaire n'existe plus, jusqu'aux enfants sans cascade.
    assert await _compter(factory, UrimPreparationModel, author_id=_ACCOUNT) == 0
    assert await _compter(factory, UrimDeliverableModel) == 0
    assert await _compter(factory, UrimPreachedModel) == 0
    assert await _compter(factory, UrimCaptureModel) == 0
    assert await _compter(factory, UrimTranscriptSegmentModel) == 0

    # Celui du voisin est intact : on supprime un compte, pas une table.
    assert await _compter(factory, UrimPreparationModel, author_id=_AUTRE) == 1

    async with factory() as s:
        account = await s.get(AccountModel, _ACCOUNT)

    assert account is not None, "la ligne survit — la vie d'église s'y accroche"
    assert account.status == "closed"
    assert account.phone_number == f"deleted:{_ACCOUNT}"
    assert account.email is None
    assert account.first_name is None and account.last_name is None
    assert account.pin_hash is None


async def test_le_numero_redevient_libre(client):
    auth = {"Authorization": f"Bearer {await _token(client)}"}
    await client.post("/api/mobile/account/delete/request", headers=auth)
    await client.post("/api/mobile/account/delete/confirm", headers=auth, json={"otp": _OTP})

    # Plus personne ne se connecte à ce compte…
    assert (
        await client.post(
            "/api/mobile/auth/login",
            json={"phone_number": _PHONE, "secret_code": _PIN, "device_id": _DEVICE},
        )
    ).status_code == 401

    # …et le numéro peut repartir à zéro : une pierre tombale ne le retient pas.
    assert (
        await client.post("/api/mobile/auth/register", json={"phone_number": _PHONE})
    ).status_code == 202


async def test_le_jeton_meurt_avec_le_compte(client):
    auth = {"Authorization": f"Bearer {await _token(client)}"}
    await client.post("/api/mobile/account/delete/request", headers=auth)
    await client.post("/api/mobile/account/delete/confirm", headers=auth, json={"otp": _OTP})

    # Le même jeton, encore valide par sa signature : l'appareil a été révoqué, donc
    # la porte est fermée sans attendre l'expiration.
    assert (
        await client.post("/api/mobile/account/delete/request", headers=auth)
    ).status_code == 401


async def test_sans_code_rien_ne_part(client, factory):
    auth = {"Authorization": f"Bearer {await _token(client)}"}

    refus = await client.post(
        "/api/mobile/account/delete/confirm", headers=auth, json={"otp": _OTP}
    )
    assert refus.status_code >= 400, "aucun défi n'a été émis"
    assert await _compter(factory, UrimPreparationModel, author_id=_ACCOUNT) == 1


async def test_un_code_d_un_autre_motif_ne_supprime_pas(client, factory):
    """Le motif est ce qui empêche un OTP de voyager d'une porte à l'autre."""
    auth = {"Authorization": f"Bearer {await _token(client)}"}

    # Un code demandé pour changer le code secret — même numéro, même valeur.
    assert (
        await client.post("/api/mobile/account/change-password/request", headers=auth)
    ).status_code == 202

    refus = await client.post(
        "/api/mobile/account/delete/confirm", headers=auth, json={"otp": _OTP}
    )
    assert refus.status_code >= 400
    assert await _compter(factory, UrimPreparationModel, author_id=_ACCOUNT) == 1
