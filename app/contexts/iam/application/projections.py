"""Projections domaine → DTO applicatifs (partagées entre requêtes IAM).

Isole la mise à plat d'un agrégat `Membership` en `MembershipStatusDTO` pour que
`GetMembershipStatus` (un tenant) et `GetMyMemberships` (tous tenants) produisent
exactement la même forme.
"""

from __future__ import annotations

from app.contexts.iam.application.dtos import MembershipStatusDTO, RoleDTO
from app.contexts.iam.domain.aggregates import Membership
from app.contexts.iam.domain.services import resolved_permissions


def to_membership_status_dto(
    membership: Membership, *, is_owner: bool = False
) -> MembershipStatusDTO:
    permissions = sorted(p.value for p in resolved_permissions(membership, is_owner=is_owner))
    return MembershipStatusDTO(
        membership_id=membership.id,
        account_id=membership.account_id,
        tenant_id=membership.tenant_id,
        status=membership.status.value,
        is_confirmed_member=membership.is_confirmed_member,
        active_absence_reason=(
            membership.active_absence_reason.value
            if membership.active_absence_reason is not None
            else None
        ),
        active_roles=[
            RoleDTO(role=ra.role.value, group_id=ra.group_id) for ra in membership.active_roles()
        ],
        is_owner=is_owner,
        permissions=permissions,
    )
