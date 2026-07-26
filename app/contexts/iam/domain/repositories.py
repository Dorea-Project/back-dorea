"""Ports de persistance du contexte IAM (interfaces).

Implémentés en infrastructure (`iam/infrastructure/persistence/`). Côté mobile,
seules les opérations de **lecture** sont exposées.
"""

from abc import abstractmethod
from uuid import UUID

from app._shared.domain.repository import Repository
from app.contexts.iam.domain.aggregates import Account, Membership
from app.contexts.iam.domain.church_invitation import ChurchInvitation
from app.contexts.iam.domain.transfer import MemberTransfer


class AccountRepository(Repository):
    @abstractmethod
    async def get_by_id(self, account_id: UUID) -> Account | None: ...

    @abstractmethod
    async def get_by_phone(self, phone_number: str) -> Account | None: ...


class MembershipRepository(Repository):
    @abstractmethod
    async def get_active(self, account_id: UUID, tenant_id: UUID) -> Membership | None:
        """Appartenance non clôturée d'un compte dans un tenant (unicité M1 §3)."""
        ...

    @abstractmethod
    async def list_active_by_account(self, account_id: UUID) -> list[Membership]:
        """Toutes les appartenances non clôturées d'un compte, tous tenants confondus."""
        ...

    @abstractmethod
    async def count_active_group_leaders(self, tenant_id: UUID, group_id: UUID) -> int:
        """Nombre de `group_leader` actifs sur un groupe (cap 1 à 6, M1 §6)."""
        ...


class MemberTransferRepository(Repository):
    @abstractmethod
    async def add(self, transfer: MemberTransfer) -> None:
        """Persiste une nouvelle demande de transfert (pending)."""
        ...

    @abstractmethod
    async def get(self, transfer_id: UUID) -> MemberTransfer | None:
        """Charge un transfert par id, ou None."""
        ...

    @abstractmethod
    async def save(self, transfer: MemberTransfer) -> None:
        """Persiste un transfert existant (après accept/decline/cancel)."""
        ...

    @abstractmethod
    async def get_pending(
        self, account_id: UUID, from_tenant_id: UUID, to_tenant_id: UUID
    ) -> MemberTransfer | None:
        """Demande en attente pour ce membre sur ce trajet (garde anti-doublon)."""
        ...

    @abstractmethod
    async def list_involving_tenant(self, tenant_id: UUID) -> list[MemberTransfer]:
        """Tous les transferts où ce tenant est source **ou** destination (pour la liste)."""
        ...


class ChurchInvitationRepository(Repository):
    @abstractmethod
    async def add(self, invitation: ChurchInvitation) -> None: ...

    @abstractmethod
    async def get(self, invitation_id: UUID) -> ChurchInvitation | None: ...

    @abstractmethod
    async def get_by_code(self, code: str) -> ChurchInvitation | None:
        """Résout un code (le join n'a que le code), ou None."""
        ...

    @abstractmethod
    async def save(self, invitation: ChurchInvitation) -> None:
        """Persiste un état existant (ex. après révocation)."""
        ...

    @abstractmethod
    async def list_active_by_tenant(self, tenant_id: UUID) -> list[ChurchInvitation]:
        """Les liens (non révoqués) d'une église — vue backoffice."""
        ...
