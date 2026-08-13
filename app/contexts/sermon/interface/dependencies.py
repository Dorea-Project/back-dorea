"""Injection de dépendances du module Sermon."""

from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.api.deps import DbSession
from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.iam.infrastructure.persistence.repositories import (
    SqlAlchemyMembershipRepository,
)
from app.contexts.sermon.application.commands.companion import (
    AdvanceCompanion,
    AnswerAttendance,
    StartCompanion,
)
from app.contexts.sermon.application.commands.deposit import DepositSermon
from app.contexts.sermon.application.commands.manage import ApproveSermon, PublishSermon
from app.contexts.sermon.application.ports import SermonDigester, SermonTextExtractor
from app.contexts.sermon.application.queries.list_sermons import GetSermon, ListTenantSermons
from app.contexts.sermon.infrastructure.capsule_feed import AnnouncementCapsuleFeedAdapter
from app.contexts.sermon.infrastructure.culte_attendance import SermonCulteAttendanceAdapter
from app.contexts.sermon.infrastructure.digester import build_sermon_digester
from app.contexts.sermon.infrastructure.extractor import build_text_extractor
from app.contexts.sermon.infrastructure.persistence.repository import (
    SqlCompanionSessionRepository,
    SqlSermonRepository,
)
from app.contexts.tenant.infrastructure.persistence.ownership_repo import SqlOwnershipRepository
from app.core.config import get_settings


def _now() -> datetime:
    return datetime.now(UTC)


def _access(session) -> GroupAccessPolicy:
    return GroupAccessPolicy(
        SqlOwnershipRepository(session), SqlAlchemyMembershipRepository(session)
    )


@lru_cache
def _digester() -> SermonDigester:
    # Un seul digesteur par configuration (Mistral réel ou repli déterministe) — construit une fois.
    return build_sermon_digester(get_settings())


@lru_cache
def _extractor() -> SermonTextExtractor:
    return build_text_extractor()


def get_deposit_command(session: DbSession) -> DepositSermon:
    return DepositSermon(
        SqlSermonRepository(session), _access(session), _digester(), _extractor(), clock=_now
    )


def get_approve_command(session: DbSession) -> ApproveSermon:
    return ApproveSermon(SqlSermonRepository(session), _access(session), clock=_now)


def get_publish_command(session: DbSession) -> PublishSermon:
    return PublishSermon(
        SqlSermonRepository(session),
        _access(session),
        AnnouncementCapsuleFeedAdapter(session),
        clock=_now,
    )


def get_list_query(session: DbSession) -> ListTenantSermons:
    return ListTenantSermons(SqlSermonRepository(session), _access(session))


def get_sermon_query(session: DbSession) -> GetSermon:
    return GetSermon(SqlSermonRepository(session), _access(session))


# --- Le compagnon (mobile, membre) ---


def get_start_companion(session: DbSession) -> StartCompanion:
    return StartCompanion(
        SqlCompanionSessionRepository(session),
        SqlSermonRepository(session),
        SqlAlchemyMembershipRepository(session),
        clock=_now,
    )


def get_answer_attendance(session: DbSession) -> AnswerAttendance:
    return AnswerAttendance(
        SqlCompanionSessionRepository(session),
        SqlSermonRepository(session),
        SermonCulteAttendanceAdapter(session),
        clock=_now,
    )


def get_advance_companion(session: DbSession) -> AdvanceCompanion:
    return AdvanceCompanion(
        SqlCompanionSessionRepository(session), SqlSermonRepository(session), clock=_now
    )


DepositSermonDep = Annotated[DepositSermon, Depends(get_deposit_command)]
ApproveSermonDep = Annotated[ApproveSermon, Depends(get_approve_command)]
PublishSermonDep = Annotated[PublishSermon, Depends(get_publish_command)]
ListTenantSermonsDep = Annotated[ListTenantSermons, Depends(get_list_query)]
GetSermonDep = Annotated[GetSermon, Depends(get_sermon_query)]
# R0 — `get_deposit_gratitude` vit désormais dans `watch/interface/dependencies.py`, avec la
# commande. L'alias déprécié de `mobile_router` en dépend directement : on ne recâble pas une
# seconde fois ce qui est déjà câblé chez lui.


StartCompanionDep = Annotated[StartCompanion, Depends(get_start_companion)]
AnswerAttendanceDep = Annotated[AnswerAttendance, Depends(get_answer_attendance)]
AdvanceCompanionDep = Annotated[AdvanceCompanion, Depends(get_advance_companion)]
