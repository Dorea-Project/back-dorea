"""Services de domaine IAM — logique métier sans état ni dépendance d'infra."""

from __future__ import annotations

from uuid import UUID

from app.contexts.iam.domain.aggregates import Membership
from app.contexts.iam.domain.permissions import Permission, permissions_for

# Toutes les permissions définies — ce que détient un Owner (1ᵉʳ étage : « peut tout »).
ALL_PERMISSIONS: frozenset[Permission] = frozenset(Permission)


class AuthorizationService:
    """Décide si une appartenance autorise un verbe sur une ressource donnée.

    Implémente le RBAC borné par la propriété (spec §5.6) : un rôle accorde le
    **verbe**, et l'attribution doit en plus **couvrir la portée** de la
    ressource (le `group_id` pour les rôles de portée groupe).
    """

    @staticmethod
    def can_perform(
        membership: Membership,
        permission: Permission,
        *,
        group_id: UUID | None = None,
    ) -> bool:
        if membership.is_closed:
            return False
        return any(
            permission in permissions_for(assignment.role) and assignment.covers(group_id=group_id)
            for assignment in membership.active_roles()
        )


def resolved_permissions(
    membership: Membership | None, *, is_owner: bool
) -> frozenset[Permission]:
    """Verbes que l'acteur détient dans un tenant (mêmes règles qu'`AccessControl`).

    Owner → **toutes** les permissions (1ᵉʳ étage, sans portée). Sinon, l'union des
    permissions des rôles **actifs** de l'appartenance (une appartenance close, ou
    absente, ne confère rien). La **portée** de chaque verbe reste portée par les
    `active_roles` (ex. `group_id` d'un responsable) — cette liste dit *quels*
    verbes, pas *sur quel périmètre*.
    """
    if is_owner:
        return ALL_PERMISSIONS
    if membership is None or membership.is_closed:
        return frozenset()
    return frozenset(
        permission
        for assignment in membership.active_roles()
        for permission in permissions_for(assignment.role)
    )
