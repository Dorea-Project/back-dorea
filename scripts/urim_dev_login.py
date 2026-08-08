"""Amorce de développement — une église, un Owner, et un jeton prêt pour Swagger.

    python scripts/urim_dev_login.py

⚠️ **Développement uniquement.** Ce script crée un compte propriétaire et frappe un jeton
d'accès sans passer par l'OTP. Il n'a rien à faire ailleurs qu'en local : il court-circuite
exactement la porte que le module d'authentification existe pour tenir.

Idempotent — relancé, il réutilise l'église et le compte déjà créés et refrappe seulement
le jeton (qui, lui, expire).
"""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid4, uuid5

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.contexts.auth.infrastructure.jwt_service import JwtTokenService
from app.contexts.auth.infrastructure.persistence.models import (
    DeviceModel,
)
from app.contexts.iam.infrastructure.persistence.models import AccountModel
from app.contexts.tenant.infrastructure.persistence.models import (
    OwnershipModel,
    TenantModel,
)
from app.core.config import get_settings
from app.core.database import async_session_factory

NS = uuid5(NAMESPACE_URL, "https://dorea.app/dev")
EGLISE_ID = uuid5(NS, "tenant:urim-demo")
COMPTE_ID = uuid5(NS, "account:pasteur-venance")
APPAREIL = "dev-tablette-urim"
TELEPHONE = "+2250700000001"


async def main() -> None:
    maintenant = datetime.now(UTC)
    async with async_session_factory() as s:
        if await s.get(TenantModel, EGLISE_ID) is None:
            s.add(TenantModel(
                id=EGLISE_ID, name="Eglise de demonstration Urim", slug="urim-demo",
                status="active", timezone="Africa/Abidjan", language="fr",
                currency="XOF", country="CI", city="Abidjan",
                operates_annexes=False, created_at=maintenant,
            ))
            print("  eglise creee")

        if await s.get(AccountModel, COMPTE_ID) is None:
            s.add(AccountModel(
                id=COMPTE_ID, phone_number=TELEPHONE, email="venance@example.test",
                first_name="Venance", last_name="Pasteur",
                is_phone_verified=True, is_email_verified=True,
                birthday_scope="private", created_at=maintenant,
                created_by_type="platform", status="active",
            ))
            print("  compte cree")

        existe = await s.scalar(
            select(OwnershipModel.id)
            .where(OwnershipModel.tenant_id == EGLISE_ID)
            .where(OwnershipModel.ended_at.is_(None))
        )
        if existe is None:
            # La propriété est le plan d'autorisation **au-dessus** des rôles : un Owner
            # actif passe `ensure_church_wide` sans avoir besoin d'une attribution de rôle.
            s.add(OwnershipModel(
                id=uuid4(), account_id=COMPTE_ID, tenant_id=EGLISE_ID,
                status="active", mode="principal", started_at=maintenant,
            ))
            print("  propriete active creee")

        appareil = await s.scalar(
            select(DeviceModel)
            .where(DeviceModel.account_id == COMPTE_ID)
            .where(DeviceModel.device_id == APPAREIL)
        )
        if appareil is None:
            s.add(DeviceModel(
                id=uuid4(), account_id=COMPTE_ID, device_id=APPAREIL,
                trusted_at=maintenant, revoked_at=None,
            ))
            print("  appareil de confiance enregistre")
        elif appareil.revoked_at is not None:
            appareil.revoked_at = None
            print("  appareil reactive")

        await s.commit()

    reglages = get_settings()
    # ⚠️ **Douze heures, et non l'heure de production.** Un jeton d'essai qui expire au milieu
    # d'une séance de test fait perdre plus de temps que le risque qu'il crée : il ne vaut que
    # sur une base locale, pour un compte de démonstration, sur un serveur qu'on arrête le soir.
    paire = JwtTokenService(
        secret=reglages.jwt_secret,
        algorithm=reglages.jwt_algorithm,
        access_ttl_seconds=12 * 3600,
        refresh_ttl_seconds=reglages.jwt_refresh_ttl_seconds,
        session_ttl_seconds=reglages.jwt_session_ttl_seconds,
    ).issue_pair(COMPTE_ID, APPAREIL)
    print("\n" + "=" * 74)
    print(f"  tenant_id : {EGLISE_ID}")
    print(f"  compte    : {COMPTE_ID}  ({TELEPHONE})")
    print("=" * 74)
    print("\n  Jeton d'acces (Swagger > Authorize > Bearer) :\n")
    print(paire.access_token)


if __name__ == "__main__":
    asyncio.run(main())
