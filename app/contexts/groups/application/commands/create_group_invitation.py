"""Use case `CreateGroupInvitation` — génère un lien/code d'invitation (M4, G-1b).

Faire entrer des gens = acte **DANS** le nœud → autorité `ensure_can_manage` (le responsable
lui-même). Le code est réutilisable, avec **expiration**. Le groupe doit être ouvert.
"""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID, uuid4

from app.contexts.groups.application.dtos import InvitationDTO
from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.groups.application.group_lookup import load_group_in_tenant
from app.contexts.groups.application.ports import InvitationCodeGenerator
from app.contexts.groups.domain.errors import GroupClosedError
from app.contexts.groups.domain.invitation import GroupInvitation
from app.contexts.groups.domain.repositories import (
    GroupInvitationRepository,
    GroupRepository,
)

INVITATION_TTL_DAYS = 30  # durée de vie par défaut d'un lien d'invitation


class CreateGroupInvitation:
    def __init__(
        self,
        groups: GroupRepository,
        invitations: GroupInvitationRepository,
        codes: InvitationCodeGenerator,
        access: GroupAccessPolicy,
        *,
        clock,
    ) -> None:
        self._groups = groups
        self._invitations = invitations
        self._codes = codes
        self._access = access
        self._clock = clock

    async def execute(
        self, *, actor_account_id: UUID, tenant_id: UUID, group_id: UUID
    ) -> InvitationDTO:
        group = await load_group_in_tenant(self._groups, group_id, tenant_id)
        if group.is_closed:
            raise GroupClosedError(
                "Ce groupe est clôturé.", details={"group_id": str(group_id)}
            )
        await self._access.ensure_can_manage(actor_account_id=actor_account_id, group=group)

        now = self._clock()
        invitation = GroupInvitation(
            id=uuid4(),
            group_id=group.id,
            tenant_id=group.tenant_id,
            code=self._codes.generate(),
            created_by_account_id=actor_account_id,
            created_at=now,
            expires_at=now + timedelta(days=INVITATION_TTL_DAYS),
        )
        await self._invitations.add(invitation)
        return InvitationDTO(
            id=invitation.id,
            group_id=group.id,
            code=invitation.code,
            expires_at=invitation.expires_at,
        )
