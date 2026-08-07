"""Ports de persistance du contexte Tenant (interfaces)."""

from abc import abstractmethod
from uuid import UUID

from app._shared.domain.repository import Repository
from app.contexts.tenant.domain.aggregates import Tenant
from app.contexts.tenant.domain.onboarding import OnboardingRequest
from app.contexts.tenant.domain.ownership import Ownership


class TenantRepository(Repository):
    @abstractmethod
    async def get_by_id(self, tenant_id: UUID) -> Tenant | None: ...

    @abstractmethod
    async def list_all(self, *, limit: int, offset: int) -> list[Tenant]:
        """Annuaire des églises (Dorea)."""
        ...

    @abstractmethod
    async def save(self, tenant: Tenant) -> None:
        """Persiste le profil et le statut (édition / suspension)."""
        ...

    @abstractmethod
    async def list_children(self, parent_id: UUID) -> list[Tenant]:
        """Les **annexes** d'un principal — églises-filles par `parent_id` (M0 §4.1).

        Filiation **plate** en V1 : une annexe n'a pas d'annexe, donc ce sont les
        enfants directs, et il n'y a pas de récursion à faire."""
        ...


class OnboardingRepository(Repository):
    @abstractmethod
    async def add(self, request: OnboardingRequest) -> None: ...

    @abstractmethod
    async def get_by_id(self, request_id: UUID) -> OnboardingRequest | None: ...

    @abstractmethod
    async def save(self, request: OnboardingRequest) -> None:
        """Persiste les changements d'état (status / decided_at / rejection_reason)."""
        ...


class OwnershipRepository(Repository):
    @abstractmethod
    async def is_active_owner(self, account_id: UUID, tenant_id: UUID) -> bool:
        """Ce compte est-il l'Owner **actif** de ce tenant ? (autorisation, 1ᵉʳ étage)."""
        ...

    @abstractmethod
    async def get_active_for_tenant(self, tenant_id: UUID) -> Ownership | None:
        """La propriété active d'un tenant (ou `None` si vacant — anomalie)."""
        ...

    @abstractmethod
    async def list_active_tenant_ids(self, account_id: UUID) -> list[UUID]:
        """Les tenants dont ce compte est l'Owner **actif** (« mes églises »)."""
        ...

    @abstractmethod
    async def add(self, ownership: Ownership) -> None: ...

    @abstractmethod
    async def end_active(self, tenant_id: UUID, ended_at) -> None:
        """Clôt la propriété active d'un tenant (succession/émancipation)."""
        ...
