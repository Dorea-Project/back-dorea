"""Use case **Intégrer** (M9-4) — le chercheur devient membre : la boucle missionnaire se ferme.

Le Seeker est le *frère digital du Visiteur* (M6-3) ; l'intégration **réutilise exactement** la
machinerie visiteur→membre (`ConvertVisitor`) : identité globale par téléphone (créée ou
réutilisée), appartenance en statut `invited` (le début du tunnel), inscription au roster de la
cellule pour un chercheur de groupe. Le missionnaire *déverse* dans le tunnel déjà bâti.

Différence avec le Visiteur : le Seeker n'est **pas supprimé** — il passe à `integrated` et garde le
lien vers le compte qu'il est devenu (le futur arbre d'attribution).
"""

from __future__ import annotations

from uuid import UUID, uuid4

from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.groups.application.group_lookup import load_group_in_tenant
from app.contexts.groups.domain.membership import GroupMembership
from app.contexts.groups.domain.repositories import (
    GroupMembershipRepository,
    GroupRepository,
)
from app.contexts.iam.application.ports import MemberEnrollmentStore
from app.contexts.iam.domain.aggregates import Account, Membership
from app.contexts.iam.domain.enums import (
    AccountCreationSource,
    AccountStatus,
    MembershipStatus,
)
from app.contexts.iam.domain.permissions import Permission
from app.contexts.iam.domain.repositories import AccountRepository, MembershipRepository
from app.contexts.mission.application.dtos import IntegrateSeekerResult
from app.contexts.mission.domain.errors import (
    SeekerNotFoundError,
    SeekerPhoneRequiredError,
)
from app.contexts.mission.domain.repositories import SeekerRepository


class IntegrateSeeker:
    def __init__(
        self,
        seekers: SeekerRepository,
        accounts: AccountRepository,
        church_memberships: MembershipRepository,
        enrollment_store: MemberEnrollmentStore,
        groups: GroupRepository,
        group_memberships: GroupMembershipRepository,
        access: GroupAccessPolicy,
        *,
        clock,
    ) -> None:
        self._seekers = seekers
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
        seeker_id: UUID,
        phone: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> IntegrateSeekerResult:
        seeker = await self._seekers.get(seeker_id)
        if seeker is None:
            raise SeekerNotFoundError(
                "Chercheur introuvable.", details={"seeker_id": str(seeker_id)}
            )
        tenant_id = seeker.tenant_id

        # Enrôler est un acte **gouverné** (comme ConvertVisitor) : chercheur de groupe → autorité
        # d'enrôlement sur la cellule (+ inscription au roster) ; chercheur personnel → autorité
        # d'enrôlement église-entière (pas de cellule cible).
        group = None
        if seeker.inviter_group_id is not None:
            group = await load_group_in_tenant(self._groups, seeker.inviter_group_id, tenant_id)
            await self._access.ensure_can(
                actor_account_id=actor_account_id,
                group=group,
                permission=Permission.ENROLL_MEMBER,
            )
        else:
            await self._access.ensure_church_wide(
                actor_account_id=actor_account_id,
                tenant_id=tenant_id,
                permission=Permission.ENROLL_MEMBER,
            )

        phone = phone or seeker.phone
        if not phone:
            raise SeekerPhoneRequiredError(
                "Un téléphone est requis pour intégrer ce chercheur.",
                details={"seeker_id": str(seeker_id)},
            )

        now = self._clock()
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
                first_name=first_name or seeker.name,
                last_name=last_name,
            )
            await self._enrollment_store.enroll(
                account=account,
                membership=self._invited(account.id, tenant_id, now),
                creation_source=AccountCreationSource.SELF_SERVICE,  # chercheur digital
                actor_account_id=actor_account_id,
            )
            account_id = account.id
            reused = False

        # Roster : seulement pour un chercheur de groupe (tolérant : jamais de doublon).
        if group is not None and await self._group_memberships.get_active(
            account_id, group.id
        ) is None:
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

        seeker.integrate(account_id=account_id, now=now)  # le Seeker reste, marqué intégré
        await self._seekers.save(seeker)
        return IntegrateSeekerResult(
            account_id=account_id,
            tenant_id=tenant_id,
            group_id=group.id if group is not None else None,
            membership_status=MembershipStatus.INVITED.value,
            reused_account=reused,
            seeker_status=seeker.status.value,
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
