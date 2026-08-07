"""Les trois courses fermées par la base — DOREA-008 / 009 / 010.

Chacune était une garde applicative qui lisait « c'est libre » **avant** d'écrire. Sous
concurrence, deux requêtes lisaient toutes deux « libre », et toutes deux écrivaient. Un test
qui passe par le use case ne prouve donc rien : il ne teste qu'une garde qui, précisément,
ne tient pas sous charge.

Ces tests écrivent **directement en base**, sans passer par l'application. C'est le seul
moyen de prouver que la contrainte **mord** — et non qu'un `if` a été poli.

Chaque course a son jumeau : le cas **légitime** qui doit rester permis. Une contrainte qui
interdit trop est une régression, pas une correction.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.contexts.appointments.infrastructure.persistence.models import AppointmentModel
from app.contexts.attendance.infrastructure.persistence.models import GatheringModel
from app.contexts.iam.infrastructure.persistence.models import AccountModel, MembershipModel
from app.core.database import Base

_NOW = datetime(2026, 8, 3, tzinfo=UTC)
_SUNDAY = datetime(2026, 8, 2, tzinfo=UTC)  # minuit du dimanche — la clé du culte (S-4)


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as opened:
        yield opened
    await engine.dispose()


async def _account(session) -> uuid4:
    account_id = uuid4()
    session.add(
        AccountModel(
            id=account_id,
            phone_number=f"+225{uuid4().int % 10**8:08d}",
            created_at=_NOW,
            created_by_type="owner",
            status="active",
        )
    )
    await session.flush()
    return account_id


def _membership(account_id, tenant_id, *, closed_at=None) -> MembershipModel:
    return MembershipModel(
        id=uuid4(),
        account_id=account_id,
        tenant_id=tenant_id,
        status="closed" if closed_at else "confirmed_member",
        last_transition_at=_NOW,
        created_at=_NOW,
        created_by_account_id=uuid4(),
        closed_at=closed_at,
    )


# ------------------------------------------------------- DOREA-008 · appartenance


async def test_008_la_base_refuse_deux_appartenances_actives(session):
    """Deux enrôlements concurrents : la personne existait deux fois dans son église."""
    account_id, tenant_id = await _account(session), uuid4()
    session.add(_membership(account_id, tenant_id))
    await session.flush()

    session.add(_membership(account_id, tenant_id))
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_008_revenir_dans_une_eglise_quittee_reste_permis(session):
    """Le jumeau légitime : une appartenance **close** n'empêche pas la nouvelle."""
    account_id, tenant_id = await _account(session), uuid4()
    session.add(_membership(account_id, tenant_id, closed_at=_NOW - timedelta(days=365)))
    await session.flush()

    session.add(_membership(account_id, tenant_id))  # il revient
    await session.flush()  # ne lève pas


async def test_008_la_meme_personne_dans_deux_eglises_reste_permise(session):
    """Identité globale : un compte, N appartenances — dans des églises différentes."""
    account_id = await _account(session)
    session.add_all([_membership(account_id, uuid4()), _membership(account_id, uuid4())])
    await session.flush()  # ne lève pas


# ------------------------------------------------------- DOREA-009 · culte du jour


def _gathering(tenant_id, *, group_id=None, kind="service", at=_SUNDAY) -> GatheringModel:
    return GatheringModel(
        id=uuid4(),
        tenant_id=tenant_id,
        group_id=group_id,
        type=kind,
        scheduled_at=at,
        status="open",
        created_by_account_id=uuid4(),
        created_at=_NOW,
    )


async def test_009_la_base_refuse_deux_cultes_le_meme_jour(session):
    """Deux « oui » simultanés au compagnon : l'assemblée se scindait en deux cultes."""
    tenant_id = uuid4()
    session.add(_gathering(tenant_id))
    await session.flush()

    session.add(_gathering(tenant_id))  # même église, même type, même minuit
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_009_deux_cellules_peuvent_se_reunir_en_meme_temps(session):
    """Le jumeau légitime : l'index ne vise que l'**église-entière** (`group_id IS NULL`)."""
    tenant_id = uuid4()
    session.add_all(
        [_gathering(tenant_id, group_id=uuid4()), _gathering(tenant_id, group_id=uuid4())]
    )
    await session.flush()  # ne lève pas


async def test_009_une_autre_eglise_nest_pas_genee(session):
    session.add_all([_gathering(uuid4()), _gathering(uuid4())])
    await session.flush()  # ne lève pas


# ------------------------------------------------------- DOREA-010 · créneau RDV


def _appointment(pastor_id, at, *, status="confirmed") -> AppointmentModel:
    return AppointmentModel(
        id=uuid4(),
        tenant_id=uuid4(),
        requester_account_id=uuid4(),
        with_pastor_account_id=pastor_id,
        category="counsel",
        subject="—",
        status=status,
        scheduled_at=at,
        created_at=_NOW,
        updated_at=_NOW,
    )


async def test_010_la_base_refuse_deux_rdv_confirmes_sur_le_meme_creneau(session):
    """Deux personnes se présentaient à la même heure — et le pasteur portait la faute."""
    pastor_id, slot = uuid4(), _NOW + timedelta(days=1)
    session.add(_appointment(pastor_id, slot))
    await session.flush()

    session.add(_appointment(pastor_id, slot))
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_010_les_demandes_en_attente_ne_bloquent_rien(session):
    """Le jumeau légitime : plusieurs personnes peuvent **demander** le même créneau ;
    seule la **confirmation** est exclusive. Sinon le premier demandeur préempterait."""
    pastor_id, slot = uuid4(), _NOW + timedelta(days=1)
    session.add_all(
        [
            _appointment(pastor_id, slot, status="requested"),
            _appointment(pastor_id, slot, status="requested"),
        ]
    )
    await session.flush()  # ne lève pas


async def test_010_un_creneau_honore_se_libere(session):
    """Une fois la rencontre honorée, le créneau — passé — ne bloque plus."""
    pastor_id, slot = uuid4(), _NOW - timedelta(days=7)
    session.add(_appointment(pastor_id, slot, status="honored"))
    await session.flush()

    session.add(_appointment(pastor_id, slot))  # confirmé au même horaire passé
    await session.flush()  # ne lève pas


async def test_010_deux_pasteurs_au_meme_moment(session):
    slot = _NOW + timedelta(days=1)
    session.add_all([_appointment(uuid4(), slot), _appointment(uuid4(), slot)])
    await session.flush()  # ne lève pas
