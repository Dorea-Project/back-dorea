"""La politique par type de groupe — et l'unicité qui la protège vraiment.

`tenant_id` nullable veut dire « politique par défaut ». Mais en SQL `NULL != NULL` : une
contrainte d'unicité ordinaire sur `(tenant_id, group_type)` laisse insérer la même politique
globale autant de fois qu'on la rejoue. Deux rangs concurrents pour un même type rendraient le
résolveur **non déterministe selon l'ordre de lecture** — et le déterminisme du moteur est ce
qui rend le ledger rejouable.
"""

from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.contexts.watch.infrastructure.persistence.models import GroupTypePolicyModel
from app.contexts.watch.infrastructure.persistence.referent import (
    SqlGroupTypePolicyRepository,
)
from app.core.database import Base


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as opened:
        yield opened
    await engine.dispose()


def _policy(group_type, *, tenant_id=None, rank=1):
    return GroupTypePolicyModel(
        id=uuid4(),
        tenant_id=tenant_id,
        group_type=group_type,
        bears_veille=True,
        primacy_rank=rank,
    )


async def test_a_default_policy_cannot_be_seeded_twice(session):
    """Re-seed, aller-retour de migration, script d'init rejoué : la base refuse."""
    session.add(_policy("cellule"))
    await session.flush()

    session.add(_policy("cellule", rank=9))
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_two_churches_may_rank_the_same_type_differently(session):
    """L'index partiel ne ferme que le défaut : chaque église garde sa propre politique."""
    bethel, siloe = uuid4(), uuid4()
    session.add_all(
        [
            _policy("cellule", tenant_id=bethel, rank=1),
            _policy("cellule", tenant_id=siloe, rank=2),
        ]
    )
    await session.flush()  # aucune erreur : ce sont deux politiques distinctes

    assert (await SqlGroupTypePolicyRepository(session).all_for(bethel))[
        "cellule"
    ].primacy_rank == 1
    assert (await SqlGroupTypePolicyRepository(session).all_for(siloe))[
        "cellule"
    ].primacy_rank == 2


async def test_a_church_policy_overrides_the_default(session):
    """Le défaut sert de socle ; l'église le remplace type par type, sans toucher au code."""
    bethel = uuid4()
    session.add_all(
        [
            _policy("cellule", rank=1),
            _policy("ministere", rank=2),
            _policy("ministere", tenant_id=bethel, rank=0),  # Béthel range autrement
        ]
    )
    await session.flush()

    policies = await SqlGroupTypePolicyRepository(session).all_for(bethel)

    assert policies["cellule"].primacy_rank == 1  # hérité du défaut
    assert policies["ministere"].primacy_rank == 0  # celui de l'église gagne
