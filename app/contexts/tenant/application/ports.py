"""Ports de la couche application Tenant.

`ProvisioningStore` isole la persistance **atomique** de la genèse : Tenant +
Account (owner) + Membership (`confirmed_member`) + RoleAssignment (`owner`) sont
écrits dans **une seule transaction** ou aucun (résout le paradoxe œuf-poule
« un rôle exige confirmed_member », M0 §3.2). L'implémentation SQL (Sprint 2) porte
la transaction ; les tests substituent un faux.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from app.contexts.iam.domain.aggregates import Account, Membership
from app.contexts.tenant.domain.aggregates import Tenant
from app.contexts.tenant.domain.ownership import Ownership

Clock = Callable[[], datetime]


class ProvisioningStore(ABC):
    @abstractmethod
    async def provision(
        self,
        *,
        tenant: Tenant,
        owner_account: Account,
        owner_membership: Membership,
        ownership: Ownership,
        owner_password_hash: str,
        hash_algo_version: int,
        actor_account_id: UUID,
    ) -> None:
        """Écrit la genèse en une transaction unique.

        `actor_account_id` = compte système « Dorea Platform » (P0.1), tracé comme
        `created_by`/`assigned_by`. L'`owner_account` est persisté avec
        `created_by_type = owner` et son credential initial (`owner_password_hash`),
        pour qu'il puisse se connecter au backoffice (remise des identifiants).
        """
        ...
