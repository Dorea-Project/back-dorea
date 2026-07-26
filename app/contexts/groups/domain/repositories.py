"""Ports de persistance du contexte Groupes."""

from abc import abstractmethod
from uuid import UUID

from app._shared.domain.repository import Repository
from app.contexts.groups.domain.aggregates import Group
from app.contexts.groups.domain.invitation import GroupInvitation
from app.contexts.groups.domain.membership import GroupMembership


class GroupRepository(Repository):
    @abstractmethod
    async def add(self, group: Group) -> None:
        """Persiste un nouveau groupe (racine ou sous-groupe)."""
        ...

    @abstractmethod
    async def get(self, group_id: UUID) -> Group | None:
        """Charge un groupe par id, ou None."""
        ...

    @abstractmethod
    async def list_children_by_lineage(self, mother_id: UUID) -> list[Group]:
        """Cellules-filles nées d'une cellule (via `multiplied_from_id`, G-3)."""
        ...

    @abstractmethod
    async def list_active_structural_children(self, parent_id: UUID) -> list[Group]:
        """Sous-groupes **non clôturés** directement rattachés à `parent_id` (G-5)."""
        ...

    @abstractmethod
    async def list_active_by_tenant(self, tenant_id: UUID) -> list[Group]:
        """Tous les groupes **non clôturés** d'une église (M7 — liste de soin église-entière)."""
        ...

    @abstractmethod
    async def save(self, group: Group) -> None:
        """Persiste un groupe existant (ex. après promotion → clôture, G-4)."""
        ...


class GroupMembershipRepository(Repository):
    @abstractmethod
    async def add(self, membership: GroupMembership) -> None:
        """Persiste une nouvelle appartenance à un groupe."""
        ...

    @abstractmethod
    async def save(self, membership: GroupMembership) -> None:
        """Persiste une appartenance existante (ex. après `leave`)."""
        ...

    @abstractmethod
    async def get_active(self, account_id: UUID, group_id: UUID) -> GroupMembership | None:
        """Appartenance active d'un compte dans un groupe, ou None."""
        ...

    @abstractmethod
    async def list_active_by_group(self, group_id: UUID) -> list[GroupMembership]:
        """Roster : appartenances actives d'un groupe."""
        ...


class GroupInvitationRepository(Repository):
    @abstractmethod
    async def add(self, invitation: GroupInvitation) -> None: ...

    @abstractmethod
    async def get(self, invitation_id: UUID) -> GroupInvitation | None: ...

    @abstractmethod
    async def get_by_code(self, code: str) -> GroupInvitation | None:
        """Résout un code (le join n'a que le code), ou None."""
        ...

    @abstractmethod
    async def save(self, invitation: GroupInvitation) -> None:
        """Persiste un état existant (ex. après révocation)."""
        ...
