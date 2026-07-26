"""Injection de dépendances du contexte Annonces (M8)."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends

from app.api.deps import DbSession, SettingsDep
from app.contexts.announcements.application.commands.archive_announcement import (
    ArchiveAnnouncement,
)
from app.contexts.announcements.application.commands.decide_consent import DecideSubjectConsent
from app.contexts.announcements.application.commands.engage_announcement import (
    EngageAnnouncement,
    WithdrawEngagement,
)
from app.contexts.announcements.application.commands.publish_announcement import (
    PublishAnnouncement,
    PublishPlatformAnnouncement,
)
from app.contexts.announcements.application.commands.react_to_announcement import (
    RemoveReaction,
    SetReaction,
)
from app.contexts.announcements.application.queries.get_consolation import GetConsolation
from app.contexts.announcements.application.queries.list_church_announcements import (
    ListChurchAnnouncements,
)
from app.contexts.announcements.application.queries.list_my_announcements import (
    ListMyAnnouncements,
)
from app.contexts.announcements.application.queries.list_responders import ListResponders
from app.contexts.announcements.application.watch_effects import EmitAnnouncementFacts
from app.contexts.announcements.infrastructure.audience_adapter import GroupAudienceAdapter
from app.contexts.announcements.infrastructure.member_directory_adapter import (
    IamMemberDirectoryAdapter,
)
from app.contexts.announcements.infrastructure.persistence.repositories import (
    SqlAnnouncementEngagementRepository,
    SqlAnnouncementReactionRepository,
    SqlAnnouncementRepository,
    SqlAnnouncementSubjectRepository,
)
from app.contexts.announcements.infrastructure.rsvp_adapter import AttendanceRsvpAdapter
from app.contexts.attendance.infrastructure.persistence.rsvp_repository import (
    SqlGatheringRsvpRepository,
)
from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.groups.infrastructure.persistence.repositories import (
    SqlGroupMembershipRepository,
    SqlGroupRepository,
)
from app.contexts.iam.infrastructure.persistence.repositories import SqlAlchemyMembershipRepository
from app.contexts.notifications.interface.dependencies import build_notifier, build_scheduler
from app.contexts.tenant.infrastructure.persistence.ownership_repo import SqlOwnershipRepository
from app.contexts.watch.interface.dependencies import build_intake


def _access(session) -> GroupAccessPolicy:
    return GroupAccessPolicy(
        SqlOwnershipRepository(session), SqlAlchemyMembershipRepository(session)
    )


def _audience(session) -> GroupAudienceAdapter:
    return GroupAudienceAdapter(
        SqlGroupMembershipRepository(session), SqlGroupRepository(session)
    )


def _now() -> datetime:
    return datetime.now(UTC)


def _watch_effects(session) -> EmitAnnouncementFacts:
    """L'annonce est une **source** du moteur : elle émet un fait, elle n'écrit rien."""
    return EmitAnnouncementFacts(build_intake(session), clock=_now)


def get_publish_announcement_command(session: DbSession) -> PublishAnnouncement:
    return PublishAnnouncement(
        SqlAnnouncementRepository(session), SqlGroupRepository(session), _access(session),
        IamMemberDirectoryAdapter(session), build_notifier(session), build_scheduler(session),
        SqlAnnouncementSubjectRepository(session), _watch_effects(session),
        clock=_now,
    )


def get_decide_consent_command(session: DbSession) -> DecideSubjectConsent:
    return DecideSubjectConsent(
        SqlAnnouncementRepository(session),
        SqlAnnouncementSubjectRepository(session),
        _watch_effects(session),
        clock=_now,
    )


def get_publish_platform_command(
    session: DbSession, settings: SettingsDep
) -> PublishPlatformAnnouncement:
    return PublishPlatformAnnouncement(
        SqlAnnouncementRepository(session),
        platform_account_id=settings.platform_account_id,
        clock=_now,
    )


def _rsvp(session) -> AttendanceRsvpAdapter:
    return AttendanceRsvpAdapter(SqlGatheringRsvpRepository(session))


def get_engage_command(session: DbSession) -> EngageAnnouncement:
    return EngageAnnouncement(
        SqlAnnouncementRepository(session),
        SqlAnnouncementEngagementRepository(session),
        _audience(session),
        clock=_now,
        rsvp=_rsvp(session),  # « je viens » → présence attendue M6
    )


def get_withdraw_command(session: DbSession) -> WithdrawEngagement:
    return WithdrawEngagement(
        SqlAnnouncementRepository(session),
        SqlAnnouncementEngagementRepository(session),
        rsvp=_rsvp(session),
    )


def get_set_reaction_command(session: DbSession) -> SetReaction:
    return SetReaction(
        SqlAnnouncementRepository(session),
        SqlAnnouncementReactionRepository(session),
        _audience(session),
        clock=_now,
    )


def get_remove_reaction_command(session: DbSession) -> RemoveReaction:
    return RemoveReaction(
        SqlAnnouncementRepository(session), SqlAnnouncementReactionRepository(session)
    )


def get_archive_command(session: DbSession) -> ArchiveAnnouncement:
    return ArchiveAnnouncement(
        SqlAnnouncementRepository(session), SqlGroupRepository(session), _access(session)
    )


def get_my_announcements_query(session: DbSession) -> ListMyAnnouncements:
    return ListMyAnnouncements(
        SqlAnnouncementRepository(session),
        SqlAnnouncementEngagementRepository(session),
        SqlAnnouncementReactionRepository(session),
        _audience(session),
        SqlAlchemyMembershipRepository(session),
        clock=_now,
    )


def get_consolation_query(session: DbSession) -> GetConsolation:
    return GetConsolation(
        SqlAnnouncementRepository(session),
        SqlAnnouncementReactionRepository(session),
        SqlAnnouncementEngagementRepository(session),
        _access(session),
    )


def get_responders_query(session: DbSession) -> ListResponders:
    return ListResponders(
        SqlAnnouncementRepository(session),
        SqlAnnouncementEngagementRepository(session),
        SqlGroupRepository(session),
        _access(session),
    )


def get_church_announcements_query(session: DbSession) -> ListChurchAnnouncements:
    return ListChurchAnnouncements(
        SqlAnnouncementRepository(session),
        SqlAnnouncementEngagementRepository(session),
        SqlAnnouncementReactionRepository(session),
        _access(session),
    )


PublishAnnouncementDep = Annotated[
    PublishAnnouncement, Depends(get_publish_announcement_command)
]
PublishPlatformDep = Annotated[
    PublishPlatformAnnouncement, Depends(get_publish_platform_command)
]
DecideConsentDep = Annotated[DecideSubjectConsent, Depends(get_decide_consent_command)]
EngageAnnouncementDep = Annotated[EngageAnnouncement, Depends(get_engage_command)]
WithdrawEngagementDep = Annotated[WithdrawEngagement, Depends(get_withdraw_command)]
SetReactionDep = Annotated[SetReaction, Depends(get_set_reaction_command)]
RemoveReactionDep = Annotated[RemoveReaction, Depends(get_remove_reaction_command)]
ArchiveAnnouncementDep = Annotated[ArchiveAnnouncement, Depends(get_archive_command)]
ListMyAnnouncementsDep = Annotated[ListMyAnnouncements, Depends(get_my_announcements_query)]
ListRespondersDep = Annotated[ListResponders, Depends(get_responders_query)]
GetConsolationDep = Annotated[GetConsolation, Depends(get_consolation_query)]
ListChurchAnnouncementsDep = Annotated[
    ListChurchAnnouncements, Depends(get_church_announcements_query)
]
