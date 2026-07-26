"""M7-0 — l'état de marche : algorithme pur (rythme personnel) + pulsation (cas Mme Richmond)."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.contexts.attendance.application.pulse_service import GroupPulseComputer
from app.contexts.attendance.application.queries.get_care_list import GetCareList
from app.contexts.attendance.application.queries.get_cell_health import GetCellHealth
from app.contexts.attendance.application.queries.get_church_dashboard import GetChurchDashboard
from app.contexts.attendance.application.queries.get_group_effectif import GetGroupEffectif
from app.contexts.attendance.application.queries.get_group_overview import GetGroupOverview
from app.contexts.attendance.application.queries.get_group_pulse import GetGroupPulse
from app.contexts.attendance.application.queries.get_group_trend import GetGroupTrend
from app.contexts.attendance.application.queries.get_member_trajectory import GetMemberTrajectory
from app.contexts.attendance.application.queries.get_multiplication_tree import (
    GetMultiplicationTree,
)
from app.contexts.attendance.domain.aggregates import AttendanceRecord, Gathering
from app.contexts.attendance.domain.enums import (
    AbsenceReason,
    AttendanceMark,
    AttendanceSource,
    GatheringStatus,
    GatheringType,
)
from app.contexts.attendance.domain.planned_absence import PlannedAbsence
from app.contexts.attendance.domain.pulse import Outcome, WalkState, compute_walk_state
from app.contexts.attendance.domain.repositories import (
    AttendanceRecordRepository,
    GatheringRepository,
    PlannedAbsenceRepository,
)
from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.groups.domain.aggregates import Group
from app.contexts.groups.domain.enums import GroupType
from app.contexts.groups.domain.errors import (
    GroupMembershipNotFoundError,
    UnauthorizedGroupActionError,
)
from app.contexts.groups.domain.membership import GroupMembership
from app.contexts.groups.domain.repositories import GroupMembershipRepository, GroupRepository
from app.contexts.iam.application.ports import OwnershipChecker
from app.contexts.iam.domain.aggregates import Membership
from app.contexts.iam.domain.entities import RoleAssignment
from app.contexts.iam.domain.enums import MembershipStatus, RoleCode
from app.contexts.iam.domain.repositories import MembershipRepository

_NOW = datetime(2026, 6, 1, tzinfo=UTC)
_JOIN = datetime(2025, 12, 1, tzinfo=UTC)  # avant toutes les rencontres de test
P, E, A = Outcome.PRESENT, Outcome.EXCUSED, Outcome.ABSENT


# --- L'algorithme pur (le cœur) ---


def test_new_when_not_enough_history():
    assert compute_walk_state([P]) == (WalkState.NEW, 0)  # 1 rencontre
    assert compute_walk_state([A, P]) == (WalkState.NEW, 0)  # 2 rencontres (< 3)


def test_engaged_when_coming():
    assert compute_walk_state([P, P, P, P])[0] is WalkState.ENGAGED


def test_awa_weekly_at_risk_after_three():
    # rythme = 1 ; 3 absences d'affilée → à interpeller.
    assert compute_walk_state([P, P, P, A, A])[0] is WalkState.ENGAGED  # 2 < 3
    assert compute_walk_state([P, P, P, A, A, A])[0] is WalkState.AT_RISK  # 3 >= 3


def test_yao_monthly_not_at_risk_for_normal_gap():
    # vient 1 rencontre sur 4 → rythme ~4 ; 3 absences = NORMAL pour lui.
    yao = [P, A, A, A, P, A, A, A, P, A, A, A]
    assert compute_walk_state(yao)[0] is WalkState.ENGAGED
    # ...mais un silence de 12 (3x son rythme) → à interpeller.
    yao_gone = [P, A, A, A, P, A, A, A, P] + [A] * 12
    assert compute_walk_state(yao_gone)[0] is WalkState.AT_RISK


def test_dormant_after_deep_silence():
    assert compute_walk_state([P, P, P] + [A] * 6)[0] is WalkState.DORMANT


def test_excused_does_not_count_as_silence():
    # a prévenu (M6-2) → jamais « à interpeller ».
    assert compute_walk_state([P, P, P, E, E, E])[0] is WalkState.ENGAGED
    assert compute_walk_state([P, P, P, A, E, A])[0] is WalkState.ENGAGED  # 2 absents concernés


# --- La pulsation de cellule (avec le signal réseau : Mme Richmond) ---


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
            (m for m in self._m
             if m.account_id == account_id and m.group_id == group_id and m.is_active),
            None,
        )

    async def list_active_by_group(self, group_id):
        return [m for m in self._m if m.group_id == group_id and m.is_active]


class _FakeGatherings(GatheringRepository):
    def __init__(self, items=()):
        self._g = list(items)

    async def add(self, g):
        self._g.append(g)

    async def get(self, gid):
        return next((g for g in self._g if g.id == gid), None)

    async def get_open_by_check_in_code(self, code):
        return None

    async def list_by_group(self, group_id):
        return [g for g in self._g if g.group_id == group_id]

    async def save(self, g):
        pass


class _FakeRecords(AttendanceRecordRepository):
    def __init__(self, items=(), *, elsewhere_accounts=()):
        self._r = list(items)
        self._elsewhere = set(elsewhere_accounts)

    async def add(self, r):
        self._r.append(r)

    async def get_for(self, gid, acc):
        return None

    async def remove(self, gid, acc):
        pass

    async def list_for_gathering(self, gid):
        return [r for r in self._r if r.gathering_id == gid]

    async def list_present_for_gatherings(self, gathering_ids):
        ids = set(gathering_ids)
        return [r for r in self._r if r.gathering_id in ids]

    async def has_present_in_other_tenant_since(self, account_id, tenant_id, since):
        return account_id in self._elsewhere


class _FakeAbsences(PlannedAbsenceRepository):
    def __init__(self, items=()):
        self._a = list(items)

    async def add(self, a):
        pass

    async def get(self, aid):
        return None

    async def save(self, a):
        pass

    async def list_active_by_tenant(self, tenant_id):
        return [a for a in self._a if a.tenant_id == tenant_id and a.is_active]

    async def list_active_by_account(self, account_id, tenant_id):
        return []

    async def get_by_source(self, account_id, source_ref):
        return None

    async def list_open_neutralizations(self, account_id, tenant_id):
        return []

    async def list_open_neutralizations_by_tenant(self, tenant_id):
        return []

    async def delete_projected(self, tenant_id):
        pass


def _church(account_id, tenant_id, *roles: RoleAssignment) -> Membership:
    return Membership(
        id=uuid4(), account_id=account_id, tenant_id=tenant_id,
        status=MembershipStatus.CONFIRMED_MEMBER, last_transition_at=_NOW,
        role_assignments=list(roles),
    )


def _cell(tenant_id) -> Group:
    return Group.create_root(
        id=uuid4(), tenant_id=tenant_id, name="Cellule", type=GroupType.CELLULE, now=_NOW,
        created_by_account_id=uuid4(),
    )


def _weekly_gatherings(tenant, group, n):
    base = datetime(2026, 1, 1, tzinfo=UTC)
    return [
        Gathering(
            id=uuid4(), tenant_id=tenant, group_id=group.id, type=GatheringType.MEETING,
            title=None, scheduled_at=base + timedelta(weeks=i), status=GatheringStatus.CLOSED,
            created_by_account_id=uuid4(), created_at=base + timedelta(weeks=i),
        )
        for i in range(n)
    ]


def _present(gathering, account_id):
    return AttendanceRecord(
        id=uuid4(), gathering_id=gathering.id, account_id=account_id,
        mark=AttendanceMark.PRESENT, source=AttendanceSource.LEADER, recorded_at=_NOW,
        recorded_by_account_id=uuid4(),
    )


def _member(group, account_id, tenant):
    return GroupMembership.join(
        id=uuid4(), group_id=group.id, account_id=account_id, tenant_id=tenant, now=_JOIN,
        joined_by_account_id=uuid4(),
    )


def _computer(gatherings, records, gms, absences=None):
    return GroupPulseComputer(gatherings, records, absences or _FakeAbsences(), gms)


def _pulse(gatherings, records, groups, gms, church, *, owners, absences=None) -> GetGroupPulse:
    access = GroupAccessPolicy(_FakeOwnership(owners), church)
    return GetGroupPulse(
        _computer(gatherings, records, gms, absences), groups, access, clock=lambda: _NOW
    )


async def test_richmond_is_shared_not_at_risk():
    owner, tenant, richmond = uuid4(), uuid4(), uuid4()
    cell = _cell(tenant)
    gs = _weekly_gatherings(tenant, cell, 6)
    # présente g0,g1 puis silence local g2..g5 → base at_risk, mais active ailleurs.
    records = _FakeRecords(
        [_present(gs[0], richmond), _present(gs[1], richmond)], elsewhere_accounts={richmond}
    )
    pulse = _pulse(
        _FakeGatherings(gs), records, _FakeGroups([cell]),
        _FakeGroupMemberships([_member(cell, richmond, tenant)]), _FakeChurch(),
        owners={(owner, tenant)},
    )
    dto = await pulse.execute(actor_account_id=owner, tenant_id=tenant, group_id=cell.id)
    entry = dto.entries[0]
    assert entry.state == "shared"  # pas perdue — active à Soba
    assert entry.needs_care is False
    assert dto.needs_care_count == 0


async def test_truly_silent_member_is_at_risk():
    owner, tenant, koffi = uuid4(), uuid4(), uuid4()
    cell = _cell(tenant)
    gs = _weekly_gatherings(tenant, cell, 6)
    records = _FakeRecords([_present(gs[0], koffi), _present(gs[1], koffi)])
    pulse = _pulse(
        _FakeGatherings(gs), records, _FakeGroups([cell]),
        _FakeGroupMemberships([_member(cell, koffi, tenant)]), _FakeChurch(),
        owners={(owner, tenant)},
    )
    dto = await pulse.execute(actor_account_id=owner, tenant_id=tenant, group_id=cell.id)
    assert dto.entries[0].state == "at_risk"
    assert dto.entries[0].needs_care is True
    assert dto.needs_care_count == 1


async def test_pulse_requires_pastoral_view():
    outsider, tenant = uuid4(), uuid4()
    cell = _cell(tenant)
    # accueil : pas de VIEW_PASTORAL_ALERTS.
    church = _FakeChurch([_church(outsider, tenant, RoleAssignment(
        id=uuid4(), role=RoleCode.WELCOME_TEAM, group_id=None, assigned_at=_NOW,
        assigned_by_account_id=uuid4(),
    ))])
    pulse = _pulse(
        _FakeGatherings(), _FakeRecords(), _FakeGroups([cell]),
        _FakeGroupMemberships(), church, owners=set(),
    )
    with pytest.raises(UnauthorizedGroupActionError):
        await pulse.execute(actor_account_id=outsider, tenant_id=tenant, group_id=cell.id)


# --- M7-1 : effectif réel (gravité, candidats à revoir) ---


def _moved_absence(account_id, tenant):
    return PlannedAbsence(
        id=uuid4(), account_id=account_id, tenant_id=tenant, reason=AbsenceReason.MOVED,
        from_date=datetime(2026, 1, 1, tzinfo=UTC), to_date=datetime(2026, 12, 31, tzinfo=UTC),
        declared_by_account_id=account_id, declared_at=_NOW,
    )


async def test_effectif_is_honest_and_suggests_candidates():
    owner, tenant = uuid4(), uuid4()
    engaged, richmond, dormant, moved = uuid4(), uuid4(), uuid4(), uuid4()
    cell = _cell(tenant)
    gs = _weekly_gatherings(tenant, cell, 8)
    records = _FakeRecords(
        [
            # engagé : présent récemment (g6,g7).
            _present(gs[6], engaged), _present(gs[7], engaged),
            # richmond : présente au début puis silence local, mais active ailleurs.
            _present(gs[0], richmond), _present(gs[1], richmond),
            # dormant : présent tout au début puis grand silence (>= 6x).
            _present(gs[0], dormant), _present(gs[1], dormant),
            # moved : présent au début (avant de déménager).
            _present(gs[0], moved), _present(gs[1], moved),
        ],
        elsewhere_accounts={richmond},
    )
    gms = _FakeGroupMemberships(
        [_member(cell, x, tenant) for x in (engaged, richmond, dormant, moved)]
    )
    absences = _FakeAbsences([_moved_absence(moved, tenant)])  # déménagement déclaré, couvre _NOW
    access = GroupAccessPolicy(_FakeOwnership({(owner, tenant)}), _FakeChurch())
    effectif = GetGroupEffectif(
        _computer(_FakeGatherings(gs), records, gms, absences), _FakeGroups([cell]), access,
        clock=lambda: _NOW,
    )

    dto = await effectif.execute(actor_account_id=owner, tenant_id=tenant, group_id=cell.id)

    assert dto.total_members == 4
    assert dto.active_count == 2  # engagé + richmond (partagé) ; dormant & moved exclus
    assert dto.shared_count == 1  # richmond
    reasons = {c.account_id: c.reason for c in dto.review_candidates}
    assert reasons[dormant] == "prolonged_silence"
    assert reasons[moved] == "declared_moved"
    assert engaged not in reasons and richmond not in reasons


# --- M7-2 : liste de soin église-entière ---


async def test_care_list_aggregates_across_groups_excluding_shared():
    owner, tenant = uuid4(), uuid4()
    richmond, koffi = uuid4(), uuid4()
    cell_a, cell_b = _cell(tenant), _cell(tenant)
    gsa, gsb = _weekly_gatherings(tenant, cell_a, 6), _weekly_gatherings(tenant, cell_b, 6)
    records = _FakeRecords(
        [_present(gsa[0], richmond), _present(gsa[1], richmond),  # richmond dans cell_a
         _present(gsb[0], koffi), _present(gsb[1], koffi)],  # koffi dans cell_b
        elsewhere_accounts={richmond},
    )
    groups = _FakeGroups([cell_a, cell_b])
    gms = _FakeGroupMemberships(
        [_member(cell_a, richmond, tenant), _member(cell_b, koffi, tenant)]
    )
    access = GroupAccessPolicy(_FakeOwnership({(owner, tenant)}), _FakeChurch())
    care = GetCareList(
        _computer(_FakeGatherings(gsa + gsb), records, gms), groups, access, clock=lambda: _NOW
    )
    dto = await care.execute(actor_account_id=owner, tenant_id=tenant)

    # Koffi (silence réel) à interpeller ; Richmond (partagée) jamais.
    assert dto.count == 1
    assert dto.entries[0].account_id == koffi
    assert dto.entries[0].group_id == cell_b.id


async def test_care_list_requires_church_wide_authority():
    tenant, leader = uuid4(), uuid4()
    cell = _cell(tenant)
    # responsable scopé (group_leader) : pas d'autorité église-entière.
    church = _FakeChurch(
        [_church(leader, tenant, RoleAssignment(
            id=uuid4(), role=RoleCode.GROUP_LEADER, group_id=cell.id, assigned_at=_NOW,
            assigned_by_account_id=uuid4(),
        ))]
    )
    care = GetCareList(
        _computer(_FakeGatherings(), _FakeRecords(), _FakeGroupMemberships()),
        _FakeGroups([cell]), GroupAccessPolicy(_FakeOwnership(), church), clock=lambda: _NOW,
    )
    with pytest.raises(UnauthorizedGroupActionError):
        await care.execute(actor_account_id=leader, tenant_id=tenant)


# --- M7-3 : ready_to_multiply honnête ---


async def test_cell_health_uses_real_presence_not_roster():
    from app.contexts.groups.application.commands.multiply_cell import MULTIPLY_THRESHOLD

    owner, tenant = uuid4(), uuid4()
    cell = _cell(tenant)
    gs = _weekly_gatherings(tenant, cell, 8)
    # roster gonflé : MULTIPLY_THRESHOLD+2 inscrits, mais seuls 2 viennent vraiment.
    members = [uuid4() for _ in range(MULTIPLY_THRESHOLD + 2)]
    present_records = [_present(gs[6], members[0]), _present(gs[7], members[0]),
                       _present(gs[6], members[1]), _present(gs[7], members[1])]
    records = _FakeRecords(present_records)  # les autres : jamais présents → dormants/nouveaux
    gms = _FakeGroupMemberships([_member(cell, m, tenant) for m in members])
    access = GroupAccessPolicy(_FakeOwnership({(owner, tenant)}), _FakeChurch())
    health = GetCellHealth(
        _computer(_FakeGatherings(gs), records, gms), _FakeGroups([cell]), gms, access,
        clock=lambda: _NOW,
    )
    dto = await health.execute(actor_account_id=owner, tenant_id=tenant, group_id=cell.id)

    assert dto.roster_count == MULTIPLY_THRESHOLD + 2  # gonflé sur le papier
    assert dto.active_count == 2  # présents réels
    assert dto.ready_to_multiply is False  # honnête : pas prête malgré le roster


# --- B7 : détail groupe (mobile) & tableau de bord (backoffice) ---


async def test_group_overview_returns_info_and_realities():
    owner, tenant, awa = uuid4(), uuid4(), uuid4()
    cell = _cell(tenant)
    gs = _weekly_gatherings(tenant, cell, 6)
    records = _FakeRecords([_present(gs[5], awa)])  # présente à la dernière → engagée
    gms = _FakeGroupMemberships([_member(cell, awa, tenant)])
    access = GroupAccessPolicy(_FakeOwnership({(owner, tenant)}), _FakeChurch())
    overview = GetGroupOverview(
        _computer(_FakeGatherings(gs), records, gms), _FakeGroups([cell]), gms, access,
        clock=lambda: _NOW,
    )
    dto = await overview.execute(actor_account_id=owner, tenant_id=tenant, group_id=cell.id)

    assert dto.name == "Cellule" and dto.type == "cellule"  # infos
    assert dto.roster_count == 1 and dto.active_count == 1  # réalités
    assert dto.at_risk_count == 0
    assert dto.ready_to_multiply is False


async def test_church_dashboard_aggregates_all_groups():
    owner, tenant, koffi = uuid4(), uuid4(), uuid4()
    cell_a, cell_b = _cell(tenant), _cell(tenant)
    gsa = _weekly_gatherings(tenant, cell_a, 6)
    records = _FakeRecords([_present(gsa[0], koffi), _present(gsa[1], koffi)])  # puis silence
    gms = _FakeGroupMemberships([_member(cell_a, koffi, tenant)])  # cell_b : vide
    access = GroupAccessPolicy(_FakeOwnership({(owner, tenant)}), _FakeChurch())
    dashboard = GetChurchDashboard(
        _computer(_FakeGatherings(gsa), records, gms), _FakeGroups([cell_a, cell_b]), gms, access,
        clock=lambda: _NOW,
    )
    dto = await dashboard.execute(actor_account_id=owner, tenant_id=tenant)

    assert dto.groups_count == 2  # la grille couvre toutes les cellules
    assert dto.members_needing_care == 1  # koffi (at_risk), distinct
    assert dto.cells_ready_to_multiply == 0
    by_id = {c.group_id: c for c in dto.groups}
    assert by_id[cell_a.id].at_risk_count == 1
    assert by_id[cell_b.id].roster_count == 0


async def test_dashboard_requires_church_wide_authority():
    leader, tenant = uuid4(), uuid4()
    cell = _cell(tenant)
    church = _FakeChurch([_church(leader, tenant, RoleAssignment(
        id=uuid4(), role=RoleCode.GROUP_LEADER, group_id=cell.id, assigned_at=_NOW,
        assigned_by_account_id=uuid4(),
    ))])
    dashboard = GetChurchDashboard(
        _computer(_FakeGatherings(), _FakeRecords(), _FakeGroupMemberships()),
        _FakeGroups([cell]), _FakeGroupMemberships(),
        GroupAccessPolicy(_FakeOwnership(), church), clock=lambda: _NOW,
    )
    with pytest.raises(UnauthorizedGroupActionError):
        await dashboard.execute(actor_account_id=leader, tenant_id=tenant)


# --- B7+ : trajectoire individuelle (le drill-down, révélateur pas juge) ---


async def test_member_trajectory_tells_the_story():
    owner, tenant, koffi = uuid4(), uuid4(), uuid4()
    cell = _cell(tenant)
    gs = _weekly_gatherings(tenant, cell, 6)
    records = _FakeRecords([_present(gs[0], koffi), _present(gs[1], koffi)])  # puis silence
    gms = _FakeGroupMemberships([_member(cell, koffi, tenant)])
    access = GroupAccessPolicy(_FakeOwnership({(owner, tenant)}), _FakeChurch())
    traj = GetMemberTrajectory(
        _computer(_FakeGatherings(gs), records, gms), _FakeGroups([cell]), access,
        clock=lambda: _NOW,
    )
    dto = await traj.execute(
        actor_account_id=owner, tenant_id=tenant, group_id=cell.id, account_id=koffi
    )

    assert dto.state == "at_risk" and dto.needs_care is True
    assert dto.missed == 4  # 4 rencontres absentes depuis la dernière venue
    assert [p.outcome for p in dto.points] == ["present", "present"] + ["absent"] * 4
    assert dto.last_present_at == gs[1].scheduled_at
    assert dto.active_elsewhere is False
    assert dto.current_absence_reason is None  # il n'a pas prévenu


async def test_member_trajectory_shows_shared_when_active_elsewhere():
    owner, tenant, richmond = uuid4(), uuid4(), uuid4()
    cell = _cell(tenant)
    gs = _weekly_gatherings(tenant, cell, 6)
    records = _FakeRecords(
        [_present(gs[0], richmond), _present(gs[1], richmond)], elsewhere_accounts={richmond}
    )
    gms = _FakeGroupMemberships([_member(cell, richmond, tenant)])
    access = GroupAccessPolicy(_FakeOwnership({(owner, tenant)}), _FakeChurch())
    traj = GetMemberTrajectory(
        _computer(_FakeGatherings(gs), records, gms), _FakeGroups([cell]), access,
        clock=lambda: _NOW,
    )
    dto = await traj.execute(
        actor_account_id=owner, tenant_id=tenant, group_id=cell.id, account_id=richmond
    )

    assert dto.state == "shared" and dto.needs_care is False  # active à Soba, pas perdue
    assert dto.active_elsewhere is True


async def test_member_trajectory_unknown_member_raises():
    owner, tenant = uuid4(), uuid4()
    cell = _cell(tenant)
    access = GroupAccessPolicy(_FakeOwnership({(owner, tenant)}), _FakeChurch())
    traj = GetMemberTrajectory(
        _computer(_FakeGatherings(), _FakeRecords(), _FakeGroupMemberships()),
        _FakeGroups([cell]), access, clock=lambda: _NOW,
    )
    with pytest.raises(GroupMembershipNotFoundError):
        await traj.execute(
            actor_account_id=owner, tenant_id=tenant, group_id=cell.id, account_id=uuid4()
        )


# --- B7+ : série temporelle (le momentum, pas la photo) ---


async def test_group_trend_reveals_momentum():
    owner, tenant, koffi = uuid4(), uuid4(), uuid4()
    cell = _cell(tenant)
    gs = _weekly_gatherings(tenant, cell, 6)  # jan 1,8,15,22,29 ; fév 5
    records = _FakeRecords([_present(gs[0], koffi), _present(gs[1], koffi)])  # puis silence
    gms = _FakeGroupMemberships([_member(cell, koffi, tenant)])
    access = GroupAccessPolicy(_FakeOwnership({(owner, tenant)}), _FakeChurch())
    trend = GetGroupTrend(
        _computer(_FakeGatherings(gs), records, gms), _FakeGroups([cell]), access,
        clock=lambda: datetime(2026, 2, 10, tzinfo=UTC),
    )
    dto = await trend.execute(
        actor_account_id=owner, tenant_id=tenant, group_id=cell.id, weeks=6
    )

    assert len(dto.points) == 6
    # le silence de Koffi apparaît dans la dérivée (les semaines les plus récentes)
    assert [p.at_risk_count for p in dto.points] == [0, 0, 0, 0, 1, 1]
    assert all(p.roster_count == 1 for p in dto.points)  # un seul inscrit tout du long
    assert dto.points == sorted(dto.points, key=lambda p: p.as_of)  # chronologique


async def test_group_trend_clamps_weeks():
    owner, tenant = uuid4(), uuid4()
    cell = _cell(tenant)
    access = GroupAccessPolicy(_FakeOwnership({(owner, tenant)}), _FakeChurch())
    trend = GetGroupTrend(
        _computer(_FakeGatherings(), _FakeRecords(), _FakeGroupMemberships()),
        _FakeGroups([cell]), access, clock=lambda: _NOW,
    )
    dto = await trend.execute(
        actor_account_id=owner, tenant_id=tenant, group_id=cell.id, weeks=100
    )
    assert len(dto.points) == 26  # garde-fou ~6 mois


# --- B7+ : arbre de multiplication (la vision, la fertilité) ---


def _named_cell(tenant, name) -> Group:
    cell = _cell(tenant)
    cell.rename(name)
    return cell


async def test_multiplication_tree_shows_reproduction_forest():
    owner, tenant = uuid4(), uuid4()
    a = _named_cell(tenant, "A")
    b = a.multiply(daughter_id=uuid4(), name="B", now=_NOW, created_by_account_id=uuid4())
    c = b.multiply(daughter_id=uuid4(), name="C", now=_NOW, created_by_account_id=uuid4())
    d = _named_cell(tenant, "D")  # cellule souche indépendante (stérile)
    ministry = Group.create_root(  # un ministère : n'appartient pas à l'arbre cellulaire
        id=uuid4(), tenant_id=tenant, name="Louange", type=GroupType.MINISTERE, now=_NOW,
        created_by_account_id=uuid4(),
    )
    access = GroupAccessPolicy(_FakeOwnership({(owner, tenant)}), _FakeChurch())
    tree = GetMultiplicationTree(
        _computer(_FakeGatherings(), _FakeRecords(), _FakeGroupMemberships()),
        _FakeGroups([a, b, c, d, ministry]), _FakeGroupMemberships(), access,
        clock=lambda: _NOW,
    )
    dto = await tree.execute(actor_account_id=owner, tenant_id=tenant)

    assert dto.cells_count == 4  # le ministère est exclu
    assert dto.max_generation == 3  # A -> B -> C
    assert [r.vitals.name for r in dto.roots] == ["A", "D"]  # deux souches, triées par nom
    root_a = dto.roots[0]
    assert root_a.vitals.generation == 1
    assert [ch.vitals.name for ch in root_a.children] == ["B"]  # A a enfanté B
    b_node = root_a.children[0]
    assert b_node.vitals.generation == 2
    assert [ch.vitals.name for ch in b_node.children] == ["C"]  # B a enfanté C
    assert b_node.children[0].vitals.generation == 3
    assert dto.roots[1].children == []  # D reste stérile


async def test_multiplication_tree_orphan_becomes_root():
    # La mère est clôturée (hors périmètre actif) → la fille redevient racine visible.
    owner, tenant = uuid4(), uuid4()
    a = _named_cell(tenant, "A")
    b = a.multiply(daughter_id=uuid4(), name="B", now=_NOW, created_by_account_id=uuid4())
    a.mark_closed()  # la mère disparaît de list_active_by_tenant
    access = GroupAccessPolicy(_FakeOwnership({(owner, tenant)}), _FakeChurch())
    tree = GetMultiplicationTree(
        _computer(_FakeGatherings(), _FakeRecords(), _FakeGroupMemberships()),
        _FakeGroups([a, b]), _FakeGroupMemberships(), access, clock=lambda: _NOW,
    )
    dto = await tree.execute(actor_account_id=owner, tenant_id=tenant)

    assert dto.cells_count == 1  # seule B est active
    assert [r.vitals.name for r in dto.roots] == ["B"]  # B, orpheline, devient racine


async def test_multiplication_tree_requires_church_wide_authority():
    leader, tenant = uuid4(), uuid4()
    cell = _cell(tenant)
    church = _FakeChurch([_church(leader, tenant, RoleAssignment(
        id=uuid4(), role=RoleCode.GROUP_LEADER, group_id=cell.id, assigned_at=_NOW,
        assigned_by_account_id=uuid4(),
    ))])
    tree = GetMultiplicationTree(
        _computer(_FakeGatherings(), _FakeRecords(), _FakeGroupMemberships()),
        _FakeGroups([cell]), _FakeGroupMemberships(),
        GroupAccessPolicy(_FakeOwnership(), church), clock=lambda: _NOW,
    )
    with pytest.raises(UnauthorizedGroupActionError):
        await tree.execute(actor_account_id=leader, tenant_id=tenant)
