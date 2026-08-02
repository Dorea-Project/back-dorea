"""Injection de dépendances du module Event."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends

from app.api.deps import DbSession
from app.contexts.events.application.commands.engage_event import (
    ConfirmParticipation,
    ReactToEvent,
    WithdrawParticipation,
)
from app.contexts.events.application.commands.moderation import (
    ReportEvent,
    TakeDownEvent,
)
from app.contexts.events.application.commands.publish_event import (
    CancelEvent,
    PublishEvent,
)
from app.contexts.events.application.commands.record_view import RecordEventView
from app.contexts.events.application.queries.event_stats import GetEventStats
from app.contexts.events.application.queries.reported_events import ListReportedEvents
from app.contexts.events.application.queries.view_events import (
    GetEvent,
    GetPublicEvent,
    ListParticipants,
    ListVisibleEvents,
)
from app.contexts.events.infrastructure.audience_adapter import IamTenantAudienceAdapter
from app.contexts.events.infrastructure.business_adapter import BillingBusinessTierAdapter
from app.contexts.events.infrastructure.persistence.repositories import (
    SqlEventParticipantRepository,
    SqlEventReactionRepository,
    SqlEventReportRepository,
    SqlEventRepository,
    SqlEventViewRepository,
)
from app.contexts.groups.interface.dependencies import GroupAccessPolicyDep
from app.contexts.iam.infrastructure.persistence.repositories import (
    SqlAlchemyMembershipRepository,
)
from app.contexts.notifications.interface.dependencies import build_notifier, build_scheduler


def _now() -> datetime:
    return datetime.now(UTC)


def get_publish_command(session: DbSession, access: GroupAccessPolicyDep) -> PublishEvent:
    return PublishEvent(
        SqlEventRepository(session),
        SqlAlchemyMembershipRepository(session),
        BillingBusinessTierAdapter(session),
        access,
        IamTenantAudienceAdapter(session),
        build_notifier(session),
        build_scheduler(session),
        clock=_now,
    )


def get_cancel_command(session: DbSession) -> CancelEvent:
    return CancelEvent(
        SqlEventRepository(session),
        SqlEventParticipantRepository(session),
        build_notifier(session),
        clock=_now,
    )


def get_react_command(session: DbSession) -> ReactToEvent:
    return ReactToEvent(
        SqlEventRepository(session),
        SqlEventReactionRepository(session),
        SqlAlchemyMembershipRepository(session),
        clock=_now,
    )


def get_confirm_command(session: DbSession) -> ConfirmParticipation:
    return ConfirmParticipation(
        SqlEventRepository(session),
        SqlEventParticipantRepository(session),
        SqlAlchemyMembershipRepository(session),
        build_notifier(session),
        # L'outbox : le rappel est posé à la confirmation et part la veille, hors requête.
        build_scheduler(session),
        clock=_now,
    )


def get_withdraw_command(session: DbSession) -> WithdrawParticipation:
    return WithdrawParticipation(SqlEventParticipantRepository(session))


def get_public_event_query(session: DbSession) -> GetPublicEvent:
    """La carte publique : aucun annuaire, aucune appartenance — le lien suffit."""
    return GetPublicEvent(SqlEventRepository(session))


def get_feed_query(session: DbSession) -> ListVisibleEvents:
    # Le fil qui m'atteint : mon église + ma dénomination + la plateforme.
    return ListVisibleEvents(
        SqlEventRepository(session),
        SqlEventParticipantRepository(session),
        SqlEventReactionRepository(session),
        IamTenantAudienceAdapter(session),
        SqlAlchemyMembershipRepository(session),
        clock=_now,  # sans elle, le fil rouvrirait sur les événements terminés
    )


def get_event_query(session: DbSession) -> GetEvent:
    return GetEvent(
        SqlEventRepository(session),
        SqlEventParticipantRepository(session),
        SqlEventReactionRepository(session),
        IamTenantAudienceAdapter(session),
        SqlAlchemyMembershipRepository(session),
    )


def get_participants_query(session: DbSession) -> ListParticipants:
    return ListParticipants(
        SqlEventRepository(session), SqlEventParticipantRepository(session)
    )


def get_record_view_command(session: DbSession) -> RecordEventView:
    return RecordEventView(
        SqlEventRepository(session),
        SqlEventViewRepository(session),
        SqlAlchemyMembershipRepository(session),
        IamTenantAudienceAdapter(session),
        clock=_now,
    )


def get_report_command(session: DbSession) -> ReportEvent:
    return ReportEvent(
        SqlEventRepository(session),
        SqlEventReportRepository(session),
        SqlAlchemyMembershipRepository(session),
        clock=_now,
    )


def get_takedown_command(session: DbSession) -> TakeDownEvent:
    return TakeDownEvent(SqlEventRepository(session), build_notifier(session), clock=_now)


def get_reported_query(session: DbSession) -> ListReportedEvents:
    return ListReportedEvents(SqlEventRepository(session), SqlEventReportRepository(session))


def get_stats_query(session: DbSession) -> GetEventStats:
    return GetEventStats(
        SqlEventRepository(session),
        SqlEventViewRepository(session),
        SqlEventParticipantRepository(session),
        SqlEventReactionRepository(session),
        IamTenantAudienceAdapter(session),
    )


PublishEventDep = Annotated[PublishEvent, Depends(get_publish_command)]
CancelEventDep = Annotated[CancelEvent, Depends(get_cancel_command)]
ReactToEventDep = Annotated[ReactToEvent, Depends(get_react_command)]
ConfirmParticipationDep = Annotated[ConfirmParticipation, Depends(get_confirm_command)]
WithdrawParticipationDep = Annotated[WithdrawParticipation, Depends(get_withdraw_command)]
ListVisibleEventsDep = Annotated[ListVisibleEvents, Depends(get_feed_query)]
GetEventDep = Annotated[GetEvent, Depends(get_event_query)]
GetPublicEventDep = Annotated[GetPublicEvent, Depends(get_public_event_query)]
ListParticipantsDep = Annotated[ListParticipants, Depends(get_participants_query)]
RecordEventViewDep = Annotated[RecordEventView, Depends(get_record_view_command)]
GetEventStatsDep = Annotated[GetEventStats, Depends(get_stats_query)]
ReportEventDep = Annotated[ReportEvent, Depends(get_report_command)]
TakeDownEventDep = Annotated[TakeDownEvent, Depends(get_takedown_command)]
ListReportedEventsDep = Annotated[ListReportedEvents, Depends(get_reported_query)]
