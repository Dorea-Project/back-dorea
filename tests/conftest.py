"""Fixtures de test.

La base réelle est un PostgreSQL détenu par ce backend ; pour les tests unitaires
on substitue la dépendance de session par un moteur SQLite in-memory (aiosqlite),
suffisant pour exercer les routes sans dépendre d'un Postgres migré.
"""

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import get_db_session
from app.main import create_app

_test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
_test_session_factory = async_sessionmaker(_test_engine, expire_on_commit=False)


async def _override_get_db_session() -> AsyncGenerator[AsyncSession]:
    async with _test_session_factory() as session:
        yield session


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient]:
    app = create_app()
    app.dependency_overrides[get_db_session] = _override_get_db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
