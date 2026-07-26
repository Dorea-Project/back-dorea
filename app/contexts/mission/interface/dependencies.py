"""Injection de dépendances du contexte Mission (M9)."""

from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.api.deps import DbSession
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
from app.contexts.media.application.media_store import MediaStore
from app.contexts.media.infrastructure.stores import build_media_store
from app.contexts.mission.application.commands.accompany import AccompanySeeker, CloseSeeker
from app.contexts.mission.application.commands.create_link import (
    CreateGroupLink,
    CreateMyLink,
    RevokeLink,
)
from app.contexts.mission.application.commands.engage_card import AcceptInvitation, ReactToCard
from app.contexts.mission.application.commands.generate_card import GenerateVerseCard
from app.contexts.mission.application.commands.integrate import IntegrateSeeker
from app.contexts.mission.application.ports import ScriptureSource, VerseResolver
from app.contexts.mission.application.queries.get_card import GetCard
from app.contexts.mission.application.queries.list_my_seekers import ListMySeekers
from app.contexts.mission.infrastructure.card_renderer import SvgCardRenderer
from app.contexts.mission.infrastructure.code_generator import SecureInvitationCodeGenerator
from app.contexts.mission.infrastructure.directory_adapter import DirectoryAdapter
from app.contexts.mission.infrastructure.persistence.repositories import (
    SqlMissionLinkRepository,
    SqlMissionReactionRepository,
    SqlSeekerRepository,
)
from app.contexts.mission.infrastructure.scripture_lsg import build_scripture_source
from app.contexts.mission.infrastructure.verse_resolver import build_verse_resolver
from app.contexts.notifications.interface.dependencies import build_notifier
from app.contexts.tenant.infrastructure.persistence.ownership_repo import SqlOwnershipRepository
from app.contexts.tenant.infrastructure.persistence.tenant_repo import SqlTenantRepository
from app.core.config import get_settings

_codes = SecureInvitationCodeGenerator()  # sans état → instance unique
_renderer = SvgCardRenderer()  # sans état → instance unique


def _now() -> datetime:
    return datetime.now(UTC)


# Bible, résolveur IA et stockage média : sans état, construits une fois selon la config.
@lru_cache
def _scripture() -> ScriptureSource:
    return build_scripture_source(get_settings())


@lru_cache
def _resolver() -> VerseResolver:
    return build_verse_resolver(get_settings(), _scripture())


@lru_cache
def _media() -> MediaStore:
    return build_media_store(get_settings())


def _access(session) -> GroupAccessPolicy:
    return GroupAccessPolicy(
        SqlOwnershipRepository(session), SqlAlchemyMembershipRepository(session)
    )


def get_create_my_link(session: DbSession) -> CreateMyLink:
    return CreateMyLink(
        SqlMissionLinkRepository(session),
        SqlAlchemyMembershipRepository(session),
        _codes,
        clock=_now,
    )


def get_create_group_link(session: DbSession) -> CreateGroupLink:
    return CreateGroupLink(
        SqlMissionLinkRepository(session),
        SqlGroupRepository(session),
        _access(session),
        _codes,
        clock=_now,
    )


def get_revoke_link(session: DbSession) -> RevokeLink:
    return RevokeLink(
        SqlMissionLinkRepository(session), SqlGroupRepository(session), _access(session),
        clock=_now,
    )


def get_react_command(session: DbSession) -> ReactToCard:
    return ReactToCard(
        SqlMissionLinkRepository(session), SqlMissionReactionRepository(session), clock=_now
    )


def get_accept_command(session: DbSession) -> AcceptInvitation:
    return AcceptInvitation(
        SqlMissionLinkRepository(session),
        SqlSeekerRepository(session),
        build_notifier(session),
        clock=_now,
    )


def get_card_query(session: DbSession) -> GetCard:
    directory = DirectoryAdapter(
        SqlAlchemyAccountRepository(session),
        SqlGroupRepository(session),
        SqlTenantRepository(session),
    )
    return GetCard(SqlMissionLinkRepository(session), directory, clock=_now)


def get_my_seekers_query(session: DbSession) -> ListMySeekers:
    return ListMySeekers(
        SqlMissionLinkRepository(session),
        SqlSeekerRepository(session),
        SqlMissionReactionRepository(session),
    )


def get_generate_card() -> GenerateVerseCard:
    # Sans base : IA (ou repli mots-clés) + Bible canonique + rendu + stockage média.
    return GenerateVerseCard(_resolver(), _scripture(), _renderer, _media())


def get_accompany_command(session: DbSession) -> AccompanySeeker:
    return AccompanySeeker(
        SqlSeekerRepository(session), SqlGroupRepository(session), _access(session), clock=_now
    )


def get_close_command(session: DbSession) -> CloseSeeker:
    return CloseSeeker(
        SqlSeekerRepository(session), SqlGroupRepository(session), _access(session), clock=_now
    )


def get_integrate_command(session: DbSession) -> IntegrateSeeker:
    # Réutilise la machinerie visiteur→membre : identité globale + enrôlement + roster.
    return IntegrateSeeker(
        SqlSeekerRepository(session),
        SqlAlchemyAccountRepository(session),
        SqlAlchemyMembershipRepository(session),
        SqlMemberEnrollmentStore(session),
        SqlGroupRepository(session),
        SqlGroupMembershipRepository(session),
        _access(session),
        clock=_now,
    )


CreateMyLinkDep = Annotated[CreateMyLink, Depends(get_create_my_link)]
CreateGroupLinkDep = Annotated[CreateGroupLink, Depends(get_create_group_link)]
RevokeLinkDep = Annotated[RevokeLink, Depends(get_revoke_link)]
ReactToCardDep = Annotated[ReactToCard, Depends(get_react_command)]
AcceptInvitationDep = Annotated[AcceptInvitation, Depends(get_accept_command)]
GetCardDep = Annotated[GetCard, Depends(get_card_query)]
ListMySeekersDep = Annotated[ListMySeekers, Depends(get_my_seekers_query)]
GenerateVerseCardDep = Annotated[GenerateVerseCard, Depends(get_generate_card)]
AccompanySeekerDep = Annotated[AccompanySeeker, Depends(get_accompany_command)]
CloseSeekerDep = Annotated[CloseSeeker, Depends(get_close_command)]
IntegrateSeekerDep = Annotated[IntegrateSeeker, Depends(get_integrate_command)]
