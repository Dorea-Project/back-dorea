"""Transfert de membre entre églises (poignée de main) — saga + souveraineté + garde-fous."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.contexts.iam.application.access_control import AccessControl
from app.contexts.iam.application.commands.transfer_member import (
    AcceptTransfer,
    CancelTransfer,
    DeclineTransfer,
    RequestTransfer,
)
from app.contexts.iam.application.ports import (
    MemberEnrollmentStore,
    MemberRosterPort,
    MembershipLifecycleStore,
    MembershipTransitionStore,
    OwnershipChecker,
)
from app.contexts.iam.application.queries.list_transfers import ListTransfers
from app.contexts.iam.domain.aggregates import Membership
from app.contexts.iam.domain.entities import RoleAssignment
from app.contexts.iam.domain.enums import MembershipStatus, RoleCode
from app.contexts.iam.domain.errors import (
    DuplicatePendingTransferError,
    GroupLastLeaderRemovalBlockedError,
    LastOwnerRemovalBlockedError,
    MembershipNotFoundError,
    SameTenantTransferError,
    TransferAlreadyResolvedError,
    UnauthorizedScopeError,
)
from app.contexts.iam.domain.repositories import (
    MembershipRepository,
    MemberTransferRepository,
)
from app.contexts.iam.domain.transfer import MemberTransfer

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


class _FakeMemberships(MembershipRepository):
    def __init__(self, memberships):
        self._m = memberships

    async def get_active(self, account_id, tenant_id):
        return next(
            (
                m
                for m in self._m
                if m.account_id == account_id and m.tenant_id == tenant_id and not m.is_closed
            ),
            None,
        )

    async def list_active_by_account(self, account_id):
        return [m for m in self._m if m.account_id == account_id and not m.is_closed]

    async def count_active_group_leaders(self, tenant_id, group_id):
        return sum(
            1
            for m in self._m
            if m.tenant_id == tenant_id
            for ra in m.active_roles()
            if ra.role is RoleCode.GROUP_LEADER and ra.group_id == group_id
        )


class _FakeOwnership(OwnershipChecker):
    def __init__(self, owners=()):
        self._owners = set(owners)

    async def is_active_owner(self, account_id, tenant_id):
        return (account_id, tenant_id) in self._owners


class _FakeTransfers(MemberTransferRepository):
    def __init__(self, items=()):
        self._t = list(items)

    async def add(self, transfer):
        self._t.append(transfer)

    async def get(self, transfer_id):
        return next((t for t in self._t if t.id == transfer_id), None)

    async def save(self, transfer):
        pass  # l'agrégat en mémoire est déjà muté

    async def get_pending(self, account_id, from_tenant_id, to_tenant_id):
        return next(
            (
                t
                for t in self._t
                if t.account_id == account_id
                and t.from_tenant_id == from_tenant_id
                and t.to_tenant_id == to_tenant_id
                and t.is_pending
            ),
            None,
        )

    async def list_involving_tenant(self, tenant_id):
        return [
            t for t in self._t if t.from_tenant_id == tenant_id or t.to_tenant_id == tenant_id
        ]


class _FakeLifecycle(MembershipLifecycleStore):
    def __init__(self):
        self.closed = []

    async def revoke_role(self, *, role_assignment_id, revoked_at, reason):
        pass

    async def close_membership(self, *, membership_id, closed_at, closure_reason):
        self.closed.append({"membership_id": membership_id, "closure_reason": closure_reason})


class _FakeEnrollment(MemberEnrollmentStore):
    def __init__(self):
        self.enrolled = []
        self.added = []

    async def enroll(self, *, account, membership, creation_source, actor_account_id):
        self.enrolled.append(membership)

    async def add_membership(self, *, membership, actor_account_id):
        self.added.append(membership)


class _FakeTransitions(MembershipTransitionStore):
    def __init__(self):
        self.transitions = []

    async def apply_transition(
        self, *, membership_id, new_status, previous_status, transitioned_at
    ):
        self.transitions.append({"membership_id": membership_id, "new_status": new_status})


class _FakeRoster(MemberRosterPort):
    def __init__(self):
        self.released = []
        self.placed = []

    async def release_from_tenant(self, *, account_id, tenant_id, now):
        self.released.append((account_id, tenant_id))

    async def place_in_group(self, *, account_id, tenant_id, group_id, now, by_account_id):
        self.placed.append((account_id, group_id))


def _m(account, tenant, roles=(), status=MembershipStatus.CONFIRMED_MEMBER) -> Membership:
    ras = [
        RoleAssignment(
            id=uuid4(), role=r, group_id=g, assigned_at=_NOW, assigned_by_account_id=uuid4()
        )
        for (r, g) in roles
    ]
    return Membership(
        id=uuid4(), account_id=account, tenant_id=tenant, status=status,
        last_transition_at=_NOW, role_assignments=ras,
    )


def _pending(account, soba, peniel, *, to_group_id=None, by=None) -> MemberTransfer:
    return MemberTransfer(
        id=uuid4(), account_id=account, from_tenant_id=soba, to_tenant_id=peniel,
        to_group_id=to_group_id, requested_by_account_id=by or uuid4(), requested_at=_NOW,
    )


def _access(ms, *, owners=()):
    return AccessControl(_FakeOwnership(owners), ms)


# --- RequestTransfer (la destination initie) ---


async def test_request_creates_pending_transfer():
    dest_admin, richmond, soba, peniel = (uuid4() for _ in range(4))
    ms = _FakeMemberships([
        _m(dest_admin, peniel, [(RoleCode.ADMIN, None)]),  # admin côté destination
        _m(richmond, soba, []),  # membre de la source
    ])
    transfers = _FakeTransfers()
    req = RequestTransfer(transfers, ms, _access(ms), clock=lambda: _NOW)

    dto = await req.execute(
        actor_account_id=dest_admin, account_id=richmond,
        from_tenant_id=soba, to_tenant_id=peniel,
    )
    assert dto.status == "pending"
    assert dto.from_tenant_id == soba and dto.to_tenant_id == peniel


async def test_request_requires_destination_authority():
    outsider, richmond, soba, peniel = (uuid4() for _ in range(4))
    ms = _FakeMemberships([_m(richmond, soba, [])])  # l'acteur n'a aucune autorité à Peniel
    req = RequestTransfer(_FakeTransfers(), ms, _access(ms), clock=lambda: _NOW)
    with pytest.raises(UnauthorizedScopeError):
        await req.execute(
            actor_account_id=outsider, account_id=richmond,
            from_tenant_id=soba, to_tenant_id=peniel,
        )


async def test_request_same_tenant_is_rejected():
    admin, richmond, church = uuid4(), uuid4(), uuid4()
    ms = _FakeMemberships([_m(admin, church, [(RoleCode.ADMIN, None)]), _m(richmond, church, [])])
    req = RequestTransfer(_FakeTransfers(), ms, _access(ms), clock=lambda: _NOW)
    with pytest.raises(SameTenantTransferError):
        await req.execute(
            actor_account_id=admin, account_id=richmond,
            from_tenant_id=church, to_tenant_id=church,
        )


async def test_request_without_source_membership_is_404():
    dest_admin, richmond, soba, peniel = (uuid4() for _ in range(4))
    ms = _FakeMemberships([_m(dest_admin, peniel, [(RoleCode.ADMIN, None)])])  # rien côté Soba
    req = RequestTransfer(_FakeTransfers(), ms, _access(ms), clock=lambda: _NOW)
    with pytest.raises(MembershipNotFoundError):
        await req.execute(
            actor_account_id=dest_admin, account_id=richmond,
            from_tenant_id=soba, to_tenant_id=peniel,
        )


async def test_request_duplicate_pending_is_rejected():
    dest_admin, richmond, soba, peniel = (uuid4() for _ in range(4))
    ms = _FakeMemberships([
        _m(dest_admin, peniel, [(RoleCode.ADMIN, None)]), _m(richmond, soba, []),
    ])
    transfers = _FakeTransfers([_pending(richmond, soba, peniel)])
    req = RequestTransfer(transfers, ms, _access(ms), clock=lambda: _NOW)
    with pytest.raises(DuplicatePendingTransferError):
        await req.execute(
            actor_account_id=dest_admin, account_id=richmond,
            from_tenant_id=soba, to_tenant_id=peniel,
        )


# --- AcceptTransfer (la source libère : la saga) ---


async def test_accept_runs_the_full_saga_new_destination_membership():
    src_admin, richmond, soba, peniel, cell = (uuid4() for _ in range(5))
    ms = _FakeMemberships([
        _m(src_admin, soba, [(RoleCode.ADMIN, None)]),  # admin côté source
        _m(richmond, soba, []),  # membre de Soba, pas encore de Peniel
    ])
    transfer = _pending(richmond, soba, peniel, to_group_id=cell)
    transfers = _FakeTransfers([transfer])
    lifecycle, enrollment, transitions, roster = (
        _FakeLifecycle(), _FakeEnrollment(), _FakeTransitions(), _FakeRoster()
    )
    accept = AcceptTransfer(
        transfers, ms, lifecycle, enrollment, transitions, roster, _access(ms), clock=lambda: _NOW
    )

    dto = await accept.execute(actor_account_id=src_admin, transfer_id=transfer.id)

    assert dto.status == "accepted"
    assert len(lifecycle.closed) == 1  # appartenance Soba clôturée (changed_church)
    assert lifecycle.closed[0]["closure_reason"].value == "changed_church"
    assert roster.released == [(richmond, soba)]  # a quitté les groupes de Soba
    assert len(enrollment.added) == 1  # nouvelle appartenance à Peniel
    assert enrollment.added[0].status is MembershipStatus.CONFIRMED_MEMBER  # atterrit confirmée
    assert roster.placed == [(richmond, cell)]  # placée dans la cellule d'accueil
    assert transitions.transitions == []  # pas de transition : c'était une création


async def test_accept_confirms_existing_shared_membership():
    src_admin, richmond, soba, peniel = (uuid4() for _ in range(4))
    dest = _m(richmond, peniel, [], status=MembershipStatus.NEWCOMER)  # déjà partagée à Peniel
    ms = _FakeMemberships([
        _m(src_admin, soba, [(RoleCode.ADMIN, None)]), _m(richmond, soba, []), dest,
    ])
    transfer = _pending(richmond, soba, peniel)
    transfers = _FakeTransfers([transfer])
    enrollment, transitions, roster = _FakeEnrollment(), _FakeTransitions(), _FakeRoster()
    accept = AcceptTransfer(
        transfers, ms, _FakeLifecycle(), enrollment, transitions, roster, _access(ms),
        clock=lambda: _NOW,
    )

    dto = await accept.execute(actor_account_id=src_admin, transfer_id=transfer.id)

    assert dto.status == "accepted"
    assert enrollment.added == []  # pas de nouvelle appartenance
    assert len(transitions.transitions) == 1  # on officialise l'existante
    assert transitions.transitions[0]["new_status"] is MembershipStatus.CONFIRMED_MEMBER
    assert transitions.transitions[0]["membership_id"] == dest.id


async def test_accept_requires_source_authority():
    # L'acteur n'a l'autorité qu'à Peniel (destination), pas à Soba (source qui libère).
    dest_admin, richmond, soba, peniel = (uuid4() for _ in range(4))
    ms = _FakeMemberships([
        _m(dest_admin, peniel, [(RoleCode.ADMIN, None)]), _m(richmond, soba, []),
    ])
    transfer = _pending(richmond, soba, peniel)
    accept = AcceptTransfer(
        _FakeTransfers([transfer]), ms, _FakeLifecycle(), _FakeEnrollment(),
        _FakeTransitions(), _FakeRoster(), _access(ms), clock=lambda: _NOW,
    )
    with pytest.raises(UnauthorizedScopeError):
        await accept.execute(actor_account_id=dest_admin, transfer_id=transfer.id)


async def test_accept_blocked_if_source_is_owner():
    src_admin, richmond, soba, peniel = (uuid4() for _ in range(4))
    ms = _FakeMemberships([
        _m(src_admin, soba, [(RoleCode.ADMIN, None)]), _m(richmond, soba, []),
    ])
    transfer = _pending(richmond, soba, peniel)
    accept = AcceptTransfer(
        _FakeTransfers([transfer]), ms, _FakeLifecycle(), _FakeEnrollment(),
        _FakeTransitions(), _FakeRoster(), _access(ms, owners={(richmond, soba)}),
        clock=lambda: _NOW,
    )
    with pytest.raises(LastOwnerRemovalBlockedError):
        await accept.execute(actor_account_id=src_admin, transfer_id=transfer.id)


async def test_accept_blocked_if_source_last_group_leader():
    src_admin, richmond, soba, peniel, cell = (uuid4() for _ in range(5))
    ms = _FakeMemberships([
        _m(src_admin, soba, [(RoleCode.ADMIN, None)]),
        _m(richmond, soba, [(RoleCode.GROUP_LEADER, cell)]),  # seule responsable de sa cellule
    ])
    transfer = _pending(richmond, soba, peniel)
    accept = AcceptTransfer(
        _FakeTransfers([transfer]), ms, _FakeLifecycle(), _FakeEnrollment(),
        _FakeTransitions(), _FakeRoster(), _access(ms), clock=lambda: _NOW,
    )
    with pytest.raises(GroupLastLeaderRemovalBlockedError):
        await accept.execute(actor_account_id=src_admin, transfer_id=transfer.id)


async def test_accept_twice_is_rejected():
    src_admin, richmond, soba, peniel = (uuid4() for _ in range(4))
    ms = _FakeMemberships([
        _m(src_admin, soba, [(RoleCode.ADMIN, None)]), _m(richmond, soba, []),
    ])
    transfer = _pending(richmond, soba, peniel)
    transfer.accept(by_account_id=src_admin, now=_NOW)  # déjà résolu
    accept = AcceptTransfer(
        _FakeTransfers([transfer]), ms, _FakeLifecycle(), _FakeEnrollment(),
        _FakeTransitions(), _FakeRoster(), _access(ms), clock=lambda: _NOW,
    )
    with pytest.raises(TransferAlreadyResolvedError):
        await accept.execute(actor_account_id=src_admin, transfer_id=transfer.id)


# --- Decline / Cancel / List ---


async def test_source_declines_transfer():
    src_admin, richmond, soba, peniel = (uuid4() for _ in range(4))
    ms = _FakeMemberships([_m(src_admin, soba, [(RoleCode.ADMIN, None)])])
    transfer = _pending(richmond, soba, peniel)
    decline = DeclineTransfer(_FakeTransfers([transfer]), _access(ms), clock=lambda: _NOW)
    dto = await decline.execute(actor_account_id=src_admin, transfer_id=transfer.id)
    assert dto.status == "declined"


async def test_destination_cancels_own_request():
    dest_admin, richmond, soba, peniel = (uuid4() for _ in range(4))
    ms = _FakeMemberships([_m(dest_admin, peniel, [(RoleCode.ADMIN, None)])])
    transfer = _pending(richmond, soba, peniel)
    cancel = CancelTransfer(_FakeTransfers([transfer]), _access(ms), clock=lambda: _NOW)
    dto = await cancel.execute(actor_account_id=dest_admin, transfer_id=transfer.id)
    assert dto.status == "cancelled"


async def test_list_splits_incoming_and_outgoing():
    admin, a, b, soba, peniel, other = (uuid4() for _ in range(6))
    ms = _FakeMemberships([_m(admin, soba, [(RoleCode.ADMIN, None)])])
    transfers = _FakeTransfers([
        _pending(a, soba, peniel),  # sortant depuis Soba (Soba = source)
        _pending(b, other, soba),  # entrant vers Soba (Soba = destination)
    ])
    listing = ListTransfers(transfers, _access(ms))
    dto = await listing.execute(actor_account_id=admin, tenant_id=soba)

    assert len(dto.incoming) == 1 and dto.incoming[0].to_tenant_id == peniel
    assert len(dto.outgoing) == 1 and dto.outgoing[0].from_tenant_id == other
