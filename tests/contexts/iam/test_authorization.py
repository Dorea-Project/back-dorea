"""Tests du service d'autorisation (RBAC borné par la propriété, spec §5.6)."""

from datetime import UTC, datetime
from uuid import uuid4

from app.contexts.iam.domain.aggregates import Membership
from app.contexts.iam.domain.entities import RoleAssignment
from app.contexts.iam.domain.enums import MembershipStatus, RoleCode
from app.contexts.iam.domain.permissions import Permission
from app.contexts.iam.domain.services import (
    ALL_PERMISSIONS,
    AuthorizationService,
    resolved_permissions,
)

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _role(role: RoleCode, *, group_id=None) -> RoleAssignment:
    return RoleAssignment(
        id=uuid4(),
        role=role,
        group_id=group_id,
        assigned_at=_NOW,
        assigned_by_account_id=uuid4(),
    )


def _membership(*roles: RoleAssignment, status=MembershipStatus.CONFIRMED_MEMBER) -> Membership:
    return Membership(
        id=uuid4(),
        account_id=uuid4(),
        tenant_id=uuid4(),
        status=status,
        last_transition_at=_NOW,
        role_assignments=list(roles),
    )


def test_admin_can_manage_but_not_record_attendance():
    # L'Owner n'est plus un rôle (propriété = 1ᵉʳ étage) ; on teste ici le RBAC des rôles.
    m = _membership(_role(RoleCode.ADMIN))
    assert AuthorizationService.can_perform(m, Permission.MANAGE_MEMBERSHIP)
    assert not AuthorizationService.can_perform(m, Permission.RECORD_ATTENDANCE)  # terrain = respo


def test_pastor_is_read_only():
    m = _membership(_role(RoleCode.PASTOR))
    assert AuthorizationService.can_perform(m, Permission.VIEW_PASTORAL_ALERTS)
    assert not AuthorizationService.can_perform(m, Permission.MANAGE_MEMBERSHIP)


def test_secretary_is_the_pastors_hands_not_a_governor():
    """Le pasteur est en lecture seule : elle est ses mains — sa voix, ses yeux, zéro pouvoir."""
    m = _membership(_role(RoleCode.SECRETARY))
    # Sa voix (annoncer au nom de l'église) et ses yeux (le carnet, l'agenda des visites).
    assert AuthorizationService.can_perform(m, Permission.PUBLISH_ANNOUNCEMENT)
    assert AuthorizationService.can_perform(m, Permission.VIEW_MEMBER_DIRECTORY)
    assert AuthorizationService.can_perform(m, Permission.VIEW_PASTORAL_ALERTS)
    # Un rôle se définit par ses limites : elle ne gouverne rien.
    for interdit in (
        Permission.MANAGE_STAFF,
        Permission.MANAGE_TEAM,
        Permission.CLOSE_MEMBERSHIP,
        Permission.TRANSFER_MEMBER,
        Permission.MANAGE_GROUP,
        Permission.MANAGE_MEMBERSHIP,
        Permission.RECORD_ATTENDANCE,
    ):
        assert not AuthorizationService.can_perform(m, interdit), interdit


def test_secretary_speaks_church_wide_not_scoped_to_a_group():
    # Rôle non scopé (group_id=None) → sa parole porte jusqu'à l'église entière.
    m = _membership(_role(RoleCode.SECRETARY))
    assert AuthorizationService.can_perform(m, Permission.PUBLISH_ANNOUNCEMENT, group_id=uuid4())


def test_group_leader_permission_is_scoped_to_its_group():
    group = uuid4()
    m = _membership(_role(RoleCode.GROUP_LEADER, group_id=group))
    # Le verbe est accordé, mais uniquement dans la portée du groupe attribué.
    assert AuthorizationService.can_perform(m, Permission.RECORD_ATTENDANCE, group_id=group)
    assert not AuthorizationService.can_perform(m, Permission.RECORD_ATTENDANCE, group_id=uuid4())


def test_closed_membership_grants_nothing():
    m = _membership(_role(RoleCode.ADMIN), status=MembershipStatus.CLOSED)
    assert not AuthorizationService.can_perform(m, Permission.VIEW_MEMBER_DIRECTORY)


def test_no_role_no_permission():
    assert not AuthorizationService.can_perform(_membership(), Permission.VIEW_MEMBER_DIRECTORY)


# --- M-3 : résolution des permissions pour `/me` ---


def test_resolved_permissions_owner_gets_everything():
    # L'Owner (1ᵉʳ étage) détient tout, même sans rôle ni appartenance.
    assert resolved_permissions(None, is_owner=True) == ALL_PERMISSIONS


def test_resolved_permissions_unions_active_roles():
    m = _membership(_role(RoleCode.WELCOME_TEAM), _role(RoleCode.INTEGRATION_TEAM))
    perms = resolved_permissions(m, is_owner=False)
    assert Permission.ENROLL_MEMBER in perms  # accueil
    assert Permission.MANAGE_MEMBERSHIP in perms  # intégration
    assert Permission.MANAGE_STAFF not in perms  # aucun des deux ne l'a


def test_resolved_permissions_group_leader_carries_its_verbs():
    m = _membership(_role(RoleCode.GROUP_LEADER, group_id=uuid4()))
    # La liste dit *quels* verbes (la portée reste exprimée par active_roles).
    assert Permission.RECORD_ATTENDANCE in resolved_permissions(m, is_owner=False)


def test_resolved_permissions_closed_or_absent_membership_is_empty():
    closed = _membership(_role(RoleCode.ADMIN), status=MembershipStatus.CLOSED)
    assert resolved_permissions(closed, is_owner=False) == frozenset()
    assert resolved_permissions(None, is_owner=False) == frozenset()
