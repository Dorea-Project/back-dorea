"""Entités internes de l'agrégat `Membership`."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app._shared.domain.entity import Entity
from app.contexts.iam.domain.enums import RevocationReason, RoleCode
from app.contexts.iam.domain.errors import RoleRequiresGroupError

# Rôles bornés à un groupe : leur portée est un `group_id` (M4 §5).
GROUP_SCOPED_ROLES: frozenset[RoleCode] = frozenset(
    {RoleCode.GROUP_LEADER, RoleCode.LEADER_IN_TRAINING}
)


class RoleAssignment(Entity):
    """Attribution d'un rôle dans une portée (M1 §4).

    Entité **interne** à l'agrégat `Membership` : jamais manipulée hors de sa
    racine. « Le rôle donne le verbe, la portée donne le périmètre » : une
    attribution de portée groupe porte obligatoirement l'`id` du groupe.
    """

    def __init__(
        self,
        *,
        id: UUID,
        role: RoleCode,
        group_id: UUID | None,
        assigned_at: datetime,
        assigned_by_account_id: UUID,
        revoked_at: datetime | None = None,
        revoked_reason: RevocationReason | None = None,
    ) -> None:
        if role in GROUP_SCOPED_ROLES and group_id is None:
            raise RoleRequiresGroupError(
                "Une attribution de portée groupe doit porter un group_id.",
                details={"role": role.value},
            )
        self.id = id
        self.role = role
        self.group_id = group_id
        self.assigned_at = assigned_at
        self.assigned_by_account_id = assigned_by_account_id
        self.revoked_at = revoked_at
        self.revoked_reason = revoked_reason

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None

    def covers(self, *, group_id: UUID | None) -> bool:
        """La portée de l'attribution couvre-t-elle la ressource visée ?

        Un rôle de portée groupe ne couvre que **son** groupe ; les autres rôles
        (portée église/annexe/tenant) ne sont pas contraints par un group_id.
        """
        if self.role in GROUP_SCOPED_ROLES:
            return group_id is not None and self.group_id == group_id
        return True
