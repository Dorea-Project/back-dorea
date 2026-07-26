"""Accès base de données — SQLAlchemy 2.0 async sur PostgreSQL partagé.

Ce backend FastAPI est le seul backend : il **possède** le schéma PostgreSQL et
le fait évoluer via **Alembic** (`migrations/`). `scripts/dev_bootstrap.py` reste
un `create_all` de dépannage local. Ce module ouvre des connexions en
lecture/écriture ; les modèles déclarés côté FastAPI **sont** la définition du
schéma, pas un miroir d'un stockage détenu ailleurs.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Base déclarative commune à tous les modèles du schéma.

    Les modèles ORM des contextes **définissent** le schéma détenu par ce
    backend. En production, l'évolution passera par des migrations Alembic
    versionnées ; `Base.metadata.create_all()` reste réservé au bootstrap de
    développement local (`scripts/dev_bootstrap.py`).
    """


_settings = get_settings()

engine: AsyncEngine = create_async_engine(
    str(_settings.database_url),
    echo=_settings.db_echo,
    pool_size=_settings.db_pool_size,
    max_overflow=_settings.db_max_overflow,
    pool_pre_ping=True,
)

async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession]:
    """Dépendance FastAPI : une session par requête, commit/rollback gérés ici."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
