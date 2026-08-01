"""Le schéma des tests **est** celui de la production — et la base le prouve, pas un commentaire.

Vingt-cinq index et six contraintes d'unicité n'existaient que dans les migrations. Les modèles
les ignoraient, et comme la base de test se construit depuis les modèles (`create_all`), elle ne
les avait **jamais eus**. Deux conséquences, et la seconde est celle qui coûte :

1. un `alembic revision --autogenerate` aurait émis `drop_constraint` pour les six — supprimant en
   silence l'unicité des participations, des réactions et des signalements ;
2. tout test affirmant « on ne peut réagir qu'une fois » ne vérifiait qu'une garde applicative.
   Deux requêtes concurrentes passaient les tests et corrompaient la production.

Ce fichier tient les deux bouts : le premier test compare les modèles à la base de développement
(il saute si elle n'est pas là), les suivants prouvent que chaque contrainte **mord** vraiment.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.contexts.announcements.infrastructure.persistence.models import (
    AnnouncementEngagementModel,
    AnnouncementReactionModel,
)
from app.contexts.events.infrastructure.persistence.models import (
    EventParticipantModel,
    EventReactionModel,
    EventReportModel,
    EventViewModel,
)
from app.core.database import Base

_NOW = datetime(2026, 8, 1, tzinfo=UTC)


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as opened:
        yield opened
    await engine.dispose()


def _twice(factory, **shared):
    """Deux lignes qui ne diffèrent que par leur identifiant — le double-clic, en somme."""
    return factory(id=uuid4(), **shared), factory(id=uuid4(), **shared)


DOUBLES = [
    pytest.param(
        lambda e, a: _twice(
            EventParticipantModel, event_id=e, tenant_id=uuid4(), account_id=a,
            confirmed_at=_NOW,
        ),
        id="une seule participation par personne",
    ),
    pytest.param(
        lambda e, a: _twice(
            EventReactionModel, event_id=e, account_id=a, kind="pray", reacted_at=_NOW
        ),
        id="une seule reaction par personne",
    ),
    pytest.param(
        lambda e, a: _twice(
            EventViewModel, event_id=e, viewer_account_id=a, viewed_at=_NOW
        ),
        id="le rayonnement compte des gens, pas des ouvertures d'ecran",
    ),
    pytest.param(
        lambda e, a: _twice(
            EventReportModel, event_id=e, reporter_account_id=a, created_at=_NOW
        ),
        id="un signalement par personne",
    ),
    pytest.param(
        lambda e, a: _twice(
            AnnouncementEngagementModel, announcement_id=e, account_id=a, responded_at=_NOW
        ),
        id="un engagement par personne",
    ),
    pytest.param(
        lambda e, a: _twice(
            AnnouncementReactionModel, announcement_id=e, account_id=a, emoji="🙏",
            reacted_at=_NOW,
        ),
        id="un emoji par personne",
    ),
]


@pytest.mark.parametrize("build", DOUBLES)
async def test_the_database_refuses_the_second_one(session, build):
    """La garde est **dans la base**, pas seulement dans le use case.

    C'est ce qui distingue « l'application vérifie avant d'écrire » de « deux requêtes simultanées
    ne peuvent pas gagner toutes les deux ». Un compteur qu'on gonfle en cliquant est exactement
    ce que ces contraintes empêchent."""
    first, second = build(uuid4(), uuid4())
    session.add(first)
    await session.flush()

    session.add(second)
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_the_models_and_the_migrations_describe_the_same_schema():
    """Le garde-fou qui aurait évité tout ceci — et qui tient désormais tout seul.

    Il compare la métadonnée des modèles à la base de développement. Sans base joignable, il
    saute plutôt que de mentir : `alembic check` fait la même chose en intégration."""
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    from app.core.config import get_settings

    engine = create_async_engine(str(get_settings().database_url))
    try:
        async with engine.connect() as connection:
            diffs = await connection.run_sync(
                lambda c: compare_metadata(MigrationContext.configure(c), Base.metadata)
            )
    except Exception as exc:  # base de dev absente : ce n'est pas un échec du code
        pytest.skip(f"base de développement injoignable : {type(exc).__name__}")
    finally:
        await engine.dispose()

    assert diffs == [], f"{len(diffs)} divergence(s) modèles ↔ base"
