"""Modèles ORM du module Event (le backend possède le schéma ; enums en String)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class EventModel(Base):
    __tablename__ = "events"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    author_account_id: Mapped[UUID] = mapped_column(Uuid)
    category: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    place_label: Mapped[str | None] = mapped_column(String, nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    media_urls: Mapped[list[str]] = mapped_column(JSON, default=list)
    scope: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    moderation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    taken_down_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EventParticipantModel(Base):
    __tablename__ = "event_participants"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    event_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("events.id"))
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    account_id: Mapped[UUID] = mapped_column(Uuid)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EventReactionModel(Base):
    __tablename__ = "event_reactions"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    event_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("events.id"))
    account_id: Mapped[UUID] = mapped_column(Uuid)
    kind: Mapped[str] = mapped_column(String)
    reacted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EventViewModel(Base):
    __tablename__ = "event_views"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    event_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("events.id"))
    viewer_account_id: Mapped[UUID] = mapped_column(Uuid)
    denomination: Mapped[str | None] = mapped_column(String, nullable=True)
    viewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EventReportModel(Base):
    __tablename__ = "event_reports"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    event_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("events.id"))
    reporter_account_id: Mapped[UUID] = mapped_column(Uuid)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
