"""Sprint 1 — genèse Tenant + Owner, testée sans base (faux ProvisioningStore)."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.contexts.auth.application.ports import PasswordHasher
from app.contexts.iam.domain.enums import MembershipStatus
from app.contexts.tenant.application.commands.provision_tenant import ProvisionTenant
from app.contexts.tenant.application.dtos import ProvisionTenantRequest
from app.contexts.tenant.application.ports import ProvisioningStore
from app.contexts.tenant.domain.aggregates import Tenant
from app.contexts.tenant.domain.enums import OwnershipMode, TenantStatus
from app.contexts.tenant.domain.errors import InvalidParentTenantError
from app.contexts.tenant.domain.repositories import TenantRepository

_NOW = datetime(2026, 1, 1, tzinfo=UTC)
_PLATFORM = uuid4()  # compte système « Dorea Platform » (P0.1)


class _FakeTenants(TenantRepository):
    """Répertoire tenant en mémoire — pour valider `parent_id` (D6) sans base."""

    def __init__(self, existing: list[Tenant] | None = None) -> None:
        self._by_id = {t.id: t for t in (existing or [])}

    async def get_by_id(self, tenant_id):
        return self._by_id.get(tenant_id)

    async def list_all(self, *, limit, offset):
        return list(self._by_id.values())

    async def list_children(self, parent_id):
        return [t for t in self._by_id.values() if t.parent_id == parent_id]

    async def save(self, tenant):
        self._by_id[tenant.id] = tenant


def _principal(tenant_id) -> Tenant:
    return Tenant(id=tenant_id, name="Mère", created_at=_NOW, status=TenantStatus.ACTIVE)


class _FakeHasher(PasswordHasher):
    def hash(self, plain: str) -> str:
        return f"hash:{plain}"

    def verify(self, hashed: str, plain: str) -> bool:
        return hashed == f"hash:{plain}"


class FakeProvisioningStore(ProvisioningStore):
    """Capture l'appel atomique — le contrat, pas SQLAlchemy."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def provision(
        self,
        *,
        tenant,
        owner_account,
        owner_membership,
        ownership,
        owner_password_hash,
        hash_algo_version,
        actor_account_id,
    ):
        self.calls.append(
            {
                "tenant": tenant,
                "owner_account": owner_account,
                "owner_membership": owner_membership,
                "ownership": ownership,
                "owner_password_hash": owner_password_hash,
                "hash_algo_version": hash_algo_version,
                "actor_account_id": actor_account_id,
            }
        )


def _command(store: ProvisioningStore, tenants: TenantRepository | None = None) -> ProvisionTenant:
    return ProvisionTenant(
        store,
        tenants or _FakeTenants(),
        platform_account_id=_PLATFORM,
        clock=lambda: _NOW,
        hasher=_FakeHasher(),
        hash_algo_version=1,
    )


async def test_genesis_creates_tenant_and_bootstraps_owner():
    store = FakeProvisioningStore()
    result = await _command(store).execute(
        ProvisionTenantRequest(
            tenant_name="Église Bethel",
            owner_phone="+2250700000001",
            owner_email="owner@bethel.ci",
            owner_password="MotDePasse#2026",
            owner_first_name="Emmanuel",
            owner_last_name="K.",
        )
    )

    assert len(store.calls) == 1  # un seul appel = une seule transaction
    call = store.calls[0]
    assert call["owner_password_hash"] == "hash:MotDePasse#2026"  # mdp hashé
    assert call["owner_account"].email == "owner@bethel.ci"
    assert call["hash_algo_version"] == 1
    tenant, account, membership = (
        call["tenant"],
        call["owner_account"],
        call["owner_membership"],
    )

    # Tenant : église indépendante (cas V1)
    assert tenant.name == "Église Bethel"
    assert tenant.is_independent is True

    # Membership : bootstrap → confirmé d'emblée, SANS rôle (owner = propriété, pas rôle)
    assert membership.status is MembershipStatus.CONFIRMED_MEMBER
    assert membership.account_id == account.id
    assert membership.tenant_id == tenant.id
    assert membership.active_roles() == []

    # Propriété (Ownership) : lie le compte au tenant, mode bootstrap
    ownership = call["ownership"]
    assert ownership.account_id == account.id
    assert ownership.tenant_id == tenant.id
    assert ownership.mode is OwnershipMode.BOOTSTRAP
    assert ownership.is_active is True
    assert call["actor_account_id"] == _PLATFORM

    # Résultat renvoyé cohérent
    assert result.tenant_id == tenant.id
    assert result.owner_account_id == account.id
    assert result.owner_membership_id == membership.id


async def test_provisioned_owner_holds_the_ownership():
    store = FakeProvisioningStore()
    await _command(store).execute(
        ProvisionTenantRequest(
            tenant_name="Bethel",
            owner_phone="+2250700000002",
            owner_email="o2@bethel.ci",
            owner_password="MotDePasse#2026",
        )
    )
    call = store.calls[0]
    # La gouvernance est portée par l'Ownership, pas par un rôle sur la membership.
    assert call["ownership"].account_id == call["owner_account"].id
    assert call["owner_membership"].active_roles() == []


async def test_annexe_case_sets_parent_id():
    store = FakeProvisioningStore()
    mother_id = uuid4()
    tenants = _FakeTenants([_principal(mother_id)])  # la mère existe, active, principale
    await _command(store, tenants).execute(
        ProvisionTenantRequest(
            tenant_name="Bethel-Sud",
            owner_phone="+2250700000003",
            owner_email="o3@bethel.ci",
            owner_password="MotDePasse#2026",
            parent_id=mother_id,
        )
    )
    tenant = store.calls[0]["tenant"]
    assert tenant.parent_id == mother_id
    assert tenant.is_independent is False


async def test_annexe_with_unknown_parent_is_rejected():
    # D6 — une mère inexistante → annexe orpheline refusée AVANT toute écriture.
    store = FakeProvisioningStore()
    with pytest.raises(InvalidParentTenantError):
        await _command(store).execute(
            ProvisionTenantRequest(
                tenant_name="Orpheline",
                owner_phone="+2250700000004",
                owner_email="o4@bethel.ci",
                owner_password="MotDePasse#2026",
                parent_id=uuid4(),
            )
        )
    assert store.calls == []  # rien n'a été provisionné
