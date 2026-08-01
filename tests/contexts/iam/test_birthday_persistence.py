"""Le cercle de l'anniversaire, contre une vraie base — **les gens de mes groupes**.

Pas l'église. Dans une assemblée de huit cents personnes, un encart qui afficherait douze
anniversaires par jour serait du bruit, et le douzième nom n'appellerait aucun geste. C'est le
groupe qui donne le cercle, parce que c'est là qu'on se connaît.

Et une vérification qui vaut plus que sa longueur : **l'année n'est pas dans la requête**. Ce qui
n'est pas lu ne peut pas fuir dans un log, une trace, ou un DTO écrit trop vite.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.contexts.groups.domain.membership import GroupMembershipStatus
from app.contexts.groups.infrastructure.persistence.models import GroupMembershipModel
from app.contexts.iam.domain.birthday import BirthdayScope
from app.contexts.iam.infrastructure.persistence.birthday_directory import (
    SqlBirthdayDirectory,
    SqlBirthdayStore,
)
from app.contexts.iam.infrastructure.persistence.models import AccountModel
from app.core.database import Base

_NOW = datetime(2026, 6, 12, tzinfo=UTC)


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as opened:
        yield opened
    await engine.dispose()


def _account(*, first="Awa", day=12, month=6, year=None, scope=BirthdayScope.GROUPS):
    return AccountModel(
        id=uuid4(), phone_number=f"+225{uuid4().int % 10**8:08d}", first_name=first,
        last_name="Diallo", birth_day=day, birth_month=month, birth_year=year,
        birthday_scope=scope.value, is_phone_verified=True, is_email_verified=False,
        created_at=_NOW, created_by_type="self", status="active",
    )


def _in_group(account, group_id, tenant, *, status=GroupMembershipStatus.ACTIVE):
    return GroupMembershipModel(
        id=uuid4(), group_id=group_id, account_id=account.id, tenant_id=tenant,
        status=status.value, joined_at=_NOW, joined_by_account_id=account.id,
    )


async def test_the_circle_is_my_groups_not_my_church(session):
    """Celui d'une autre cellule n'apparaît pas — même église, autre cercle."""
    tenant, bethel, siloe = uuid4(), uuid4(), uuid4()
    me, near, far = _account(first="Moi"), _account(first="Awa"), _account(first="Fatou")
    session.add_all([
        me, near, far,
        _in_group(me, bethel, tenant),
        _in_group(near, bethel, tenant),
        _in_group(far, siloe, tenant),
    ])
    await session.flush()

    rows = await SqlBirthdayDirectory(session).candidates(
        viewer_account_id=me.id, tenant_id=tenant
    )

    assert {r[1] for r in rows} == {"Moi", "Awa"}  # le filtre du jour se fait au-dessus


async def test_someone_who_left_the_group_is_out_of_the_circle(session):
    tenant, bethel = uuid4(), uuid4()
    me, gone = _account(first="Moi"), _account(first="Awa")
    session.add_all([
        me, gone,
        _in_group(me, bethel, tenant),
        _in_group(gone, bethel, tenant, status=GroupMembershipStatus.LEFT),
    ])
    await session.flush()

    rows = await SqlBirthdayDirectory(session).candidates(
        viewer_account_id=me.id, tenant_id=tenant
    )

    assert {r[1] for r in rows} == {"Moi"}


async def test_the_year_is_never_selected(session):
    """L'âge de quelqu'un n'est pas une donnée d'église : il ne sort pas de la base.

    Six colonnes exactement — et la ligne rendue n'a **aucune** place où l'année pourrait tenir,
    même si quelqu'un l'a donnée."""
    tenant, bethel = uuid4(), uuid4()
    me = _account(first="Moi")
    awa = _account(first="Awa", year=1994)
    session.add_all([me, awa, _in_group(me, bethel, tenant), _in_group(awa, bethel, tenant)])
    await session.flush()

    rows = await SqlBirthdayDirectory(session).candidates(
        viewer_account_id=me.id, tenant_id=tenant
    )

    assert all(len(row) == 6 for row in rows)  # id, prénom, nom, jour, mois, cercle
    assert not any(1994 in row for row in rows)


async def test_someone_without_a_date_is_not_even_read(session):
    """Ne pas renseigner sa date équivaut à `HIDDEN` — autant ne pas la ramener du tout."""
    tenant, bethel = uuid4(), uuid4()
    me, silent = _account(first="Moi"), _account(first="Awa", day=None, month=None)
    session.add_all([me, silent, _in_group(me, bethel, tenant), _in_group(silent, bethel, tenant)])
    await session.flush()

    rows = await SqlBirthdayDirectory(session).candidates(
        viewer_account_id=me.id, tenant_id=tenant
    )

    assert {r[1] for r in rows} == {"Moi"}


async def test_another_church_is_never_read(session):
    tenant, other, bethel = uuid4(), uuid4(), uuid4()
    me, elsewhere = _account(first="Moi"), _account(first="Awa")
    session.add_all([
        me, elsewhere, _in_group(me, bethel, tenant), _in_group(elsewhere, bethel, other)
    ])
    await session.flush()

    rows = await SqlBirthdayDirectory(session).candidates(
        viewer_account_id=me.id, tenant_id=tenant
    )

    assert {r[1] for r in rows} == {"Moi"}


async def test_the_member_posts_his_date_and_his_circle(session):
    account = _account(day=None, month=None)
    session.add(account)
    await session.flush()

    await SqlBirthdayStore(session).set_birthday(
        account_id=account.id, day=29, month=2, year=None,
        scope=BirthdayScope.REFERENT_ONLY.value,
    )
    await session.refresh(account)

    assert (account.birth_day, account.birth_month) == (29, 2)
    assert account.birthday_scope == BirthdayScope.REFERENT_ONLY.value
