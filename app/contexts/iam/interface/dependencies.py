"""Injection de dépendances du contexte IAM — câble dépôts et use cases.

L'acteur authentifié (`CurrentActor`) est fourni par le contexte Auth (M2), qui
est responsable de l'authentification.
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends

from app.api.deps import DbSession
from app.contexts.groups.infrastructure.member_roster_adapter import GroupRosterAdapter
from app.contexts.groups.infrastructure.persistence.repositories import (
    SqlGroupMembershipRepository,
)
from app.contexts.iam.application.access_control import AccessControl
from app.contexts.iam.application.birthdays import BirthdaysToday, SetMyBirthday
from app.contexts.iam.application.commands.bulk_enroll_members import BulkEnrollMembers
from app.contexts.iam.application.commands.church_invitation import (
    CreateChurchInvitation,
    JoinChurchByCode,
    RevokeChurchInvitation,
)
from app.contexts.iam.application.commands.close_membership import CloseMembership
from app.contexts.iam.application.commands.enroll_invited_member import EnrollInvitedMember
from app.contexts.iam.application.commands.enroll_member import EnrollMember
from app.contexts.iam.application.commands.revoke_role import RevokeRole
from app.contexts.iam.application.commands.transfer_member import (
    AcceptTransfer,
    CancelTransfer,
    DeclineTransfer,
    RequestTransfer,
)
from app.contexts.iam.application.commands.transition_status import TransitionStatus
from app.contexts.iam.application.queries.check_permission import CheckPermission
from app.contexts.iam.application.queries.get_membership_status import GetMembershipStatus
from app.contexts.iam.application.queries.get_my_memberships import GetMyMemberships
from app.contexts.iam.application.queries.get_my_profile import GetMyProfile
from app.contexts.iam.application.queries.is_confirmed_member import IsConfirmedMember
from app.contexts.iam.application.queries.list_transfers import ListTransfers
from app.contexts.iam.domain.repositories import AccountRepository, MembershipRepository
from app.contexts.iam.infrastructure.code_generator import SecureInvitationCodeGenerator
from app.contexts.iam.infrastructure.persistence.birthday_directory import (
    SqlBirthdayDirectory,
    SqlBirthdayStore,
)
from app.contexts.iam.infrastructure.persistence.church_invitation_repository import (
    SqlChurchInvitationRepository,
)
from app.contexts.iam.infrastructure.persistence.enrollment import SqlMemberEnrollmentStore
from app.contexts.iam.infrastructure.persistence.lifecycle import SqlMembershipLifecycleStore
from app.contexts.iam.infrastructure.persistence.profile_reader import SqlProfileReader
from app.contexts.iam.infrastructure.persistence.repositories import (
    SqlAlchemyAccountRepository,
    SqlAlchemyMembershipRepository,
)
from app.contexts.iam.infrastructure.persistence.transfer_repository import (
    SqlMemberTransferRepository,
)
from app.contexts.iam.infrastructure.persistence.transitions import SqlMembershipTransitionStore
from app.contexts.tenant.infrastructure.persistence.ownership_repo import SqlOwnershipRepository


def get_membership_repository(session: DbSession) -> MembershipRepository:
    return SqlAlchemyMembershipRepository(session)


MembershipRepositoryDep = Annotated[MembershipRepository, Depends(get_membership_repository)]


def get_account_repository(session: DbSession) -> AccountRepository:
    return SqlAlchemyAccountRepository(session)


AccountRepositoryDep = Annotated[AccountRepository, Depends(get_account_repository)]


def get_access_control(memberships: MembershipRepositoryDep, session: DbSession) -> AccessControl:
    # 1ᵉʳ étage : propriété (ownership) ; 2ᵉ étage : rôles (memberships).
    return AccessControl(SqlOwnershipRepository(session), memberships)


AccessControlDep = Annotated[AccessControl, Depends(get_access_control)]


def get_enroll_member_command(
    accounts: AccountRepositoryDep,
    memberships: MembershipRepositoryDep,
    access: AccessControlDep,
    session: DbSession,
) -> EnrollMember:
    return EnrollMember(
        accounts,
        memberships,
        SqlMemberEnrollmentStore(session),
        access,
        clock=lambda: datetime.now(UTC),
    )


EnrollMemberDep = Annotated[EnrollMember, Depends(get_enroll_member_command)]


def get_enroll_invited_member_command(
    accounts: AccountRepositoryDep,
    memberships: MembershipRepositoryDep,
    access: AccessControlDep,
    session: DbSession,
) -> EnrollInvitedMember:
    return EnrollInvitedMember(
        accounts,
        memberships,
        SqlMemberEnrollmentStore(session),
        access,
        clock=lambda: datetime.now(UTC),
    )


EnrollInvitedMemberDep = Annotated[
    EnrollInvitedMember, Depends(get_enroll_invited_member_command)
]


def get_bulk_enroll_command(
    accounts: AccountRepositoryDep,
    memberships: MembershipRepositoryDep,
    access: AccessControlDep,
    session: DbSession,
) -> BulkEnrollMembers:
    return BulkEnrollMembers(
        accounts,
        memberships,
        SqlMemberEnrollmentStore(session),
        access,
        clock=lambda: datetime.now(UTC),
    )


BulkEnrollDep = Annotated[BulkEnrollMembers, Depends(get_bulk_enroll_command)]


def get_transition_status_command(
    memberships: MembershipRepositoryDep, access: AccessControlDep, session: DbSession
) -> TransitionStatus:
    return TransitionStatus(
        memberships,
        SqlMembershipTransitionStore(session),
        access,
        clock=lambda: datetime.now(UTC),
    )


TransitionStatusDep = Annotated[TransitionStatus, Depends(get_transition_status_command)]


def get_revoke_role_command(
    memberships: MembershipRepositoryDep, access: AccessControlDep, session: DbSession
) -> RevokeRole:
    return RevokeRole(
        memberships,
        SqlMembershipLifecycleStore(session),
        access,
        clock=lambda: datetime.now(UTC),
    )


RevokeRoleDep = Annotated[RevokeRole, Depends(get_revoke_role_command)]


def get_close_membership_command(
    memberships: MembershipRepositoryDep, access: AccessControlDep, session: DbSession
) -> CloseMembership:
    return CloseMembership(
        memberships,
        SqlMembershipLifecycleStore(session),
        access,
        clock=lambda: datetime.now(UTC),
    )


CloseMembershipDep = Annotated[CloseMembership, Depends(get_close_membership_command)]


_invitation_codes = SecureInvitationCodeGenerator()  # sans état → instance unique


def get_create_church_invitation_command(
    access: AccessControlDep, session: DbSession
) -> CreateChurchInvitation:
    return CreateChurchInvitation(
        SqlChurchInvitationRepository(session), _invitation_codes, access,
        clock=lambda: datetime.now(UTC),
    )


def get_revoke_church_invitation_command(
    access: AccessControlDep, session: DbSession
) -> RevokeChurchInvitation:
    return RevokeChurchInvitation(
        SqlChurchInvitationRepository(session), access, clock=lambda: datetime.now(UTC)
    )


def get_join_church_command(
    memberships: MembershipRepositoryDep, session: DbSession
) -> JoinChurchByCode:
    return JoinChurchByCode(
        SqlChurchInvitationRepository(session),
        memberships,
        SqlMemberEnrollmentStore(session),
        clock=lambda: datetime.now(UTC),
    )


CreateChurchInvitationDep = Annotated[
    CreateChurchInvitation, Depends(get_create_church_invitation_command)
]
RevokeChurchInvitationDep = Annotated[
    RevokeChurchInvitation, Depends(get_revoke_church_invitation_command)
]
JoinChurchByCodeDep = Annotated[JoinChurchByCode, Depends(get_join_church_command)]


def get_request_transfer_command(
    memberships: MembershipRepositoryDep, access: AccessControlDep, session: DbSession
) -> RequestTransfer:
    return RequestTransfer(
        SqlMemberTransferRepository(session),
        memberships,
        access,
        clock=lambda: datetime.now(UTC),
    )


def get_accept_transfer_command(
    memberships: MembershipRepositoryDep, access: AccessControlDep, session: DbSession
) -> AcceptTransfer:
    return AcceptTransfer(
        SqlMemberTransferRepository(session),
        memberships,
        SqlMembershipLifecycleStore(session),
        SqlMemberEnrollmentStore(session),
        SqlMembershipTransitionStore(session),
        GroupRosterAdapter(SqlGroupMembershipRepository(session)),
        access,
        clock=lambda: datetime.now(UTC),
    )


def get_decline_transfer_command(
    access: AccessControlDep, session: DbSession
) -> DeclineTransfer:
    return DeclineTransfer(
        SqlMemberTransferRepository(session), access, clock=lambda: datetime.now(UTC)
    )


def get_cancel_transfer_command(access: AccessControlDep, session: DbSession) -> CancelTransfer:
    return CancelTransfer(
        SqlMemberTransferRepository(session), access, clock=lambda: datetime.now(UTC)
    )


def get_list_transfers_query(access: AccessControlDep, session: DbSession) -> ListTransfers:
    return ListTransfers(SqlMemberTransferRepository(session), access)


RequestTransferDep = Annotated[RequestTransfer, Depends(get_request_transfer_command)]
AcceptTransferDep = Annotated[AcceptTransfer, Depends(get_accept_transfer_command)]
DeclineTransferDep = Annotated[DeclineTransfer, Depends(get_decline_transfer_command)]
CancelTransferDep = Annotated[CancelTransfer, Depends(get_cancel_transfer_command)]
ListTransfersDep = Annotated[ListTransfers, Depends(get_list_transfers_query)]


def get_membership_status_query(
    repo: MembershipRepositoryDep, session: DbSession
) -> GetMembershipStatus:
    return GetMembershipStatus(repo, SqlOwnershipRepository(session))


def get_my_memberships_query(
    repo: MembershipRepositoryDep, session: DbSession
) -> GetMyMemberships:
    return GetMyMemberships(repo, SqlOwnershipRepository(session))


def get_my_profile_query(repo: MembershipRepositoryDep, session: DbSession) -> GetMyProfile:
    """Réutilise `GetMyMemberships` au lieu de relire les appartenances : une seconde
    définition de « mes églises » aurait divergé de la première."""
    return GetMyProfile(
        SqlProfileReader(session), GetMyMemberships(repo, SqlOwnershipRepository(session))
    )


def get_is_confirmed_member_query(repo: MembershipRepositoryDep) -> IsConfirmedMember:
    return IsConfirmedMember(repo)


def get_check_permission_query(repo: MembershipRepositoryDep) -> CheckPermission:
    return CheckPermission(repo)


def get_set_my_birthday_command(session: DbSession) -> SetMyBirthday:
    return SetMyBirthday(SqlBirthdayStore(session))


def get_birthdays_today_query(session: DbSession) -> BirthdaysToday:
    """L'encart se **calcule à la lecture** : pas d'échéance, pas de worker, pas de push."""
    return BirthdaysToday(
        SqlBirthdayDirectory(session), clock=lambda: datetime.now(UTC)
    )


SetMyBirthdayDep = Annotated[SetMyBirthday, Depends(get_set_my_birthday_command)]
BirthdaysTodayDep = Annotated[BirthdaysToday, Depends(get_birthdays_today_query)]

GetMembershipStatusDep = Annotated[GetMembershipStatus, Depends(get_membership_status_query)]
GetMyMembershipsDep = Annotated[GetMyMemberships, Depends(get_my_memberships_query)]
GetMyProfileDep = Annotated[GetMyProfile, Depends(get_my_profile_query)]
IsConfirmedMemberDep = Annotated[IsConfirmedMember, Depends(get_is_confirmed_member_query)]
CheckPermissionDep = Annotated[CheckPermission, Depends(get_check_permission_query)]
