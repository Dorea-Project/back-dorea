"""Sprint 4 — cascade atomique de clôture, vérifiée en base (SQLite)."""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.contexts.auth.infrastructure.hashing import HASH_ALGO_VERSION, Argon2PasswordHasher
from app.contexts.iam.domain.enums import MembershipClosureReason
from app.contexts.iam.infrastructure.persistence.lifecycle import SqlMembershipLifecycleStore
from app.contexts.iam.infrastructure.persistence.models import MembershipModel, RoleAssignmentModel
from app.contexts.tenant.application.commands.provision_tenant import ProvisionTenant
from app.contexts.tenant.application.dtos import ProvisionTenantRequest
from app.contexts.tenant.infrastructure.persistence.store import SqlProvisioningStore
from app.contexts.tenant.infrastructure.persistence.tenant_repo import SqlTenantRepository
from app.core.config import get_settings
from app.core.database import Base

_NOW = datetime(2026, 1, 1, tzinfo=UTC)
_PLATFORM = get_settings().platform_account_id


@pytest.fixture
async def session() -> AsyncGenerator[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as s:
        yield s
    await engine.dispose()


async def test_close_membership_revokes_all_roles_atomically(session: AsyncSession):
    # Genèse : une appartenance confirmée (l'Owner n'a pas de rôle).
    prov = ProvisionTenant(
        SqlProvisioningStore(session),
        SqlTenantRepository(session),
        platform_account_id=_PLATFORM,
        clock=lambda: _NOW,
        hasher=Argon2PasswordHasher(),
        hash_algo_version=HASH_ALGO_VERSION,
    )
    result = await prov.execute(
        ProvisionTenantRequest(
            tenant_name="Bethel",
            owner_phone="+2250700000060",
            owner_email="o60@bethel.ci",
            owner_password="MotDePasse#2026",
        )
    )
    # On pose un rôle sur l'appartenance pour vérifier que la cascade le révoque.
    session.add(
        RoleAssignmentModel(
            id=uuid4(),
            membership_id=result.owner_membership_id,
            tenant_id=result.tenant_id,
            role="admin",
            group_id=None,
            assigned_at=_NOW,
            assigned_by_account_id=_PLATFORM,
        )
    )
    await session.commit()

    # Clôture (cascade) via le store de cycle de vie.
    await SqlMembershipLifecycleStore(session).close_membership(
        membership_id=result.owner_membership_id,
        closed_at=_NOW,
        closure_reason=MembershipClosureReason.CHANGED_CHURCH,
    )
    await session.commit()

    membership = await session.get(MembershipModel, result.owner_membership_id)
    assert membership.status == "closed"
    assert membership.closure_reason == "changed_church"
    assert membership.closed_at is not None

    roles = (
        await session.execute(
            select(RoleAssignmentModel).where(
                RoleAssignmentModel.membership_id == result.owner_membership_id
            )
        )
    ).scalars().all()
    assert len(roles) == 1
    assert roles[0].revoked_at is not None  # révoqué par la cascade
    assert roles[0].revoked_reason == "demotion_cascade"
