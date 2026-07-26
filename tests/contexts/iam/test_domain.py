"""Tests unitaires du domaine IAM — pur, sans base ni framework."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.contexts.iam.domain.aggregates import Membership
from app.contexts.iam.domain.entities import RoleAssignment
from app.contexts.iam.domain.enums import MembershipStatus, RoleCode
from app.contexts.iam.domain.errors import InvalidPhoneNumberError, RoleRequiresGroupError
from app.contexts.iam.domain.value_objects import PhoneNumber

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _role(role: RoleCode, *, group_id=None, revoked=False) -> RoleAssignment:
    return RoleAssignment(
        id=uuid4(),
        role=role,
        group_id=group_id,
        assigned_at=_NOW,
        assigned_by_account_id=uuid4(),
        revoked_at=_NOW if revoked else None,
    )


def _membership(status: MembershipStatus, roles=None) -> Membership:
    return Membership(
        id=uuid4(),
        account_id=uuid4(),
        tenant_id=uuid4(),
        status=status,
        last_transition_at=_NOW,
        role_assignments=roles or [],
    )


class TestPhoneNumber:
    def test_normalizes_and_accepts_valid_e164(self):
        assert PhoneNumber(" +225 0700000000 ").value == "+2250700000000"

    def test_rejects_invalid(self):
        with pytest.raises(InvalidPhoneNumberError):
            PhoneNumber("0700000000")


class TestRoleAssignmentInvariant:
    def test_group_leader_requires_group_id(self):
        with pytest.raises(RoleRequiresGroupError):
            _role(RoleCode.GROUP_LEADER)  # pas de group_id → invariant violé

    def test_admin_needs_no_group(self):
        assert _role(RoleCode.ADMIN).role is RoleCode.ADMIN


class TestMembership:
    def test_is_confirmed_member(self):
        assert _membership(MembershipStatus.CONFIRMED_MEMBER).is_confirmed_member
        assert not _membership(MembershipStatus.VISITOR).is_confirmed_member

    def test_active_roles_excludes_revoked(self):
        m = _membership(
            MembershipStatus.CONFIRMED_MEMBER,
            roles=[_role(RoleCode.ADMIN), _role(RoleCode.PASTOR, revoked=True)],
        )
        assert [r.role for r in m.active_roles()] == [RoleCode.ADMIN]

    def test_has_role_is_scoped_by_group(self):
        group = uuid4()
        m = _membership(
            MembershipStatus.CONFIRMED_MEMBER,
            roles=[_role(RoleCode.GROUP_LEADER, group_id=group)],
        )
        assert m.has_role(RoleCode.GROUP_LEADER, group_id=group)
        assert not m.has_role(RoleCode.GROUP_LEADER, group_id=uuid4())  # autre groupe
