"""M6-0 — socle Présence : ouvrir une rencontre, pointer (idempotent), roster dérivé, clôturer.

Autorisation par `RECORD_ATTENDANCE` (portée sous-arbre) : group_leader ET leader_in_training.
L'absence est déduite du roster (attendu moins présents).
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.contexts.attendance.application.commands.add_visitor import AddVisitor, RemoveVisitor
from app.contexts.attendance.application.commands.close_gathering import CloseGathering
from app.contexts.attendance.application.commands.convert_visitor import ConvertVisitor
from app.contexts.attendance.application.commands.create_gathering import CreateGathering
from app.contexts.attendance.application.commands.declare_absence import (
    CancelAbsence,
    DeclareAbsence,
)
from app.contexts.attendance.application.commands.mark_present import MarkPresent, UnmarkPresent
from app.contexts.attendance.application.commands.self_check_in import SelfCheckIn
from app.contexts.attendance.application.ports import SessionCodeGenerator
from app.contexts.attendance.application.queries.get_gathering_roster import GetGatheringRoster
from app.contexts.attendance.application.queries.get_my_absences import GetMyPlannedAbsences
from app.contexts.attendance.application.queries.list_gathering_visitors import (
    ListGatheringVisitors,
)
from app.contexts.attendance.domain.enums import AbsenceReason, GatheringType
from app.contexts.attendance.domain.errors import (
    GatheringClosedError,
    GatheringNotFoundError,
    InvalidAbsencePeriodError,
    NotAChurchMemberError,
    NotAGroupMemberError,
    PlannedAbsenceNotFoundError,
    VisitorNotFoundError,
    VisitorPhoneRequiredError,
)
from app.contexts.attendance.domain.gravity import gravity_of
from app.contexts.attendance.domain.planned_absence import PlannedAbsence
from app.contexts.attendance.domain.repositories import (
    AttendanceRecordRepository,
    GatheringRepository,
    GatheringRsvpRepository,
    PlannedAbsenceRepository,
    VisitorRepository,
)
from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.groups.domain.aggregates import Group
from app.contexts.groups.domain.enums import GroupType
from app.contexts.groups.domain.errors import UnauthorizedGroupActionError
from app.contexts.groups.domain.membership import GroupMembership
from app.contexts.groups.domain.repositories import GroupMembershipRepository, GroupRepository
from app.contexts.iam.application.ports import MemberEnrollmentStore, OwnershipChecker
from app.contexts.iam.domain.aggregates import Account, Membership
from app.contexts.iam.domain.entities import RoleAssignment
from app.contexts.iam.domain.enums import AccountStatus, MembershipStatus, RoleCode
from app.contexts.iam.domain.repositories import AccountRepository, MembershipRepository

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


class _FakeOwnership(OwnershipChecker):
    def __init__(self, owners=()):
        self._owners = set(owners)

    async def is_active_owner(self, account_id, tenant_id):
        return (account_id, tenant_id) in self._owners


class _FakeChurch(MembershipRepository):
    def __init__(self, memberships=()):
        self._m = list(memberships)

    async def get_active(self, account_id, tenant_id):
        return next(
            (m for m in self._m if m.account_id == account_id and m.tenant_id == tenant_id), None
        )

    async def list_active_by_account(self, account_id):
        return []

    async def count_active_group_leaders(self, tenant_id, group_id):
        return 0


class _FakeGroups(GroupRepository):
    def __init__(self, groups=()):
        self._by_id = {g.id: g for g in groups}

    async def add(self, group):
        self._by_id[group.id] = group

    async def get(self, group_id):
        return self._by_id.get(group_id)

    async def list_children_by_lineage(self, mother_id):
        return []

    async def list_active_structural_children(self, parent_id):
        return []

    async def list_active_by_tenant(self, tenant_id):
        return [
            g
            for g in self._by_id.values()
            if g.tenant_id == tenant_id and g.status.value != "closed"
        ]

    async def save(self, group):
        self._by_id[group.id] = group


class _FakeGroupMemberships(GroupMembershipRepository):
    def __init__(self, members=()):
        self._m = list(members)

    async def add(self, membership):
        self._m.append(membership)

    async def save(self, membership):
        pass

    async def get_active(self, account_id, group_id):
        return next(
            (
                m
                for m in self._m
                if m.account_id == account_id and m.group_id == group_id and m.is_active
            ),
            None,
        )

    async def list_active_by_group(self, group_id):
        return [m for m in self._m if m.group_id == group_id and m.is_active]


class _FakeGatherings(GatheringRepository):
    def __init__(self):
        self._by_id = {}

    async def add(self, gathering):
        self._by_id[gathering.id] = gathering

    async def get(self, gathering_id):
        return self._by_id.get(gathering_id)

    async def get_open_by_check_in_code(self, code):
        return next(
            (
                g
                for g in self._by_id.values()
                if g.check_in_code == code and g.status.value == "open"
            ),
            None,
        )

    async def list_by_group(self, group_id):
        return [g for g in self._by_id.values() if g.group_id == group_id]

    async def save(self, gathering):
        self._by_id[gathering.id] = gathering


class _FakeCodes(SessionCodeGenerator):
    def __init__(self, code="SESS01"):
        self._code = code

    def generate(self):
        return self._code


class _FakeAbsences(PlannedAbsenceRepository):
    def __init__(self, items=()):
        self._a = list(items)

    async def add(self, absence):
        self._a.append(absence)

    async def get(self, absence_id):
        return next((x for x in self._a if x.id == absence_id), None)

    async def save(self, absence):
        for i, x in enumerate(self._a):
            if x.id == absence.id:
                self._a[i] = absence
                return

    async def list_active_by_tenant(self, tenant_id):
        return [x for x in self._a if x.tenant_id == tenant_id and x.is_active]

    async def list_active_by_account(self, account_id, tenant_id):
        return [
            x
            for x in self._a
            if x.account_id == account_id and x.tenant_id == tenant_id and x.is_active
        ]

    async def get_by_source(self, account_id, source_ref):
        return next(
            (x for x in self._a if x.account_id == account_id and x.source_ref == source_ref),
            None,
        )

    async def list_open_neutralizations(self, account_id, tenant_id):
        return [
            x
            for x in self._a
            if x.account_id == account_id
            and x.tenant_id == tenant_id
            and x.is_neutralization
            and x.is_open
        ]

    async def list_open_neutralizations_by_tenant(self, tenant_id):
        return [
            x
            for x in self._a
            if x.tenant_id == tenant_id and x.is_neutralization and x.is_open
        ]

    async def delete_projected(self, tenant_id):
        self._a = [
            x
            for x in self._a
            if not (x.tenant_id == tenant_id and x.is_neutralization)
        ]


class _FakeRsvps(GatheringRsvpRepository):
    def __init__(self, account_ids=()):
        self._by_gathering: dict = {}
        self._seed = set(account_ids)

    async def set_for(self, rsvp):
        self._by_gathering.setdefault(rsvp.gathering_id, set()).add(rsvp.account_id)

    async def remove(self, gathering_id, account_id):
        self._by_gathering.get(gathering_id, set()).discard(account_id)

    async def list_account_ids_for(self, gathering_id):
        return set(self._by_gathering.get(gathering_id, set())) | self._seed


class _FakeVisitors(VisitorRepository):
    def __init__(self):
        self._v = []

    async def add(self, visitor):
        self._v.append(visitor)

    async def get(self, visitor_id):
        return next((x for x in self._v if x.id == visitor_id), None)

    async def remove(self, visitor_id):
        self._v = [x for x in self._v if x.id != visitor_id]

    async def list_for_gathering(self, gathering_id):
        return [x for x in self._v if x.gathering_id == gathering_id]


class _FakeRecords(AttendanceRecordRepository):
    def __init__(self):
        self._r = []

    async def add(self, record):
        self._r.append(record)

    async def get_for(self, gathering_id, account_id):
        return next(
            (r for r in self._r if r.gathering_id == gathering_id and r.account_id == account_id),
            None,
        )

    async def remove(self, gathering_id, account_id):
        self._r = [
            r
            for r in self._r
            if not (r.gathering_id == gathering_id and r.account_id == account_id)
        ]

    async def list_for_gathering(self, gathering_id):
        return [r for r in self._r if r.gathering_id == gathering_id]

    async def list_present_for_gatherings(self, gathering_ids):
        ids = set(gathering_ids)
        return [r for r in self._r if r.gathering_id in ids and r.mark.value == "present"]

    async def has_present_in_other_tenant_since(self, account_id, tenant_id, since):
        return False


def _church(account_id, tenant_id, *roles: RoleAssignment) -> Membership:
    return Membership(
        id=uuid4(),
        account_id=account_id,
        tenant_id=tenant_id,
        status=MembershipStatus.CONFIRMED_MEMBER,
        last_transition_at=_NOW,
        role_assignments=list(roles),
    )


def _role(role: RoleCode, *, group_id) -> RoleAssignment:
    return RoleAssignment(
        id=uuid4(), role=role, group_id=group_id, assigned_at=_NOW, assigned_by_account_id=uuid4()
    )


def _cell(tenant_id) -> Group:
    return Group.create_root(
        id=uuid4(), tenant_id=tenant_id, name="Cellule", type=GroupType.CELLULE, now=_NOW,
        created_by_account_id=uuid4(),
    )


def _member(group, account_id, tenant_id) -> GroupMembership:
    return GroupMembership.join(
        id=uuid4(), group_id=group.id, account_id=account_id, tenant_id=tenant_id, now=_NOW,
        joined_by_account_id=uuid4(),
    )


def _policy(church, *, owners=()) -> GroupAccessPolicy:
    return GroupAccessPolicy(_FakeOwnership(owners), church)


async def test_leader_opens_a_gathering():
    leader, tenant = uuid4(), uuid4()
    cell = _cell(tenant)
    church = _FakeChurch([_church(leader, tenant, _role(RoleCode.GROUP_LEADER, group_id=cell.id))])
    policy = _policy(church)
    cmd = CreateGathering(
        _FakeGatherings(), _FakeGroups([cell]), _FakeCodes(), policy, clock=lambda: _NOW
    )

    dto = await cmd.execute(
        actor_account_id=leader, tenant_id=tenant, group_id=cell.id,
        type=GatheringType.MEETING, scheduled_at=_NOW, title="Jeudi",
    )
    assert dto.status == "open"
    assert dto.type == "meeting"


async def test_trainee_can_open_a_gathering():
    """Le Timothée porte RECORD_ATTENDANCE — il peut animer la présence sans gouverner."""
    trainee, tenant = uuid4(), uuid4()
    cell = _cell(tenant)
    church = _FakeChurch(
        [_church(trainee, tenant, _role(RoleCode.LEADER_IN_TRAINING, group_id=cell.id))]
    )
    policy = _policy(church)
    cmd = CreateGathering(
        _FakeGatherings(), _FakeGroups([cell]), _FakeCodes(), policy, clock=lambda: _NOW
    )
    dto = await cmd.execute(
        actor_account_id=trainee, tenant_id=tenant, group_id=cell.id,
        type=GatheringType.MEETING, scheduled_at=_NOW,
    )
    assert dto.status == "open"


async def test_without_record_attendance_is_rejected():
    outsider, tenant = uuid4(), uuid4()
    cell = _cell(tenant)
    # welcome_team n'a PAS RECORD_ATTENDANCE.
    church = _FakeChurch([_church(outsider, tenant, _role(RoleCode.WELCOME_TEAM, group_id=None))])
    policy = _policy(church)
    cmd = CreateGathering(
        _FakeGatherings(), _FakeGroups([cell]), _FakeCodes(), policy, clock=lambda: _NOW
    )
    with pytest.raises(UnauthorizedGroupActionError):
        await cmd.execute(
            actor_account_id=outsider, tenant_id=tenant, group_id=cell.id,
            type=GatheringType.MEETING, scheduled_at=_NOW,
        )


async def _open_gathering(gatherings, groups, policy, owner, tenant, cell):
    dto = await CreateGathering(
        gatherings, groups, _FakeCodes(), policy, clock=lambda: _NOW
    ).execute(
        actor_account_id=owner, tenant_id=tenant, group_id=cell.id,
        type=GatheringType.MEETING, scheduled_at=_NOW,
    )
    return dto.id


async def test_mark_present_is_idempotent_and_shows_in_roster():
    owner, tenant, m1 = uuid4(), uuid4(), uuid4()
    cell = _cell(tenant)
    gms = _FakeGroupMemberships([_member(cell, m1, tenant)])
    groups = _FakeGroups([cell])
    gatherings, records = _FakeGatherings(), _FakeRecords()
    policy = _policy(_FakeChurch(), owners={(owner, tenant)})
    gid = await _open_gathering(gatherings, groups, policy, owner, tenant, cell)

    mark = MarkPresent(gatherings, records, groups, gms, policy, clock=lambda: _NOW)
    await mark.execute(actor_account_id=owner, gathering_id=gid, account_id=m1)
    await mark.execute(actor_account_id=owner, gathering_id=gid, account_id=m1)  # idempotent

    assert len(records._r) == 1
    roster = await GetGatheringRoster(
        gatherings, records, _FakeAbsences(), _FakeRsvps(), groups, gms, policy
    ).execute(
        actor_account_id=owner, gathering_id=gid
    )
    assert roster.present_count == 1
    assert roster.total_expected == 1
    assert roster.entries[0].present is True


async def test_roster_derives_absence():
    owner, tenant = uuid4(), uuid4()
    a, b, c = uuid4(), uuid4(), uuid4()
    cell = _cell(tenant)
    gms = _FakeGroupMemberships([_member(cell, x, tenant) for x in (a, b, c)])
    groups = _FakeGroups([cell])
    gatherings, records = _FakeGatherings(), _FakeRecords()
    policy = _policy(_FakeChurch(), owners={(owner, tenant)})
    gid = await _open_gathering(gatherings, groups, policy, owner, tenant, cell)

    mark = MarkPresent(gatherings, records, groups, gms, policy, clock=lambda: _NOW)
    await mark.execute(actor_account_id=owner, gathering_id=gid, account_id=a)
    await mark.execute(actor_account_id=owner, gathering_id=gid, account_id=b)

    roster = await GetGatheringRoster(
        gatherings, records, _FakeAbsences(), _FakeRsvps(), groups, gms, policy
    ).execute(
        actor_account_id=owner, gathering_id=gid
    )
    assert roster.total_expected == 3
    assert roster.present_count == 2  # c est absent (déduit, jamais stocké)
    absent = [e.account_id for e in roster.entries if not e.present]
    assert absent == [c]


async def test_cannot_mark_a_non_member():
    owner, tenant, stranger = uuid4(), uuid4(), uuid4()
    cell = _cell(tenant)
    groups = _FakeGroups([cell])
    gatherings, records = _FakeGatherings(), _FakeRecords()
    policy = _policy(_FakeChurch(), owners={(owner, tenant)})
    gid = await _open_gathering(gatherings, groups, policy, owner, tenant, cell)

    mark = MarkPresent(
        gatherings, records, groups, _FakeGroupMemberships(), policy, clock=lambda: _NOW
    )
    with pytest.raises(NotAGroupMemberError):
        await mark.execute(actor_account_id=owner, gathering_id=gid, account_id=stranger)


async def test_unmark_removes_presence():
    owner, tenant, m1 = uuid4(), uuid4(), uuid4()
    cell = _cell(tenant)
    gms = _FakeGroupMemberships([_member(cell, m1, tenant)])
    groups = _FakeGroups([cell])
    gatherings, records = _FakeGatherings(), _FakeRecords()
    policy = _policy(_FakeChurch(), owners={(owner, tenant)})
    gid = await _open_gathering(gatherings, groups, policy, owner, tenant, cell)

    await MarkPresent(gatherings, records, groups, gms, policy, clock=lambda: _NOW).execute(
        actor_account_id=owner, gathering_id=gid, account_id=m1
    )
    await UnmarkPresent(gatherings, records, groups, policy, clock=lambda: _NOW).execute(
        actor_account_id=owner, gathering_id=gid, account_id=m1
    )
    assert records._r == []


async def test_closed_gathering_blocks_marking():
    owner, tenant, m1 = uuid4(), uuid4(), uuid4()
    cell = _cell(tenant)
    gms = _FakeGroupMemberships([_member(cell, m1, tenant)])
    groups = _FakeGroups([cell])
    gatherings, records = _FakeGatherings(), _FakeRecords()
    policy = _policy(_FakeChurch(), owners={(owner, tenant)})
    gid = await _open_gathering(gatherings, groups, policy, owner, tenant, cell)

    await CloseGathering(gatherings, groups, policy, clock=lambda: _NOW).execute(
        actor_account_id=owner, gathering_id=gid
    )
    mark = MarkPresent(gatherings, records, groups, gms, policy, clock=lambda: _NOW)
    with pytest.raises(GatheringClosedError):
        await mark.execute(actor_account_id=owner, gathering_id=gid, account_id=m1)


# --- M6-1 : self-check-in (2ᵉ voix) ---


async def test_member_self_checks_in_with_code():
    owner, tenant, m1 = uuid4(), uuid4(), uuid4()
    cell = _cell(tenant)
    gms = _FakeGroupMemberships([_member(cell, m1, tenant)])
    groups = _FakeGroups([cell])
    gatherings, records = _FakeGatherings(), _FakeRecords()
    policy = _policy(_FakeChurch(), owners={(owner, tenant)})
    await _open_gathering(gatherings, groups, policy, owner, tenant, cell)  # code = SESS01

    checkin = SelfCheckIn(gatherings, records, gms, clock=lambda: _NOW)
    dto = await checkin.execute(actor_account_id=m1, code="SESS01")
    dto2 = await checkin.execute(actor_account_id=m1, code="SESS01")  # idempotent

    assert dto.group_id == cell.id
    assert len(records._r) == 1
    assert records._r[0].source.value == "self"  # la 2ᵉ voix
    assert dto2.gathering_id == dto.gathering_id


async def test_self_check_in_bad_code_is_not_found():
    checkin = SelfCheckIn(
        _FakeGatherings(), _FakeRecords(), _FakeGroupMemberships(), clock=lambda: _NOW
    )
    with pytest.raises(GatheringNotFoundError):
        await checkin.execute(actor_account_id=uuid4(), code="NOPE99")


async def test_self_check_in_on_closed_gathering_is_not_found():
    owner, tenant, m1 = uuid4(), uuid4(), uuid4()
    cell = _cell(tenant)
    gms = _FakeGroupMemberships([_member(cell, m1, tenant)])
    groups = _FakeGroups([cell])
    gatherings, records = _FakeGatherings(), _FakeRecords()
    policy = _policy(_FakeChurch(), owners={(owner, tenant)})
    gid = await _open_gathering(gatherings, groups, policy, owner, tenant, cell)
    await CloseGathering(gatherings, groups, policy, clock=lambda: _NOW).execute(
        actor_account_id=owner, gathering_id=gid
    )
    checkin = SelfCheckIn(gatherings, records, gms, clock=lambda: _NOW)
    with pytest.raises(GatheringNotFoundError):  # le code ne résout plus une rencontre ouverte
        await checkin.execute(actor_account_id=m1, code="SESS01")


async def test_self_check_in_by_non_member_is_rejected():
    owner, tenant, stranger = uuid4(), uuid4(), uuid4()
    cell = _cell(tenant)
    groups = _FakeGroups([cell])
    gatherings, records = _FakeGatherings(), _FakeRecords()
    policy = _policy(_FakeChurch(), owners={(owner, tenant)})
    await _open_gathering(gatherings, groups, policy, owner, tenant, cell)
    checkin = SelfCheckIn(gatherings, records, _FakeGroupMemberships(), clock=lambda: _NOW)
    with pytest.raises(NotAGroupMemberError):
        await checkin.execute(actor_account_id=stranger, code="SESS01")


# --- M6-2 : pré-déclaration d'absence (tags + période) ---

_FROM = datetime(2025, 12, 31, tzinfo=UTC)
_TO = datetime(2026, 1, 10, tzinfo=UTC)  # couvre _NOW (2026-01-01)


def _planned(
    account_id, tenant, reason=AbsenceReason.TRAVEL, *, frm=_FROM, to=_TO
) -> PlannedAbsence:
    return PlannedAbsence(
        id=uuid4(), account_id=account_id, tenant_id=tenant, reason=reason,
        from_date=frm, to_date=to, declared_by_account_id=account_id, declared_at=_NOW,
    )


async def test_declare_absence_with_tag_and_gravity():
    member, tenant = uuid4(), uuid4()
    church = _FakeChurch([_church(member, tenant)])
    absences = _FakeAbsences()
    cmd = DeclareAbsence(absences, church, clock=lambda: _NOW)

    dto = await cmd.execute(
        actor_account_id=member, tenant_id=tenant, reason=AbsenceReason.MOVED,
        from_date=_FROM, to_date=_TO,
    )
    assert dto.reason == "moved"
    assert dto.gravity == "structural"  # déménagement = poids fort (crochet effectif M7)
    assert len(absences._a) == 1


async def test_declare_absence_invalid_period():
    member, tenant = uuid4(), uuid4()
    cmd = DeclareAbsence(
        _FakeAbsences(), _FakeChurch([_church(member, tenant)]), clock=lambda: _NOW
    )
    with pytest.raises(InvalidAbsencePeriodError):
        await cmd.execute(
            actor_account_id=member, tenant_id=tenant, reason=AbsenceReason.TRAVEL,
            from_date=_TO, to_date=_FROM,  # fin avant début
        )


async def test_declare_absence_requires_church_membership():
    cmd = DeclareAbsence(_FakeAbsences(), _FakeChurch(), clock=lambda: _NOW)
    with pytest.raises(NotAChurchMemberError):
        await cmd.execute(
            actor_account_id=uuid4(), tenant_id=uuid4(), reason=AbsenceReason.SICK,
            from_date=_FROM, to_date=_TO,
        )


async def test_roster_shows_excused_from_planned_absence():
    owner, tenant = uuid4(), uuid4()
    present_m, excused_m, absent_m = uuid4(), uuid4(), uuid4()
    cell = _cell(tenant)
    gms = _FakeGroupMemberships(
        [_member(cell, x, tenant) for x in (present_m, excused_m, absent_m)]
    )
    groups = _FakeGroups([cell])
    gatherings, records = _FakeGatherings(), _FakeRecords()
    absences = _FakeAbsences([_planned(excused_m, tenant)])  # période couvrant _NOW
    policy = _policy(_FakeChurch(), owners={(owner, tenant)})
    gid = await _open_gathering(gatherings, groups, policy, owner, tenant, cell)
    await MarkPresent(gatherings, records, groups, gms, policy, clock=lambda: _NOW).execute(
        actor_account_id=owner, gathering_id=gid, account_id=present_m
    )

    roster = await GetGatheringRoster(
        gatherings, records, absences, _FakeRsvps(), groups, gms, policy
    ).execute(actor_account_id=owner, gathering_id=gid)

    assert roster.present_count == 1
    assert roster.excused_count == 1  # excused_m a prévenu
    by_id = {e.account_id: e for e in roster.entries}
    assert by_id[excused_m].excused is True and by_id[excused_m].present is False
    assert by_id[absent_m].present is False and by_id[absent_m].excused is False  # absence sèche


async def test_roster_shows_who_said_they_come():
    """Le « je viens » (M8) pré-remplit le roster — distinct de la présence réelle."""
    owner, tenant, awa = uuid4(), uuid4(), uuid4()
    cell = _cell(tenant)
    gms = _FakeGroupMemberships([_member(cell, awa, tenant)])
    groups = _FakeGroups([cell])
    gatherings, records = _FakeGatherings(), _FakeRecords()
    policy = _policy(_FakeChurch(), owners={(owner, tenant)})
    gid = await _open_gathering(gatherings, groups, policy, owner, tenant, cell)

    roster = await GetGatheringRoster(
        gatherings, records, _FakeAbsences(), _FakeRsvps({awa}), groups, gms, policy
    ).execute(actor_account_id=owner, gathering_id=gid)

    assert roster.rsvp_count == 1
    assert roster.entries[0].rsvp is True
    assert roster.entries[0].present is False  # un RSVP n'est pas une présence


async def test_cancel_own_absence():
    member, tenant = uuid4(), uuid4()
    absence = _planned(member, tenant)
    absences = _FakeAbsences([absence])
    await CancelAbsence(absences, clock=lambda: _NOW).execute(
        actor_account_id=member, absence_id=absence.id
    )
    assert (await absences.get(absence.id)).is_active is False


async def test_cancel_someone_elses_absence_is_not_found():
    member, other = uuid4(), uuid4()
    absence = _planned(member, uuid4())
    cmd = CancelAbsence(_FakeAbsences([absence]), clock=lambda: _NOW)
    with pytest.raises(PlannedAbsenceNotFoundError):
        await cmd.execute(actor_account_id=other, absence_id=absence.id)


async def test_my_absences_lists_active_only():
    member, tenant = uuid4(), uuid4()
    a1 = _planned(member, tenant, AbsenceReason.TRAVEL)
    a2 = _planned(member, tenant, AbsenceReason.SICK)
    a2.cancel(now=_NOW)  # annulée → exclue
    absences = _FakeAbsences([a1, a2])
    result = await GetMyPlannedAbsences(absences).execute(actor_account_id=member, tenant_id=tenant)
    assert {r.id for r in result} == {a1.id}


def test_gravity_mapping():
    assert gravity_of(AbsenceReason.MOVED).value == "structural"
    assert gravity_of(AbsenceReason.TRAVEL).value == "transient"
    assert gravity_of(AbsenceReason.OTHER).value == "watch"


# --- M6-3 : visiteurs (visages nouveaux) ---


async def test_add_visitor_and_list():
    owner, tenant = uuid4(), uuid4()
    cell = _cell(tenant)
    groups = _FakeGroups([cell])
    gatherings, visitors = _FakeGatherings(), _FakeVisitors()
    policy = _policy(_FakeChurch(), owners={(owner, tenant)})
    gid = await _open_gathering(gatherings, groups, policy, owner, tenant, cell)

    add = AddVisitor(gatherings, visitors, groups, policy, clock=lambda: _NOW)
    dto = await add.execute(
        actor_account_id=owner, gathering_id=gid, name="Koffi (ami)", phone="+2250700000099"
    )
    assert dto.name == "Koffi (ami)"

    listed = await ListGatheringVisitors(gatherings, visitors, groups, policy).execute(
        actor_account_id=owner, gathering_id=gid
    )
    assert [v.name for v in listed] == ["Koffi (ami)"]


async def test_add_visitor_on_closed_gathering_is_rejected():
    owner, tenant = uuid4(), uuid4()
    cell = _cell(tenant)
    groups = _FakeGroups([cell])
    gatherings, visitors = _FakeGatherings(), _FakeVisitors()
    policy = _policy(_FakeChurch(), owners={(owner, tenant)})
    gid = await _open_gathering(gatherings, groups, policy, owner, tenant, cell)
    await CloseGathering(gatherings, groups, policy, clock=lambda: _NOW).execute(
        actor_account_id=owner, gathering_id=gid
    )
    add = AddVisitor(gatherings, visitors, groups, policy, clock=lambda: _NOW)
    with pytest.raises(GatheringClosedError):
        await add.execute(actor_account_id=owner, gathering_id=gid, name="Trop tard")


async def test_add_visitor_requires_record_attendance():
    outsider, tenant = uuid4(), uuid4()
    cell = _cell(tenant)
    groups = _FakeGroups([cell])
    gatherings, visitors = _FakeGatherings(), _FakeVisitors()
    church = _FakeChurch([_church(outsider, tenant, _role(RoleCode.WELCOME_TEAM, group_id=None))])
    # L'accueil n'a pas RECORD_ATTENDANCE → il ne peut pas ouvrir de rencontre non plus ;
    # on ouvre en tant qu'owner, puis on tente l'ajout en tant qu'outsider.
    owner = uuid4()
    owner_policy = _policy(_FakeChurch(), owners={(owner, tenant)})
    gid = await _open_gathering(gatherings, groups, owner_policy, owner, tenant, cell)
    add = AddVisitor(gatherings, visitors, groups, _policy(church), clock=lambda: _NOW)
    with pytest.raises(UnauthorizedGroupActionError):
        await add.execute(actor_account_id=outsider, gathering_id=gid, name="X")


async def test_remove_visitor():
    owner, tenant = uuid4(), uuid4()
    cell = _cell(tenant)
    groups = _FakeGroups([cell])
    gatherings, visitors = _FakeGatherings(), _FakeVisitors()
    policy = _policy(_FakeChurch(), owners={(owner, tenant)})
    gid = await _open_gathering(gatherings, groups, policy, owner, tenant, cell)
    dto = await AddVisitor(gatherings, visitors, groups, policy, clock=lambda: _NOW).execute(
        actor_account_id=owner, gathering_id=gid, name="Erreur"
    )
    await RemoveVisitor(gatherings, visitors, groups, policy).execute(
        actor_account_id=owner, gathering_id=gid, visitor_id=dto.id
    )
    assert visitors._v == []


async def test_remove_unknown_visitor_is_not_found():
    owner, tenant = uuid4(), uuid4()
    cell = _cell(tenant)
    groups = _FakeGroups([cell])
    gatherings, visitors = _FakeGatherings(), _FakeVisitors()
    policy = _policy(_FakeChurch(), owners={(owner, tenant)})
    gid = await _open_gathering(gatherings, groups, policy, owner, tenant, cell)
    with pytest.raises(VisitorNotFoundError):
        await RemoveVisitor(gatherings, visitors, groups, policy).execute(
            actor_account_id=owner, gathering_id=gid, visitor_id=uuid4()
        )


# --- M6-3 : conversion visiteur -> membre (l'entonnoir bouclé) ---


class _FakeAccounts(AccountRepository):
    def __init__(self, accounts=()):
        self._a = list(accounts)

    async def get_by_id(self, account_id):
        return next((a for a in self._a if a.id == account_id), None)

    async def get_by_phone(self, phone_number):
        return next((a for a in self._a if a.phone_number == phone_number), None)


class _FakeEnrollStore(MemberEnrollmentStore):
    """Écrit dans le même _FakeChurch (les appartenances créées deviennent visibles)."""

    def __init__(self, church):
        self._church = church
        self.enrolled = []
        self.added = []

    async def enroll(self, *, account, membership, creation_source, actor_account_id):
        self._church._m.append(membership)
        self.enrolled.append((account, membership, creation_source))

    async def add_membership(self, *, membership, actor_account_id):
        self._church._m.append(membership)
        self.added.append(membership)


def _account(phone, *, first_name=None) -> Account:
    return Account(
        id=uuid4(), phone_number=phone, status=AccountStatus.ACTIVE, first_name=first_name
    )


async def _open_with_visitor(gatherings, visitors, groups, policy, owner, tenant, cell, *, phone):
    gid = await _open_gathering(gatherings, groups, policy, owner, tenant, cell)
    dto = await AddVisitor(gatherings, visitors, groups, policy, clock=lambda: _NOW).execute(
        actor_account_id=owner, gathering_id=gid, name="Koffi (ami de Awa)", phone=phone
    )
    return dto.id


async def test_convert_visitor_creates_invited_member_and_joins_cell():
    leader, tenant = uuid4(), uuid4()
    cell = _cell(tenant)
    groups, gms = _FakeGroups([cell]), _FakeGroupMemberships()
    gatherings, visitors = _FakeGatherings(), _FakeVisitors()
    church = _FakeChurch([_church(leader, tenant, _role(RoleCode.GROUP_LEADER, group_id=cell.id))])
    policy = _policy(church)
    vid = await _open_with_visitor(
        gatherings, visitors, groups, policy, leader, tenant, cell, phone="+2250700000099"
    )
    store = _FakeEnrollStore(church)
    convert = ConvertVisitor(
        visitors, gatherings, _FakeAccounts(), church, store, groups, gms, policy,
        clock=lambda: _NOW,
    )

    result = await convert.execute(actor_account_id=leader, visitor_id=vid)

    assert result.status == "invited"  # début du parcours, pas confirmé
    assert result.reused_account is False  # téléphone inconnu -> compte créé
    assert len(store.enrolled) == 1  # une appartenance église créée
    assert await gms.get_active(result.account_id, cell.id) is not None  # inscrit au roster
    assert visitors._v == []  # la fiche visiteur a disparu (converti)


async def test_convert_visitor_reuses_global_account():
    leader, tenant, known = uuid4(), uuid4(), uuid4()
    cell = _cell(tenant)
    groups, gms = _FakeGroups([cell]), _FakeGroupMemberships()
    gatherings, visitors = _FakeGatherings(), _FakeVisitors()
    church = _FakeChurch([_church(leader, tenant, _role(RoleCode.GROUP_LEADER, group_id=cell.id))])
    policy = _policy(church)
    vid = await _open_with_visitor(
        gatherings, visitors, groups, policy, leader, tenant, cell, phone="+2250700000099"
    )
    # Le téléphone est déjà un compte global (autre église), pas membre ici.
    accounts = _FakeAccounts([Account(id=known, phone_number="+2250700000099",
                                      status=AccountStatus.ACTIVE, first_name="Mme Richmond")])
    store = _FakeEnrollStore(church)
    convert = ConvertVisitor(
        visitors, gatherings, accounts, church, store, groups, gms, policy, clock=lambda: _NOW
    )

    result = await convert.execute(actor_account_id=leader, visitor_id=vid)

    assert result.account_id == known  # compte global réutilisé (M-2), pas de doublon
    assert result.reused_account is True
    assert len(store.added) == 1 and len(store.enrolled) == 0  # appartenance ajoutée au compte
    assert await gms.get_active(known, cell.id) is not None


async def test_convert_visitor_already_member_just_rosters():
    leader, tenant, known = uuid4(), uuid4(), uuid4()
    cell = _cell(tenant)
    groups, gms = _FakeGroups([cell]), _FakeGroupMemberships()
    gatherings, visitors = _FakeGatherings(), _FakeVisitors()
    church = _FakeChurch([
        _church(leader, tenant, _role(RoleCode.GROUP_LEADER, group_id=cell.id)),
        _church(known, tenant),  # déjà membre de l'église
    ])
    policy = _policy(church)
    vid = await _open_with_visitor(
        gatherings, visitors, groups, policy, leader, tenant, cell, phone="+2250700000099"
    )
    accounts = _FakeAccounts([_account("+2250700000099")])
    accounts._a[0] = Account(id=known, phone_number="+2250700000099",
                             status=AccountStatus.ACTIVE, first_name="Déjà")
    store = _FakeEnrollStore(church)
    convert = ConvertVisitor(
        visitors, gatherings, accounts, church, store, groups, gms, policy, clock=lambda: _NOW
    )

    result = await convert.execute(actor_account_id=leader, visitor_id=vid)

    assert result.reused_account is True
    assert store.enrolled == [] and store.added == []  # déjà membre : aucune appartenance créée
    assert await gms.get_active(known, cell.id) is not None  # mais rattaché au roster
    assert visitors._v == []


async def test_convert_visitor_without_phone_is_rejected():
    leader, tenant = uuid4(), uuid4()
    cell = _cell(tenant)
    groups, gms = _FakeGroups([cell]), _FakeGroupMemberships()
    gatherings, visitors = _FakeGatherings(), _FakeVisitors()
    church = _FakeChurch([_church(leader, tenant, _role(RoleCode.GROUP_LEADER, group_id=cell.id))])
    policy = _policy(church)
    vid = await _open_with_visitor(
        gatherings, visitors, groups, policy, leader, tenant, cell, phone=None
    )
    convert = ConvertVisitor(
        visitors, gatherings, _FakeAccounts(), church, _FakeEnrollStore(church), groups, gms,
        policy, clock=lambda: _NOW,
    )
    with pytest.raises(VisitorPhoneRequiredError):
        await convert.execute(actor_account_id=leader, visitor_id=vid)


async def test_convert_visitor_requires_enroll_authority():
    leader, tenant, outsider = uuid4(), uuid4(), uuid4()
    cell = _cell(tenant)
    groups, gms = _FakeGroups([cell]), _FakeGroupMemberships()
    gatherings, visitors = _FakeGatherings(), _FakeVisitors()
    church = _FakeChurch([_church(leader, tenant, _role(RoleCode.GROUP_LEADER, group_id=cell.id))])
    policy = _policy(church)
    vid = await _open_with_visitor(
        gatherings, visitors, groups, policy, leader, tenant, cell, phone="+2250700000099"
    )
    convert = ConvertVisitor(
        visitors, gatherings, _FakeAccounts(), church, _FakeEnrollStore(church), groups, gms,
        policy, clock=lambda: _NOW,
    )
    with pytest.raises(UnauthorizedGroupActionError):
        await convert.execute(actor_account_id=outsider, visitor_id=vid)  # pas d'autorité
