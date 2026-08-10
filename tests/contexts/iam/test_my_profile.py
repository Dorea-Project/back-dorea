"""« Continuer en tant que Kouassi » — le profil de la personne, contre une vraie base.

Trois choses se vérifient ici, et une seule est du confort :

**Un compte sans église répond 200.** C'est le cas d'usage qui a motivé la route : Urim
s'installe seul, et le pasteur qui ne rejoint aucune église prépare quand même. Faire de
l'absence d'appartenance une erreur aurait fermé la porte à son premier utilisateur.

**L'année de naissance ne sort pas.** Elle existe en base, elle n'est pas dans le `SELECT`,
et le DTO n'a aucune place où elle pourrait tenir. Ce qui n'est pas lu ne peut pas fuir.

**Le profil ne vit pas dans Urim.** La règle de placement du domaine utilisateur est qu'une
donnée vraie de la personne vit dans le noyau ; le test le tient sur les *tables*, parce
qu'une seconde source de vérité sur quelqu'un divergerait au premier changement de nom.
"""

from dataclasses import fields
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.contexts.iam.application.ports import ProfileRow
from app.contexts.iam.application.queries.get_my_profile import GetMyProfile, MyProfileDTO
from app.contexts.iam.infrastructure.persistence.models import AccountModel
from app.contexts.iam.infrastructure.persistence.profile_reader import SqlProfileReader
from app.contexts.urim.infrastructure.persistence import corpus_models, models  # noqa: F401
from app.core.database import Base

_NOW = datetime(2026, 8, 10, tzinfo=UTC)


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as opened:
        yield opened
    await engine.dispose()


def _account(*, first="Kouassi", year=None, email=None):
    return AccountModel(
        id=uuid4(), phone_number=f"+225{uuid4().int % 10**8:08d}", first_name=first,
        last_name="N'Guessan", email=email, birth_day=12, birth_month=6, birth_year=year,
        birthday_scope="groups", is_phone_verified=True, is_email_verified=False,
        created_at=_NOW, created_by_type="self", status="active",
    )


class _AucuneAppartenance:
    async def execute(self, *, account_id):
        return []


async def test_a_full_profile_comes_back_in_one_call(session):
    compte = _account(email="kouassi@example.com")
    session.add(compte)
    await session.flush()

    dto = await GetMyProfile(SqlProfileReader(session), _AucuneAppartenance()).execute(
        account_id=compte.id
    )

    assert dto is not None
    assert (dto.first_name, dto.last_name) == ("Kouassi", "N'Guessan")
    assert dto.phone_number == compte.phone_number
    assert dto.email == "kouassi@example.com"
    assert (dto.birth_day, dto.birth_month, dto.birthday_scope) == (12, 6, "groups")


async def test_no_church_is_an_answer_not_an_error(session):
    """Le compte qui n'a rejoint aucune église existe, et il a un prénom."""
    compte = _account()
    session.add(compte)
    await session.flush()

    dto = await GetMyProfile(SqlProfileReader(session), _AucuneAppartenance()).execute(
        account_id=compte.id
    )

    assert dto is not None
    assert dto.memberships == ()


async def test_an_unknown_account_is_absent_not_empty(session):
    """Jeton valide, personne disparue : `None` — la route en fera un 404, pas un profil vide."""
    dto = await GetMyProfile(SqlProfileReader(session), _AucuneAppartenance()).execute(
        account_id=uuid4()
    )

    assert dto is None


async def test_the_birth_year_has_nowhere_to_land(session):
    """Elle est en base, donnée par la personne — et aucune des deux structures ne la porte."""
    compte = _account(year=1994)
    session.add(compte)
    await session.flush()

    ligne = await SqlProfileReader(session).read(compte.id)

    assert ligne is not None
    assert "birth_year" not in {f.name for f in fields(ProfileRow)}
    assert "birth_year" not in {f.name for f in fields(MyProfileDTO)}


def test_the_person_is_not_stored_in_a_urim_table():
    """Prénom, téléphone, naissance : dans `accounts`, et nulle part sous `urim_*`.

    Le jour où Urim recopierait le prénom pour l'afficher plus vite, les deux divergeraient
    au premier changement de nom — et personne ne saurait lequel croire."""
    identite = {"first_name", "last_name", "phone_number", "birth_day", "birth_month"}

    for nom, table in Base.metadata.tables.items():
        if nom.startswith("urim_"):
            assert not (identite & set(table.columns.keys())), nom
