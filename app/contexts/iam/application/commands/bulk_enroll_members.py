"""Use case `BulkEnrollMembers` — import en masse de fidèles (M3 onboarding).

L'Owner/Admin importe sa liste de membres (formulaire/CSV) : chacun devient un
membre `invited` **sans credential** (cf. `EnrollInvitedMember`). **Best-effort** :
une ligne en échec (déjà membre de ce tenant, format invalide) n'annule pas les autres
— on renvoie un rapport par ligne. La déduplication se fait par **lecture préalable**
(`get_by_phone`), pour ne pas empoisonner la transaction avec une violation d'unicité.

**Réutilisation du compte global (M-2)** : si le téléphone existe déjà, on **ajoute une
appartenance** au compte existant (jamais de doublon) ; il n'échoue que s'il est déjà
membre de ce tenant.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID, uuid4

from app.contexts.iam.application.access_control import AccessControl
from app.contexts.iam.application.dtos import (
    BulkEnrollResult,
    EnrolledRow,
    FailedRow,
    InvitedMemberInput,
)
from app.contexts.iam.application.ports import MemberEnrollmentStore
from app.contexts.iam.domain.aggregates import Account, Membership
from app.contexts.iam.domain.enums import AccountCreationSource, AccountStatus, MembershipStatus
from app.contexts.iam.domain.errors import DuplicateActiveMembershipError, IamError
from app.contexts.iam.domain.permissions import Permission
from app.contexts.iam.domain.repositories import AccountRepository, MembershipRepository

MAX_BATCH = 500  # borne l'import pour éviter les abus / requêtes géantes


class BatchTooLargeError(IamError):
    code = "IAM_IMPORT_BATCH_TOO_LARGE"
    http_status = 422


class BulkEnrollMembers:
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
        rows: Sequence[InvitedMemberInput],
    ) -> BulkEnrollResult:
        if len(rows) > MAX_BATCH:
            raise BatchTooLargeError(
                f"Import limité à {MAX_BATCH} lignes.",
                details={"count": len(rows)},
            )

        # Autorisation vérifiée UNE fois (fail-fast), pas par ligne.
        await self._access.ensure(
            account_id=actor_account_id, tenant_id=tenant_id, permission=Permission.ENROLL_MEMBER
        )

        now = self._clock()
        enrolled: list[EnrolledRow] = []
        failed: list[FailedRow] = []
        seen: set[str] = set()  # doublons intra-lot

        for row in rows:
            phone = row.phone_number
            if phone in seen:
                failed.append(FailedRow(phone, "IAM_DUPLICATE_ROW_IN_BATCH"))
                continue

            try:
                account_id = await self._enroll_one(row, tenant_id, now, actor_account_id)
            except IamError as exc:
                failed.append(FailedRow(phone, exc.code))
                continue

            seen.add(phone)
            enrolled.append(EnrolledRow(phone, account_id))

        return BulkEnrollResult(enrolled=enrolled, failed=failed)

    async def _enroll_one(
        self, row: InvitedMemberInput, tenant_id: UUID, now, actor_account_id: UUID
    ) -> UUID:
        phone = row.phone_number
        existing = await self._accounts.get_by_phone(phone)

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
            return existing.id

        account = Account(
            id=uuid4(),
            phone_number=phone,
            status=AccountStatus.ACTIVE,
            first_name=row.first_name,
            last_name=row.last_name,
        )
        membership = self._new_membership(account.id, tenant_id, now)
        await self._store.enroll(
            account=account,
            membership=membership,
            creation_source=AccountCreationSource.WALK_IN_REGISTRATION,
            actor_account_id=actor_account_id,
        )
        return account.id

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
