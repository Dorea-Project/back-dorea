"""Use cases du **lien d'invitation église** (M-5) — rejoindre une église en self-service.

- `CreateChurchInvitation` — accueil / Admin / Owner génère un lien (autorité `ENROLL_MEMBER`
  **église-entière** : un rôle scopé n'invite pas au nom de toute l'église). Réutilisable.
- `RevokeChurchInvitation` — coupe un lien.
- `JoinChurchByCode` — **le code EST l'autorisation** : un compte authentifié (mobile) entre dans
  l'église en `invited` (réutilise le compte global, M-2). Tolérant : déjà membre → aucune création.
"""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID, uuid4

from app.contexts.iam.application.access_control import AccessControl
from app.contexts.iam.application.dtos import ChurchInvitationDTO, JoinChurchResult
from app.contexts.iam.application.ports import InvitationCodeGenerator, MemberEnrollmentStore
from app.contexts.iam.domain.aggregates import Membership
from app.contexts.iam.domain.church_invitation import ChurchInvitation
from app.contexts.iam.domain.enums import MembershipStatus
from app.contexts.iam.domain.errors import (
    ChurchInvitationInactiveError,
    ChurchInvitationNotFoundError,
)
from app.contexts.iam.domain.permissions import Permission
from app.contexts.iam.domain.repositories import (
    ChurchInvitationRepository,
    MembershipRepository,
)

CHURCH_INVITATION_TTL_DAYS = 30


def _to_dto(inv: ChurchInvitation) -> ChurchInvitationDTO:
    return ChurchInvitationDTO(
        id=inv.id,
        tenant_id=inv.tenant_id,
        code=inv.code,
        expires_at=inv.expires_at,
        revoked=inv.revoked_at is not None,
    )


class CreateChurchInvitation:
    def __init__(
        self,
        invitations: ChurchInvitationRepository,
        codes: InvitationCodeGenerator,
        access: AccessControl,
        *,
        clock,
    ) -> None:
        self._invitations = invitations
        self._codes = codes
        self._access = access
        self._clock = clock

    async def execute(
        self, *, actor_account_id: UUID, tenant_id: UUID
    ) -> ChurchInvitationDTO:
        await self._access.ensure(
            account_id=actor_account_id,
            tenant_id=tenant_id,
            permission=Permission.ENROLL_MEMBER,
        )
        now = self._clock()
        invitation = ChurchInvitation(
            id=uuid4(),
            tenant_id=tenant_id,
            code=self._codes.generate(),
            created_by_account_id=actor_account_id,
            created_at=now,
            expires_at=now + timedelta(days=CHURCH_INVITATION_TTL_DAYS),
        )
        await self._invitations.add(invitation)
        return _to_dto(invitation)


class RevokeChurchInvitation:
    def __init__(
        self,
        invitations: ChurchInvitationRepository,
        access: AccessControl,
        *,
        clock,
    ) -> None:
        self._invitations = invitations
        self._access = access
        self._clock = clock

    async def execute(
        self, *, actor_account_id: UUID, invitation_id: UUID
    ) -> ChurchInvitationDTO:
        invitation = await self._invitations.get(invitation_id)
        if invitation is None:
            raise ChurchInvitationNotFoundError(
                "Lien d'invitation introuvable.",
                details={"invitation_id": str(invitation_id)},
            )
        await self._access.ensure(
            account_id=actor_account_id,
            tenant_id=invitation.tenant_id,
            permission=Permission.ENROLL_MEMBER,
        )
        invitation.revoke(now=self._clock())
        await self._invitations.save(invitation)
        return _to_dto(invitation)


class JoinChurchByCode:
    def __init__(
        self,
        invitations: ChurchInvitationRepository,
        memberships: MembershipRepository,
        enrollment: MemberEnrollmentStore,
        *,
        clock,
    ) -> None:
        self._invitations = invitations
        self._memberships = memberships
        self._enrollment = enrollment
        self._clock = clock

    async def execute(self, *, actor_account_id: UUID, code: str) -> JoinChurchResult:
        now = self._clock()
        invitation = await self._invitations.get_by_code(code)
        if invitation is None:
            raise ChurchInvitationNotFoundError("Code d'invitation inconnu.")
        if not invitation.is_active(now):
            raise ChurchInvitationInactiveError(
                "Ce lien d'invitation a expiré ou a été révoqué."
            )

        tenant_id = invitation.tenant_id
        existing = await self._memberships.get_active(actor_account_id, tenant_id)
        if existing is not None:
            # Déjà membre : le lien ne double pas — on referme sans créer.
            return JoinChurchResult(
                account_id=actor_account_id,
                tenant_id=tenant_id,
                membership_id=existing.id,
                status=existing.status.value,
                already_member=True,
            )

        membership = Membership(
            id=uuid4(),
            account_id=actor_account_id,
            tenant_id=tenant_id,
            status=MembershipStatus.INVITED,
            last_transition_at=now,
            role_assignments=[],
        )
        await self._enrollment.add_membership(
            membership=membership, actor_account_id=actor_account_id
        )
        return JoinChurchResult(
            account_id=actor_account_id,
            tenant_id=tenant_id,
            membership_id=membership.id,
            status=MembershipStatus.INVITED.value,
            already_member=False,
        )
