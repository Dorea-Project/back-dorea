"""Bootstrap de développement — À N'UTILISER QU'EN LOCAL.

⚠️ Ce script émet du DDL (`create_all`) et insère des données de test. Ce backend
possède le schéma (spec §14) ; en production son évolution passera par des
migrations Alembic versionnées. Ce script n'existe que comme dépannage local pour
tester l'API mobile sur Swagger sans dérouler ces migrations.

Il :
  1. crée les tables (accounts, memberships, role_assignments) ;
  2. insère un compte de test (téléphone + code secret hashé argon2id) ;
  3. lui attache une appartenance « membre confirmé » + un rôle admin dans un
     tenant de test.

Usage :  uv run python -m scripts.dev_bootstrap
"""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from app.contexts.auth.infrastructure.hashing import HASH_ALGO_VERSION, Argon2PasswordHasher
from app.contexts.iam.domain.enums import (
    AccountCreationSource,
    AccountStatus,
    MembershipStatus,
    RoleCode,
)
from app.contexts.iam.infrastructure.persistence.models import (
    AccountModel,
    MembershipModel,
    RoleAssignmentModel,
)
from app.core.config import PLATFORM_ACCOUNT_ID, get_settings
from app.core.database import Base, async_session_factory, engine

# --- Données de test (déterministes) ---
ACCOUNT_ID = UUID("11111111-1111-1111-1111-111111111111")
TENANT_ID = UUID("22222222-2222-2222-2222-222222222222")
MEMBERSHIP_ID = UUID("33333333-3333-3333-3333-333333333333")
ROLE_ID = UUID("44444444-4444-4444-4444-444444444444")
PHONE = "+2250700000001"
SECRET_CODE = "1234"


async def main() -> None:
    # La console Windows est en cp1252 par défaut → forcer UTF-8 pour l'affichage.
    sys.stdout.reconfigure(encoding="utf-8")

    settings = get_settings()
    if settings.environment != "local":
        env = settings.environment
        sys.exit(f"Refusé : dev_bootstrap réservé à l'env 'local' (actuel : {env})")

    # 1. Création des tables (dev only — en prod, migrations Alembic versionnées).
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    now = datetime.now(UTC)
    hashed = Argon2PasswordHasher().hash(SECRET_CODE)

    async with async_session_factory() as session:
        existing = await session.get(AccountModel, ACCOUNT_ID)
        if existing is not None:
            print("Compte de test déjà présent — rien à faire.")
        else:
            session.add(
                AccountModel(
                    id=ACCOUNT_ID,
                    phone_number=PHONE,
                    first_name="Test",
                    last_name="Fidèle",
                    password_hash=hashed,
                    hash_algo_version=HASH_ALGO_VERSION,
                    is_phone_verified=True,
                    is_email_verified=False,
                    created_at=now,
                    created_by_type=AccountCreationSource.SELF_SERVICE.value,
                    status=AccountStatus.ACTIVE.value,
                )
            )
            session.add(
                MembershipModel(
                    id=MEMBERSHIP_ID,
                    account_id=ACCOUNT_ID,
                    tenant_id=TENANT_ID,
                    status=MembershipStatus.CONFIRMED_MEMBER.value,
                    last_transition_at=now,
                    created_at=now,
                    created_by_account_id=ACCOUNT_ID,
                )
            )
            session.add(
                RoleAssignmentModel(
                    id=ROLE_ID,
                    membership_id=MEMBERSHIP_ID,
                    tenant_id=TENANT_ID,  # dénormalisé (P0.2)
                    role=RoleCode.ADMIN.value,
                    group_id=None,
                    assigned_at=now,
                    assigned_by_account_id=ACCOUNT_ID,
                )
            )
            await session.commit()
            print("Compte de test créé.")

        # Compte système « Dorea Platform » (P0.1) — non authentifiable, sans membership.
        if await session.get(AccountModel, PLATFORM_ACCOUNT_ID) is None:
            session.add(
                AccountModel(
                    id=PLATFORM_ACCOUNT_ID,
                    phone_number="+00000000000",  # sentinelle réservée
                    first_name="Dorea",
                    last_name="Platform",
                    password_hash=None,  # jamais de login
                    hash_algo_version=None,
                    is_phone_verified=False,
                    is_email_verified=False,
                    created_at=now,
                    created_by_type=AccountCreationSource.SYSTEM.value,
                    status=AccountStatus.ACTIVE.value,
                )
            )
            await session.commit()
            print("Compte système Plateforme créé.")

        # Vérif rapide
        count = len((await session.execute(select(AccountModel.id))).all())

    await engine.dispose()

    print("\n--- Seed dev prêt ---")
    print(f"  Téléphone    : {PHONE}")
    print(f"  Code secret  : {SECRET_CODE}")
    print(f"  Tenant test  : {TENANT_ID}")
    print(f"  Comptes en base : {count}")
    print("\nSur Swagger : POST /api/mobile/auth/login -> Authorize (access_token) ->")
    print(f"  GET /api/mobile/iam/me/tenants/{TENANT_ID}/membership")


if __name__ == "__main__":
    asyncio.run(main())
