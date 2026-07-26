"""Injection de dépendances du contexte Présence (surface mobile, M6-0)."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends

from app.api.deps import DbSession
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
from app.contexts.attendance.application.pulse_service import GroupPulseComputer
from app.contexts.attendance.application.queries.get_care_list import GetCareList
from app.contexts.attendance.application.queries.get_cell_health import GetCellHealth
from app.contexts.attendance.application.queries.get_church_dashboard import GetChurchDashboard
from app.contexts.attendance.application.queries.get_gathering_roster import GetGatheringRoster
from app.contexts.attendance.application.queries.get_group_effectif import GetGroupEffectif
from app.contexts.attendance.application.queries.get_group_overview import GetGroupOverview
from app.contexts.attendance.application.queries.get_group_pulse import GetGroupPulse
from app.contexts.attendance.application.queries.get_group_trend import GetGroupTrend
from app.contexts.attendance.application.queries.get_member_trajectory import GetMemberTrajectory
from app.contexts.attendance.application.queries.get_multiplication_tree import (
    GetMultiplicationTree,
)
from app.contexts.attendance.application.queries.get_my_absences import GetMyPlannedAbsences
from app.contexts.attendance.application.queries.list_gathering_visitors import (
    ListGatheringVisitors,
)
from app.contexts.attendance.application.return_detection import DetectReturn
from app.contexts.attendance.infrastructure.code_generator import SecureSessionCodeGenerator
from app.contexts.attendance.infrastructure.persistence.absence_repository import (
    SqlPlannedAbsenceRepository,
    SqlWatchExclusionRepository,
)
from app.contexts.attendance.infrastructure.persistence.repositories import (
    SqlAttendanceRecordRepository,
    SqlGatheringRepository,
)
from app.contexts.attendance.infrastructure.persistence.rsvp_repository import (
    SqlGatheringRsvpRepository,
)
from app.contexts.attendance.infrastructure.persistence.visitor_repository import (
    SqlVisitorRepository,
)
from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.groups.infrastructure.persistence.repositories import (
    SqlGroupMembershipRepository,
    SqlGroupRepository,
)
from app.contexts.iam.infrastructure.persistence.enrollment import SqlMemberEnrollmentStore
from app.contexts.iam.infrastructure.persistence.repositories import (
    SqlAlchemyAccountRepository,
    SqlAlchemyMembershipRepository,
)
from app.contexts.tenant.infrastructure.persistence.ownership_repo import SqlOwnershipRepository
from app.contexts.watch.interface.dependencies import build_intake


def get_group_access_policy(session: DbSession) -> GroupAccessPolicy:
    return GroupAccessPolicy(
        SqlOwnershipRepository(session), SqlAlchemyMembershipRepository(session)
    )


GroupAccessPolicyDep = Annotated[GroupAccessPolicy, Depends(get_group_access_policy)]


_session_codes = SecureSessionCodeGenerator()  # sans état → instance unique


def get_session_code_generator() -> SessionCodeGenerator:
    return _session_codes


SessionCodeGeneratorDep = Annotated[SessionCodeGenerator, Depends(get_session_code_generator)]


def get_create_gathering_command(
    codes: SessionCodeGeneratorDep, access: GroupAccessPolicyDep, session: DbSession
) -> CreateGathering:
    return CreateGathering(
        SqlGatheringRepository(session), SqlGroupRepository(session), codes, access,
        clock=lambda: datetime.now(UTC),
    )


def get_self_check_in_command(session: DbSession) -> SelfCheckIn:
    return SelfCheckIn(
        SqlGatheringRepository(session),
        SqlAttendanceRecordRepository(session),
        SqlGroupMembershipRepository(session),
        DetectReturn(build_intake(session)),
        clock=lambda: datetime.now(UTC),
    )


def _returns(session) -> DetectReturn:
    """La présence est une **source** du moteur : elle émet un fait, elle ne décide rien."""
    return DetectReturn(build_intake(session))


def get_mark_present_command(access: GroupAccessPolicyDep, session: DbSession) -> MarkPresent:
    return MarkPresent(
        SqlGatheringRepository(session),
        SqlAttendanceRecordRepository(session),
        SqlGroupRepository(session),
        SqlGroupMembershipRepository(session),
        access,
        _returns(session),
        clock=lambda: datetime.now(UTC),
    )


def get_unmark_present_command(access: GroupAccessPolicyDep, session: DbSession) -> UnmarkPresent:
    return UnmarkPresent(
        SqlGatheringRepository(session),
        SqlAttendanceRecordRepository(session),
        SqlGroupRepository(session),
        access,
        clock=lambda: datetime.now(UTC),
    )


def get_close_gathering_command(
    access: GroupAccessPolicyDep, session: DbSession
) -> CloseGathering:
    return CloseGathering(
        SqlGatheringRepository(session), SqlGroupRepository(session), access,
        clock=lambda: datetime.now(UTC),
    )


def get_gathering_roster_query(
    access: GroupAccessPolicyDep, session: DbSession
) -> GetGatheringRoster:
    return GetGatheringRoster(
        SqlGatheringRepository(session),
        SqlAttendanceRecordRepository(session),
        SqlPlannedAbsenceRepository(session),
        SqlGatheringRsvpRepository(session),
        SqlGroupRepository(session),
        SqlGroupMembershipRepository(session),
        access,
    )


def get_declare_absence_command(session: DbSession) -> DeclareAbsence:
    return DeclareAbsence(
        SqlPlannedAbsenceRepository(session),
        SqlAlchemyMembershipRepository(session),
        clock=lambda: datetime.now(UTC),
    )


def get_cancel_absence_command(session: DbSession) -> CancelAbsence:
    return CancelAbsence(SqlPlannedAbsenceRepository(session), clock=lambda: datetime.now(UTC))


def get_my_absences_query(session: DbSession) -> GetMyPlannedAbsences:
    return GetMyPlannedAbsences(SqlPlannedAbsenceRepository(session))


def get_add_visitor_command(access: GroupAccessPolicyDep, session: DbSession) -> AddVisitor:
    return AddVisitor(
        SqlGatheringRepository(session),
        SqlVisitorRepository(session),
        SqlGroupRepository(session),
        access,
        clock=lambda: datetime.now(UTC),
    )


def get_remove_visitor_command(access: GroupAccessPolicyDep, session: DbSession) -> RemoveVisitor:
    return RemoveVisitor(
        SqlGatheringRepository(session),
        SqlVisitorRepository(session),
        SqlGroupRepository(session),
        access,
    )


def get_convert_visitor_command(
    access: GroupAccessPolicyDep, session: DbSession
) -> ConvertVisitor:
    return ConvertVisitor(
        SqlVisitorRepository(session),
        SqlGatheringRepository(session),
        SqlAlchemyAccountRepository(session),
        SqlAlchemyMembershipRepository(session),
        SqlMemberEnrollmentStore(session),
        SqlGroupRepository(session),
        SqlGroupMembershipRepository(session),
        access,
        clock=lambda: datetime.now(UTC),
    )


def get_list_visitors_query(
    access: GroupAccessPolicyDep, session: DbSession
) -> ListGatheringVisitors:
    return ListGatheringVisitors(
        SqlGatheringRepository(session),
        SqlVisitorRepository(session),
        SqlGroupRepository(session),
        access,
    )


def _pulse_computer(session) -> GroupPulseComputer:
    return GroupPulseComputer(
        SqlGatheringRepository(session),
        SqlAttendanceRecordRepository(session),
        SqlPlannedAbsenceRepository(session),
        SqlGroupMembershipRepository(session),
        SqlWatchExclusionRepository(session),
    )


def get_group_pulse_query(access: GroupAccessPolicyDep, session: DbSession) -> GetGroupPulse:
    return GetGroupPulse(
        _pulse_computer(session), SqlGroupRepository(session), access,
        clock=lambda: datetime.now(UTC),
    )


def get_group_effectif_query(
    access: GroupAccessPolicyDep, session: DbSession
) -> GetGroupEffectif:
    return GetGroupEffectif(
        _pulse_computer(session), SqlGroupRepository(session), access,
        clock=lambda: datetime.now(UTC),
    )


def get_care_list_query(access: GroupAccessPolicyDep, session: DbSession) -> GetCareList:
    return GetCareList(
        _pulse_computer(session), SqlGroupRepository(session), access,
        clock=lambda: datetime.now(UTC),
    )


def get_cell_health_query(access: GroupAccessPolicyDep, session: DbSession) -> GetCellHealth:
    return GetCellHealth(
        _pulse_computer(session),
        SqlGroupRepository(session),
        SqlGroupMembershipRepository(session),
        access,
        clock=lambda: datetime.now(UTC),
    )


def get_group_overview_query(
    access: GroupAccessPolicyDep, session: DbSession
) -> GetGroupOverview:
    return GetGroupOverview(
        _pulse_computer(session),
        SqlGroupRepository(session),
        SqlGroupMembershipRepository(session),
        access,
        clock=lambda: datetime.now(UTC),
    )


def get_group_trend_query(access: GroupAccessPolicyDep, session: DbSession) -> GetGroupTrend:
    return GetGroupTrend(
        _pulse_computer(session), SqlGroupRepository(session), access,
        clock=lambda: datetime.now(UTC),
    )


def get_member_trajectory_query(
    access: GroupAccessPolicyDep, session: DbSession
) -> GetMemberTrajectory:
    return GetMemberTrajectory(
        _pulse_computer(session), SqlGroupRepository(session), access,
        clock=lambda: datetime.now(UTC),
    )


def get_church_dashboard_query(
    access: GroupAccessPolicyDep, session: DbSession
) -> GetChurchDashboard:
    return GetChurchDashboard(
        _pulse_computer(session),
        SqlGroupRepository(session),
        SqlGroupMembershipRepository(session),
        access,
        clock=lambda: datetime.now(UTC),
    )


def get_multiplication_tree_query(
    access: GroupAccessPolicyDep, session: DbSession
) -> GetMultiplicationTree:
    return GetMultiplicationTree(
        _pulse_computer(session),
        SqlGroupRepository(session),
        SqlGroupMembershipRepository(session),
        access,
        clock=lambda: datetime.now(UTC),
    )


CreateGatheringDep = Annotated[CreateGathering, Depends(get_create_gathering_command)]
SelfCheckInDep = Annotated[SelfCheckIn, Depends(get_self_check_in_command)]
MarkPresentDep = Annotated[MarkPresent, Depends(get_mark_present_command)]
UnmarkPresentDep = Annotated[UnmarkPresent, Depends(get_unmark_present_command)]
CloseGatheringDep = Annotated[CloseGathering, Depends(get_close_gathering_command)]
GetGatheringRosterDep = Annotated[GetGatheringRoster, Depends(get_gathering_roster_query)]
DeclareAbsenceDep = Annotated[DeclareAbsence, Depends(get_declare_absence_command)]
CancelAbsenceDep = Annotated[CancelAbsence, Depends(get_cancel_absence_command)]
GetMyPlannedAbsencesDep = Annotated[GetMyPlannedAbsences, Depends(get_my_absences_query)]
AddVisitorDep = Annotated[AddVisitor, Depends(get_add_visitor_command)]
RemoveVisitorDep = Annotated[RemoveVisitor, Depends(get_remove_visitor_command)]
ConvertVisitorDep = Annotated[ConvertVisitor, Depends(get_convert_visitor_command)]
ListGatheringVisitorsDep = Annotated[ListGatheringVisitors, Depends(get_list_visitors_query)]
GetGroupPulseDep = Annotated[GetGroupPulse, Depends(get_group_pulse_query)]
GetGroupEffectifDep = Annotated[GetGroupEffectif, Depends(get_group_effectif_query)]
GetCareListDep = Annotated[GetCareList, Depends(get_care_list_query)]
GetCellHealthDep = Annotated[GetCellHealth, Depends(get_cell_health_query)]
GetGroupOverviewDep = Annotated[GetGroupOverview, Depends(get_group_overview_query)]
GetGroupTrendDep = Annotated[GetGroupTrend, Depends(get_group_trend_query)]
GetMemberTrajectoryDep = Annotated[GetMemberTrajectory, Depends(get_member_trajectory_query)]
GetChurchDashboardDep = Annotated[GetChurchDashboard, Depends(get_church_dashboard_query)]
GetMultiplicationTreeDep = Annotated[
    GetMultiplicationTree, Depends(get_multiplication_tree_query)
]
