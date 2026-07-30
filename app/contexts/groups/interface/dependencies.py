"""Injection de dépendances du contexte Groupes (surface backoffice, G-0)."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends

from app.api.deps import DbSession, SettingsDep
from app.contexts.groups.application.commands.add_group_member import AddGroupMember
from app.contexts.groups.application.commands.appoint_group_leadership import AppointGroupLeadership
from app.contexts.groups.application.commands.close_group import CloseGroup
from app.contexts.groups.application.commands.create_group import CreateGroup
from app.contexts.groups.application.commands.create_group_invitation import CreateGroupInvitation
from app.contexts.groups.application.commands.join_group_by_code import JoinGroupByCode
from app.contexts.groups.application.commands.leave_group import LeaveGroup
from app.contexts.groups.application.commands.modify_group import ModifyGroup
from app.contexts.groups.application.commands.multiply_cell import MultiplyCell
from app.contexts.groups.application.commands.promote_group_to_church import PromoteGroupToChurch
from app.contexts.groups.application.commands.remove_group_member import RemoveGroupMember
from app.contexts.groups.application.commands.revoke_group_invitation import RevokeGroupInvitation
from app.contexts.groups.application.commands.revoke_group_leadership import RevokeGroupLeadership
from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.groups.application.ports import InvitationCodeGenerator
from app.contexts.groups.application.queries.get_cell_report import GetCellReport
from app.contexts.groups.application.queries.list_group_members import ListGroupMembers
from app.contexts.groups.application.watch_facts import EmitJoinedGroupFact
from app.contexts.groups.infrastructure.code_generator import SecureInvitationCodeGenerator
from app.contexts.groups.infrastructure.persistence.church_enrollment_store import (
    SqlChurchEnrollmentStore,
)
from app.contexts.groups.infrastructure.persistence.church_plant_store import SqlChurchPlantStore
from app.contexts.groups.infrastructure.persistence.church_role_store import SqlChurchRoleStore
from app.contexts.groups.infrastructure.persistence.invitation_repository import (
    SqlGroupInvitationRepository,
)
from app.contexts.groups.infrastructure.persistence.repositories import (
    SqlGroupMembershipRepository,
    SqlGroupRepository,
)
from app.contexts.iam.infrastructure.persistence.repositories import SqlAlchemyMembershipRepository
from app.contexts.tenant.infrastructure.persistence.ownership_repo import SqlOwnershipRepository
from app.contexts.watch.interface.dependencies import (
    build_absence_rhythm,
    build_intake,
)


def get_group_access_policy(session: DbSession) -> GroupAccessPolicy:
    # 1ᵉʳ étage : propriété (tenant) ; 2ᵉ étage : rôles scopés (memberships IAM).
    return GroupAccessPolicy(
        SqlOwnershipRepository(session), SqlAlchemyMembershipRepository(session)
    )


GroupAccessPolicyDep = Annotated[GroupAccessPolicy, Depends(get_group_access_policy)]


def get_create_group_command(
    access: GroupAccessPolicyDep, session: DbSession
) -> CreateGroup:
    return CreateGroup(
        SqlGroupRepository(session), access, clock=lambda: datetime.now(UTC)
    )


def get_add_group_member_command(
    access: GroupAccessPolicyDep, session: DbSession
) -> AddGroupMember:
    return AddGroupMember(
        SqlGroupRepository(session),
        SqlGroupMembershipRepository(session),
        SqlAlchemyMembershipRepository(session),
        access,
        EmitJoinedGroupFact(build_intake(session), build_absence_rhythm(session)),
        clock=lambda: datetime.now(UTC),
    )


def get_remove_group_member_command(
    access: GroupAccessPolicyDep, session: DbSession
) -> RemoveGroupMember:
    return RemoveGroupMember(
        SqlGroupRepository(session),
        SqlGroupMembershipRepository(session),
        access,
        clock=lambda: datetime.now(UTC),
    )


def get_list_group_members_query(
    access: GroupAccessPolicyDep, session: DbSession
) -> ListGroupMembers:
    return ListGroupMembers(
        SqlGroupRepository(session), SqlGroupMembershipRepository(session), access
    )


def get_appoint_group_leadership_command(
    access: GroupAccessPolicyDep, session: DbSession
) -> AppointGroupLeadership:
    return AppointGroupLeadership(
        SqlGroupRepository(session),
        SqlAlchemyMembershipRepository(session),
        SqlChurchRoleStore(session),
        access,
        clock=lambda: datetime.now(UTC),
    )


def get_multiply_cell_command(
    access: GroupAccessPolicyDep, session: DbSession
) -> MultiplyCell:
    return MultiplyCell(
        SqlGroupRepository(session),
        SqlGroupMembershipRepository(session),
        SqlAlchemyMembershipRepository(session),
        SqlChurchRoleStore(session),
        access,
        clock=lambda: datetime.now(UTC),
    )


def get_cell_report_query(
    access: GroupAccessPolicyDep, session: DbSession
) -> GetCellReport:
    return GetCellReport(
        SqlGroupRepository(session), SqlGroupMembershipRepository(session), access
    )


def get_modify_group_command(access: GroupAccessPolicyDep, session: DbSession) -> ModifyGroup:
    return ModifyGroup(SqlGroupRepository(session), access)


def get_close_group_command(access: GroupAccessPolicyDep, session: DbSession) -> CloseGroup:
    return CloseGroup(
        SqlGroupRepository(session),
        SqlGroupMembershipRepository(session),
        SqlChurchRoleStore(session),
        access,
        clock=lambda: datetime.now(UTC),
    )


def get_revoke_group_leadership_command(
    access: GroupAccessPolicyDep, session: DbSession
) -> RevokeGroupLeadership:
    return RevokeGroupLeadership(
        SqlGroupRepository(session),
        SqlAlchemyMembershipRepository(session),
        SqlChurchRoleStore(session),
        access,
        clock=lambda: datetime.now(UTC),
    )


_code_generator = SecureInvitationCodeGenerator()  # sans état → instance unique


def get_invitation_code_generator() -> InvitationCodeGenerator:
    return _code_generator


InvitationCodeGeneratorDep = Annotated[
    InvitationCodeGenerator, Depends(get_invitation_code_generator)
]


def get_create_group_invitation_command(
    access: GroupAccessPolicyDep, codes: InvitationCodeGeneratorDep, session: DbSession
) -> CreateGroupInvitation:
    return CreateGroupInvitation(
        SqlGroupRepository(session),
        SqlGroupInvitationRepository(session),
        codes,
        access,
        clock=lambda: datetime.now(UTC),
    )


def get_revoke_group_invitation_command(
    access: GroupAccessPolicyDep, session: DbSession
) -> RevokeGroupInvitation:
    return RevokeGroupInvitation(
        SqlGroupRepository(session),
        SqlGroupInvitationRepository(session),
        access,
        clock=lambda: datetime.now(UTC),
    )


def get_join_group_by_code_command(session: DbSession) -> JoinGroupByCode:
    return JoinGroupByCode(
        SqlGroupRepository(session),
        SqlGroupInvitationRepository(session),
        SqlGroupMembershipRepository(session),
        SqlAlchemyMembershipRepository(session),
        SqlChurchEnrollmentStore(session),
        clock=lambda: datetime.now(UTC),
    )


def get_leave_group_command(session: DbSession) -> LeaveGroup:
    return LeaveGroup(SqlGroupMembershipRepository(session), clock=lambda: datetime.now(UTC))


def get_promote_group_to_church_command(
    session: DbSession, settings: SettingsDep
) -> PromoteGroupToChurch:
    return PromoteGroupToChurch(
        SqlGroupRepository(session),
        SqlGroupMembershipRepository(session),
        SqlAlchemyMembershipRepository(session),
        SqlChurchPlantStore(session),
        platform_account_id=settings.platform_account_id,
        clock=lambda: datetime.now(UTC),
    )


CreateGroupDep = Annotated[CreateGroup, Depends(get_create_group_command)]
AddGroupMemberDep = Annotated[AddGroupMember, Depends(get_add_group_member_command)]
RemoveGroupMemberDep = Annotated[RemoveGroupMember, Depends(get_remove_group_member_command)]
ListGroupMembersDep = Annotated[ListGroupMembers, Depends(get_list_group_members_query)]
AppointGroupLeadershipDep = Annotated[
    AppointGroupLeadership, Depends(get_appoint_group_leadership_command)
]
MultiplyCellDep = Annotated[MultiplyCell, Depends(get_multiply_cell_command)]
GetCellReportDep = Annotated[GetCellReport, Depends(get_cell_report_query)]
ModifyGroupDep = Annotated[ModifyGroup, Depends(get_modify_group_command)]
CloseGroupDep = Annotated[CloseGroup, Depends(get_close_group_command)]
RevokeGroupLeadershipDep = Annotated[
    RevokeGroupLeadership, Depends(get_revoke_group_leadership_command)
]
PromoteGroupToChurchDep = Annotated[
    PromoteGroupToChurch, Depends(get_promote_group_to_church_command)
]
CreateGroupInvitationDep = Annotated[
    CreateGroupInvitation, Depends(get_create_group_invitation_command)
]
RevokeGroupInvitationDep = Annotated[
    RevokeGroupInvitation, Depends(get_revoke_group_invitation_command)
]
JoinGroupByCodeDep = Annotated[JoinGroupByCode, Depends(get_join_group_by_code_command)]
LeaveGroupDep = Annotated[LeaveGroup, Depends(get_leave_group_command)]
