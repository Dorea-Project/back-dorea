"""Use case `JoinGroupByCode` — rejoindre un groupe par lien d'invitation (M4, G-1b).

Le membre lui-même (mobile) présente un **code** ; le code *est* l'autorisation (pas besoin
de gérer le groupe). **Porte d'onboarding** : si le compte n'est pas encore membre de
l'église, le lien l'y **rattache** (`invited`) puis le rattache au groupe. Alimente la
croissance des cellules (→ multiplication, G-3).
"""

from __future__ import annotations

from uuid import UUID, uuid4

from app.contexts.groups.application.dtos import JoinResultDTO
from app.contexts.groups.application.group_lookup import load_group_in_tenant
from app.contexts.groups.application.ports import ChurchEnrollmentStore
from app.contexts.groups.domain.errors import (
    DuplicateGroupMembershipError,
    GroupClosedError,
    InvitationInactiveError,
    InvitationNotFoundError,
)
from app.contexts.groups.domain.membership import GroupMembership
from app.contexts.groups.domain.repositories import (
    GroupInvitationRepository,
    GroupMembershipRepository,
    GroupRepository,
)
from app.contexts.iam.domain.repositories import MembershipRepository


class JoinGroupByCode:
    def __init__(
        self,
        groups: GroupRepository,
        invitations: GroupInvitationRepository,
        group_memberships: GroupMembershipRepository,
        church_memberships: MembershipRepository,
        enrollment: ChurchEnrollmentStore,
        *,
        clock,
    ) -> None:
        self._groups = groups
        self._invitations = invitations
        self._group_memberships = group_memberships
        self._church_memberships = church_memberships
        self._enrollment = enrollment
        self._clock = clock

    async def execute(self, *, actor_account_id: UUID, code: str) -> JoinResultDTO:
        now = self._clock()
        invitation = await self._invitations.get_by_code(code)
        if invitation is None:
            raise InvitationNotFoundError("Code d'invitation inconnu.")
        if not invitation.is_active(now):
            raise InvitationInactiveError("Ce lien d'invitation a expiré ou a été révoqué.")

        group = await load_group_in_tenant(self._groups, invitation.group_id, invitation.tenant_id)
        if group.is_closed:
            raise GroupClosedError(
                "Ce groupe est clôturé.", details={"group_id": str(group.id)}
            )

        # Onboarding : rattache à l'église si le compte n'en est pas encore membre.
        enrolled = False
        if await self._church_memberships.get_active(actor_account_id, group.tenant_id) is None:
            await self._enrollment.enroll_invited(
                account_id=actor_account_id,
                tenant_id=group.tenant_id,
                actor_account_id=actor_account_id,
                now=now,
            )
            enrolled = True

        if await self._group_memberships.get_active(actor_account_id, group.id) is not None:
            raise DuplicateGroupMembershipError(
                "Vous êtes déjà membre de ce groupe.",
                details={"group_id": str(group.id)},
            )
        await self._group_memberships.add(
            GroupMembership.join(
                id=uuid4(),
                group_id=group.id,
                account_id=actor_account_id,
                tenant_id=group.tenant_id,
                now=now,
                joined_by_account_id=actor_account_id,  # self-join
            )
        )
        return JoinResultDTO(
            group_id=group.id,
            group_name=group.name,
            tenant_id=group.tenant_id,
            enrolled_in_church=enrolled,
        )
