"""Schémas HTTP du module Event."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.contexts.events.application.dtos import (
    EventDTO,
    EventStatsDTO,
    ParticipantDTO,
    ReportedEventDTO,
)
from app.contexts.events.domain.enums import EventCategory, EventReaction, EventScope


class PublishEventBody(BaseModel):
    category: EventCategory = Field(default=EventCategory.OTHER)
    title: str = Field(examples=["Grande veillée de prière"])
    starts_at: datetime
    scope: EventScope = Field(
        default=EventScope.CHURCH,
        description="church (gratuit). denomination/platform : compte Business (à venir)",
    )
    description: str | None = Field(default=None)
    ends_at: datetime | None = Field(default=None)
    place_label: str | None = Field(default=None, examples=["Temple central, Yopougon"])
    latitude: float | None = Field(default=None)
    longitude: float | None = Field(default=None)
    media_urls: list[str] | None = Field(default=None, description="Affiche(s) de l'événement")


class ReactEventBody(BaseModel):
    kind: EventReaction = Field(description="interested | blessed | pray")


class EventView(BaseModel):
    id: UUID
    author_account_id: UUID
    category: str
    title: str
    description: str | None
    starts_at: datetime
    ends_at: datetime | None
    place_label: str | None
    latitude: float | None
    longitude: float | None
    media_urls: list[str]
    scope: str
    status: str
    # `None` = non divulgué : sans capacité, un nombre nu est un score. L'organisateur le lit
    # dans `/stats`.
    participant_count: int | None
    my_reaction: str | None
    i_confirmed: bool

    @classmethod
    def from_dto(cls, d: EventDTO) -> EventView:
        return cls(
            id=d.id,
            author_account_id=d.author_account_id,
            category=d.category,
            title=d.title,
            description=d.description,
            starts_at=d.starts_at,
            ends_at=d.ends_at,
            place_label=d.place_label,
            latitude=d.latitude,
            longitude=d.longitude,
            media_urls=d.media_urls,
            scope=d.scope,
            status=d.status,
            participant_count=d.participant_count,
            my_reaction=d.my_reaction,
            i_confirmed=d.i_confirmed,
        )


class EventFeedView(BaseModel):
    total: int
    events: list[EventView]

    @classmethod
    def from_dtos(cls, dtos: list[EventDTO]) -> EventFeedView:
        return cls(total=len(dtos), events=[EventView.from_dto(d) for d in dtos])


class EventStatsView(BaseModel):
    reach: int
    views_total: int
    views_by_denomination: dict[str, int]
    interested_count: int
    confirmed_count: int
    reaction_counts: dict[str, int]

    @classmethod
    def from_dto(cls, d: EventStatsDTO) -> EventStatsView:
        return cls(
            reach=d.reach,
            views_total=d.views_total,
            views_by_denomination=d.views_by_denomination,
            interested_count=d.interested_count,
            confirmed_count=d.confirmed_count,
            reaction_counts=d.reaction_counts,
        )


class ReportEventBody(BaseModel):
    reason: str | None = Field(default=None, description="Pourquoi ce signalement")


class TakeDownEventBody(BaseModel):
    reason: str | None = Field(default=None, description="Le motif du retrait")


class ReportedEventView(BaseModel):
    id: UUID
    tenant_id: UUID
    author_account_id: UUID
    title: str
    scope: str
    status: str
    starts_at: datetime
    report_count: int

    @classmethod
    def from_dto(cls, d: ReportedEventDTO) -> ReportedEventView:
        return cls(
            id=d.id,
            tenant_id=d.tenant_id,
            author_account_id=d.author_account_id,
            title=d.title,
            scope=d.scope,
            status=d.status,
            starts_at=d.starts_at,
            report_count=d.report_count,
        )


class ReportedEventListView(BaseModel):
    total: int
    events: list[ReportedEventView]

    @classmethod
    def from_dtos(cls, dtos: list[ReportedEventDTO]) -> ReportedEventListView:
        return cls(total=len(dtos), events=[ReportedEventView.from_dto(d) for d in dtos])


class _Participant(BaseModel):
    account_id: UUID
    confirmed_at: datetime


class ParticipantListView(BaseModel):
    total: int
    participants: list[_Participant]

    @classmethod
    def from_dtos(cls, dtos: list[ParticipantDTO]) -> ParticipantListView:
        return cls(
            total=len(dtos),
            participants=[
                _Participant(account_id=p.account_id, confirmed_at=p.confirmed_at) for p in dtos
            ],
        )
