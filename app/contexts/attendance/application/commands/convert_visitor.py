"""Use case `ConvertVisitor` (M6-3, l'entonnoir bouclé) — un visage capturé devient membre.

Le geste qui referme l'entonnoir : le responsable qui a capturé un visiteur (autorité
`ENROLL_MEMBER`, déjà portée par le `group_leader`) le fait passer *visage* → **membre église
`invited`** (début du parcours, aucun rôle, aucun credential) **et** l'inscrit au **roster de la
cellule visitée** (le `group_id` de la rencontre) — il entre dès lors dans la pulsation.

Saga à cheval sur deux contextes (iam : compte + appartenance ; groups : roster). **Tolérant** :
si le téléphone est déjà un compte (M-2) on le réutilise ; s'il est déjà membre / déjà au roster,
on ne double pas — on referme quand même l'entonnoir. La fiche visiteur est ensuite **supprimée**.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from app.contexts.attendance.application.authz import load_gathering
from app.contexts.attendance.application.dtos import ConvertVisitorResult
from app.contexts.attendance.domain.errors import (
    VisitorNotFoundError,
    VisitorNotGroupScopedError,
    VisitorPhoneRequiredError,
)
from app.contexts.attendance.domain.repositories import GatheringRepository, VisitorRepository
from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.groups.application.group_lookup import load_group_in_tenant
from app.contexts.groups.domain.membership import GroupMembership
from app.contexts.groups.domain.repositories import GroupMembershipRepository, GroupRepository
from app.contexts.iam.application.ports import MemberEnrollmentStore
from app.contexts.iam.domain.aggregates import Account, Membership
from app.contexts.iam.domain.enums import (
    AccountCreationSource,
    AccountStatus,
    MembershipStatus,
)
from app.contexts.iam.domain.permissions import Permission
from app.contexts.iam.domain.repositories import AccountRepository, MembershipRepository


class ConvertVisitor:
    def __init__(
        self,
        visitors: VisitorRepository,
        gatherings: GatheringRepository,
        accounts: AccountRepository,
        church_memberships: MembershipRepository,
        enrollment_store: MemberEnrollmentStore,
        groups: GroupRepository,
        group_memberships: GroupMembershipRepository,
        access: GroupAccessPolicy,
        *,
        clock,
    ) -> None:
        self._visitors = visitors
        self._gatherings = gatherings
        self._accounts = accounts
        self._church_memberships = church_memberships
        self._enrollment_store = enrollment_store
        self._groups = groups
        self._group_memberships = group_memberships
        self._access = access
        self._clock = clock

    async def execute(
        self,
        *,
        actor_account_id: UUID,
        visitor_id: UUID,
        phone: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> ConvertVisitorResult:
        visitor = await self._visitors.get(visitor_id)
        if visitor is None:
            raise VisitorNotFoundError(
                "Visiteur introuvable.", details={"visitor_id": str(visitor_id)}
            )

        gathering = await load_gathering(self._gatherings, visitor.gathering_id)
        if gathering.group_id is None:
            raise VisitorNotGroupScopedError(
                "Cette rencontre n'est rattachée à aucune cellule.",
                details={"gathering_id": str(gathering.id)},
            )
        group = await load_group_in_tenant(
            self._groups, gathering.group_id, gathering.tenant_id
        )
        # Un seul verrou pour toute la saga : l'autorité d'enrôlement sur cette cellule.
        await self._access.ensure_can(
            actor_account_id=actor_account_id, group=group, permission=Permission.ENROLL_MEMBER
        )

        phone = phone or visitor.phone
        if not phone:
            raise VisitorPhoneRequiredError(
                "Un téléphone est requis pour convertir ce visiteur en membre.",
                details={"visitor_id": str(visitor_id)},
            )

        now = self._clock()
        tenant_id = gathering.tenant_id
        existing = await self._accounts.get_by_phone(phone)

        if existing is not None:
            account_id = existing.id
            reused = True
            if await self._church_memberships.get_active(account_id, tenant_id) is None:
                await self._enrollment_store.add_membership(
                    membership=self._invited(account_id, tenant_id, now),
                    actor_account_id=actor_account_id,
                )
        else:
            account = Account(
                id=uuid4(),
                phone_number=phone,
                status=AccountStatus.ACTIVE,
                first_name=first_name or visitor.name,
                last_name=last_name,
            )
            await self._enrollment_store.enroll(
                account=account,
                membership=self._invited(account.id, tenant_id, now),
                creation_source=AccountCreationSource.WALK_IN_REGISTRATION,
                actor_account_id=actor_account_id,
            )
            account_id = account.id
            reused = False

        # Roster de la cellule visitée (tolérant : jamais de doublon).
        if await self._group_memberships.get_active(account_id, group.id) is None:
            await self._group_memberships.add(
                GroupMembership.join(
                    id=uuid4(),
                    group_id=group.id,
                    account_id=account_id,
                    tenant_id=tenant_id,
                    now=now,
                    joined_by_account_id=actor_account_id,
                )
            )

        await self._visitors.remove(visitor_id)  # le visage est devenu membre → fiche retirée
        return ConvertVisitorResult(
            account_id=account_id,
            tenant_id=tenant_id,
            group_id=group.id,
            status=MembershipStatus.INVITED.value,
            reused_account=reused,
        )

    @staticmethod
    def _invited(account_id: UUID, tenant_id: UUID, now) -> Membership:
        return Membership(
            id=uuid4(),
            account_id=account_id,
            tenant_id=tenant_id,
            status=MembershipStatus.INVITED,
            last_transition_at=now,
            role_assignments=[],
        )
