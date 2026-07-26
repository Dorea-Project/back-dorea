"""Use case `EnrollInvitedMember` — enrôle un fidèle ordinaire en statut `invited` (étape ④).

Le responsable/accueil enregistre les membres. **Aucun rôle, aucun credential** (le
visiteur existe avant l'app ; il activera son PIN plus tard). Le membre démarre en
`invited` et progressera par `TransitionStatus`.

**Réutilisation du compte global (M-2)** : si le téléphone existe déjà, on **ajoute une
appartenance** au compte existant (jamais de doublon), sauf s'il est déjà membre de ce tenant.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from app.contexts.iam.application.access_control import AccessControl
from app.contexts.iam.application.dtos import EnrollInvitedMemberResult
from app.contexts.iam.application.ports import MemberEnrollmentStore
from app.contexts.iam.domain.aggregates import Account, Membership
from app.contexts.iam.domain.enums import AccountCreationSource, AccountStatus, MembershipStatus
from app.contexts.iam.domain.errors import DuplicateActiveMembershipError
from app.contexts.iam.domain.permissions import Permission
from app.contexts.iam.domain.repositories import AccountRepository, MembershipRepository


class EnrollInvitedMember:
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
        phone_number: str,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> EnrollInvitedMemberResult:
        await self._access.ensure(
            account_id=actor_account_id, tenant_id=tenant_id, permission=Permission.ENROLL_MEMBER
        )

        now = self._clock()
        existing = await self._accounts.get_by_phone(phone_number)

        if existing is not None:
            # Compte global déjà présent → on RÉUTILISE (M-2), on n'en recrée pas.
            if await self._memberships.get_active(existing.id, tenant_id) is not None:
                raise DuplicateActiveMembershipError(
                    "Ce compte est déjà membre de ce tenant.",
                    details={"account_id": str(existing.id), "tenant_id": str(tenant_id)},
                )
            membership = self._new_membership(existing.id, tenant_id, now)
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
            membership = self._new_membership(account.id, tenant_id, now)
            await self._store.enroll(
                account=account,
                membership=membership,
                creation_source=AccountCreationSource.WALK_IN_REGISTRATION,
                actor_account_id=actor_account_id,
            )
            account_id = account.id

        return EnrollInvitedMemberResult(
            account_id=account_id,
            membership_id=membership.id,
            status=MembershipStatus.INVITED.value,
        )

    @staticmethod
    def _new_membership(account_id: UUID, tenant_id: UUID, now) -> Membership:
        return Membership(
            id=uuid4(),
            account_id=account_id,
            tenant_id=tenant_id,
            status=MembershipStatus.INVITED,
            last_transition_at=now,
            role_assignments=[],
        )
