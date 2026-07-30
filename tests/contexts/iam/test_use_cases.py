"""Tests des use cases IAM avec un faux dépôt en mémoire (sans base ni framework)."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.contexts.iam.application.ports import OwnershipChecker
from app.contexts.iam.application.queries.check_permission import CheckPermission
from app.contexts.iam.application.queries.get_membership_status import GetMembershipStatus
from app.contexts.iam.application.queries.get_my_memberships import GetMyMemberships
from app.contexts.iam.application.queries.is_confirmed_member import IsConfirmedMember
from app.contexts.iam.domain.aggregates import Membership
from app.contexts.iam.domain.entities import RoleAssignment
from app.contexts.iam.domain.enums import MembershipStatus, RoleCode
from app.contexts.iam.domain.errors import MembershipNotFoundError, UnauthorizedScopeError
from app.contexts.iam.domain.permissions import Permission
from app.contexts.iam.domain.repositories import MembershipRepository
from app.contexts.iam.domain.services import ALL_PERMISSIONS

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


class FakeOwnership(OwnershipChecker):
    def __init__(self, owners=()) -> None:
        self._owners = set(owners)  # {(account_id, tenant_id)}

    async def is_active_owner(self, account_id, tenant_id):
        return (account_id, tenant_id) in self._owners


class FakeMembershipRepository(MembershipRepository):
    """Implémente le port en mémoire — le contrat, pas SQLAlchemy."""

    def __init__(self, memberships: list[Membership]) -> None:
        self._memberships = memberships

    async def get_active(self, account_id, tenant_id):
        return next(
            (
                m
                for m in self._memberships
                if m.account_id == account_id and m.tenant_id == tenant_id and not m.is_closed
            ),
            None,
        )

    async def list_active_by_account(self, account_id):
        return [
            m for m in self._memberships if m.account_id == account_id and not m.is_closed
        ]

    async def count_active_group_leaders(self, tenant_id, group_id):
        return sum(
            1
            for m in self._memberships
            if m.tenant_id == tenant_id
            for ra in m.active_roles()
            if ra.role is RoleCode.GROUP_LEADER and ra.group_id == group_id
        )


def _confirmed_member(account_id, tenant_id, *roles) -> Membership:
    return Membership(
        id=uuid4(),
        account_id=account_id,
        tenant_id=tenant_id,
        status=MembershipStatus.CONFIRMED_MEMBER,
        last_transition_at=_NOW,
        role_assignments=list(roles),
    )


def _role(role: RoleCode, *, group_id=None) -> RoleAssignment:
    return RoleAssignment(
        id=uuid4(),
        role=role,
        group_id=group_id,
        assigned_at=_NOW,
        assigned_by_account_id=uuid4(),
    )


async def test_get_membership_status_projects_roles_and_permissions():
    account, tenant = uuid4(), uuid4()
    repo = FakeMembershipRepository([_confirmed_member(account, tenant, _role(RoleCode.ADMIN))])

    dto = await GetMembershipStatus(repo, FakeOwnership()).execute(
        account_id=account, tenant_id=tenant
    )

    assert dto.is_confirmed_member is True
    assert [r.role for r in dto.active_roles] == ["admin"]
    # M-3 : permissions résolues (verbes de l'Admin), pas owner.
    assert dto.is_owner is False
    assert "manage_membership" in dto.permissions
    assert "enroll_member" in dto.permissions
    assert dto.permissions == sorted(dto.permissions)  # liste stable


async def test_get_membership_status_owner_gets_all_permissions():
    account, tenant = uuid4(), uuid4()
    # Owner sans rôle (reconnu par la propriété) — peut tout.
    repo = FakeMembershipRepository([_confirmed_member(account, tenant)])

    dto = await GetMembershipStatus(repo, FakeOwnership({(account, tenant)})).execute(
        account_id=account, tenant_id=tenant
    )

    assert dto.is_owner is True
    assert set(dto.permissions) == {p.value for p in ALL_PERMISSIONS}


async def test_get_membership_status_pastor_is_read_only_except_his_agenda():
    account, tenant = uuid4(), uuid4()
    repo = FakeMembershipRepository([_confirmed_member(account, tenant, _role(RoleCode.PASTOR))])

    dto = await GetMembershipStatus(repo, FakeOwnership()).execute(
        account_id=account, tenant_id=tenant
    )

    # Lecture seule sur les **personnes** (spec §5.6). Ses actes d'écriture sont sur ses propres
    # objets : son agenda, ses sermons, et désormais les collectes qu'il lance. Lancer une
    # collecte ne rompt pas la règle — il ne verra jamais qui a donné quoi, et c'est précisément
    # pourquoi `view_contributions` n'est pas là.
    assert set(dto.permissions) == {
        "view_member_directory",
        "view_pastoral_alerts",
        "manage_appointments",
        "publish_sermon",
        "launch_collection",
    }
    assert "view_contributions" not in dto.permissions


async def test_get_membership_status_raises_when_absent():
    repo = FakeMembershipRepository([])
    with pytest.raises(MembershipNotFoundError):
        await GetMembershipStatus(repo, FakeOwnership()).execute(
            account_id=uuid4(), tenant_id=uuid4()
        )


async def test_get_my_memberships_lists_all_active_tenants():
    account = uuid4()
    bethel, sion = uuid4(), uuid4()
    repo = FakeMembershipRepository(
        [
            _confirmed_member(account, bethel, _role(RoleCode.ADMIN)),
            _confirmed_member(account, sion, _role(RoleCode.PASTOR)),
            _confirmed_member(uuid4(), bethel),  # autre compte — exclu
        ]
    )

    # Owner de Bethel seulement — is_owner résolu par tenant.
    dtos = await GetMyMemberships(repo, FakeOwnership({(account, bethel)})).execute(
        account_id=account
    )

    assert {d.tenant_id for d in dtos} == {bethel, sion}
    assert all(d.account_id == account for d in dtos)
    by_tenant = {d.tenant_id: d for d in dtos}
    assert by_tenant[bethel].is_owner is True
    assert set(by_tenant[bethel].permissions) == {p.value for p in ALL_PERMISSIONS}
    assert by_tenant[sion].is_owner is False  # pasteur → lecture seule


async def test_get_my_memberships_empty_is_not_an_error():
    repo = FakeMembershipRepository([])
    assert await GetMyMemberships(repo, FakeOwnership()).execute(account_id=uuid4()) == []


async def test_is_confirmed_member():
    account, tenant = uuid4(), uuid4()
    repo = FakeMembershipRepository([_confirmed_member(account, tenant)])
    assert await IsConfirmedMember(repo).execute(account_id=account, tenant_id=tenant)
    assert not await IsConfirmedMember(repo).execute(account_id=uuid4(), tenant_id=tenant)


async def test_check_permission_ensure_raises_when_denied():
    account, tenant = uuid4(), uuid4()
    repo = FakeMembershipRepository([_confirmed_member(account, tenant, _role(RoleCode.PASTOR))])
    check = CheckPermission(repo)

    assert await check.execute(
        account_id=account, tenant_id=tenant, permission=Permission.VIEW_PASTORAL_ALERTS
    )
    with pytest.raises(UnauthorizedScopeError):
        await check.ensure(
            account_id=account, tenant_id=tenant, permission=Permission.MANAGE_MEMBERSHIP
        )
