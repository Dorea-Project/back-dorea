"""Use case `EnrollMember` — enrôle un membre porteur d'un rôle (chaîne d'autorité §5.3).

Politique d'autorité **par rôle** : pastor/admin → `MANAGE_STAFF` (Owner) ; responsable/
accueil/intégration → `MANAGE_TEAM` (Admin). Confère `confirmed_member` (bootstrap §5.4).

**Aucun credential posé** (M-0) : le staff activera son mot de passe backoffice, les rôles
terrain leur PIN mobile. **Réutilise le compte global** si le téléphone existe (M-2).
"""

from __future__ import annotations

from uuid import UUID, uuid4

from app.contexts.iam.application.access_control import AccessControl
from app.contexts.iam.application.dtos import EnrollMemberResult
from app.contexts.iam.application.ports import MemberEnrollmentStore
from app.contexts.iam.domain.aggregates import Account, Membership
from app.contexts.iam.domain.entities import RoleAssignment
from app.contexts.iam.domain.enums import (
    AccountCreationSource,
    AccountStatus,
    MembershipStatus,
    RoleCode,
)
from app.contexts.iam.domain.errors import (
    DuplicateActiveMembershipError,
    GroupLeaderCapExceededError,
    RoleNotEnrollableError,
    RoleRequiresGroupError,
)
from app.contexts.iam.domain.repositories import AccountRepository, MembershipRepository
from app.contexts.iam.domain.role_authority import ROLE_AUTHORITY

_GROUP_LEADER_CAP = 6  # 1 à 6 responsables par groupe (§6)


class EnrollMember:
    def __init__(
        self,
        accounts: AccountRepository,
        memberships: MembershipRepository,
        store: MemberEnrollmentStore,
        access: AccessControl,
        *,
        clock,
    ) -> None:
        self._accounts = accounts
        self._memberships = memberships
        self._store = store
        self._access = access
        self._clock = clock

    async def execute(
        self,
        *,
        actor_account_id: UUID,
        tenant_id: UUID,
        role: RoleCode,
        phone_number: str,
        group_id: UUID | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> EnrollMemberResult:
        required_permission = ROLE_AUTHORITY.get(role)
        if required_permission is None:
            raise RoleNotEnrollableError(
                "Rôle non enrôlable par cette opération.", details={"role": role.value}
            )
        await self._access.ensure(
            account_id=actor_account_id, tenant_id=tenant_id, permission=required_permission
        )

        if role is RoleCode.GROUP_LEADER:
            if group_id is None:
                raise RoleRequiresGroupError(
                    "Une attribution 'group_leader' doit porter un group_id.",
                    details={"role": role.value},
                )
            active = await self._memberships.count_active_group_leaders(tenant_id, group_id)
            if active >= _GROUP_LEADER_CAP:
                raise GroupLeaderCapExceededError(
                    f"Cap de {_GROUP_LEADER_CAP} responsables atteint sur ce groupe.",
                    details={"group_id": str(group_id)},
                )

        now = self._clock()
        assignment = RoleAssignment(
            id=uuid4(),
            role=role,
            group_id=group_id,
            assigned_at=now,
            assigned_by_account_id=actor_account_id,
        )
        existing = await self._accounts.get_by_phone(phone_number)

        if existing is not None:
            if await self._memberships.get_active(existing.id, tenant_id) is not None:
                raise DuplicateActiveMembershipError(
                    "Ce compte est déjà membre de ce tenant.",
                    details={"account_id": str(existing.id), "tenant_id": str(tenant_id)},
                )
            membership = self._new_membership(existing.id, tenant_id, now, assignment)
            await self._store.add_membership(
                membership=membership, actor_account_id=actor_account_id
            )
            account_id = existing.id
        else:
            account = Account(
                id=uuid4(),
                phone_number=phone_number,
                status=AccountStatus.ACTIVE,
                first_name=first_name,
                last_name=last_name,
            )
            membership = self._new_membership(account.id, tenant_id, now, assignment)
            await self._store.enroll(
                account=account,
                membership=membership,
                creation_source=AccountCreationSource.OWNER,
                actor_account_id=actor_account_id,
            )
            account_id = account.id

        return EnrollMemberResult(
            account_id=account_id,
            membership_id=membership.id,
            role=role.value,
            group_id=group_id,
        )

    @staticmethod
    def _new_membership(account_id, tenant_id, now, assignment: RoleAssignment) -> Membership:
        return Membership(
            id=uuid4(),
            account_id=account_id,
            tenant_id=tenant_id,
            status=MembershipStatus.CONFIRMED_MEMBER,  # bootstrap (§5.4)
            last_transition_at=now,
            role_assignments=[assignment],
        )
