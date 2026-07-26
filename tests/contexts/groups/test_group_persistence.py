"""G-0 — round-trip SQLAlchemy du GroupRepository (chemin matérialisé, types, récursivité)."""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.contexts.groups.domain.aggregates import Group
from app.contexts.groups.domain.enums import GroupStatus, GroupType
from app.contexts.groups.infrastructure.persistence.repositories import SqlGroupRepository
from app.core.database import Base

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture
async def session() -> AsyncGenerator:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def test_root_and_child_round_trip(session):
    repo = SqlGroupRepository(session)
    tenant, actor = uuid4(), uuid4()

    root = Group.create_root(
        id=uuid4(),
        tenant_id=tenant,
        name="Jeunesse",
        type=GroupType.MINISTERE,
        now=_NOW,
        created_by_account_id=actor,
    )
    await repo.add(root)
    child = Group.create_child(
        id=uuid4(),
        parent=root,
        name="Famille A",
        type=GroupType.CELLULE,
        now=_NOW,
        created_by_account_id=actor,
    )
    await repo.add(child)
    await session.commit()

    loaded = await repo.get(child.id)
    assert loaded is not None
    assert loaded.name == "Famille A"
    assert loaded.type is GroupType.CELLULE
    assert loaded.status is GroupStatus.ACTIVE
    assert loaded.parent_group_id == root.id
    assert loaded.tenant_id == tenant  # hérité du parent
    assert loaded.path == f"/{root.id}/{child.id}/"
    # La portée sous-arbre est calculable depuis le chemin rechargé.
    assert loaded.is_covered_by(root.id)
    assert loaded.is_covered_by(child.id)
    assert not loaded.is_covered_by(uuid4())


async def test_get_unknown_returns_none(session):
    assert await SqlGroupRepository(session).get(uuid4()) is None
