"""Use case `RevokeGroupInvitation` — désactive un lien d'invitation (M4, G-1b).

Autorité `ensure_can_manage` (le responsable qui gère le groupe). Idempotent : révoquer un
lien déjà révoqué ne fait rien de plus.
"""

from __future__ import annotations

from uuid import UUID

from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.groups.application.group_lookup import load_group_in_tenant
from app.contexts.groups.domain.errors import InvitationNotFoundError
from app.contexts.groups.domain.repositories import (
    GroupInvitationRepository,
    GroupRepository,
)


class RevokeGroupInvitation:
    def __init__(
        self,
        groups: GroupRepository,
        invitations: GroupInvitationRepository,
        access: GroupAccessPolicy,
        *,
        clock,
    ) -> None:
        self._groups = groups
        self._invitations = invitations
        self._access = access
        self._clock = clock

    async def execute(
        self, *, actor_account_id: UUID, tenant_id: UUID, invitation_id: UUID
    ) -> None:
        invitation = await self._invitations.get(invitation_id)
        if invitation is None or invitation.tenant_id != tenant_id:
            raise InvitationNotFoundError(
                "Invitation introuvable.", details={"invitation_id": str(invitation_id)}
            )
        group = await load_group_in_tenant(self._groups, invitation.group_id, tenant_id)
        await self._access.ensure_can_manage(actor_account_id=actor_account_id, group=group)

        invitation.revoke(now=self._clock())
        await self._invitations.save(invitation)
