"""Modèles ORM du module Event (le backend possède le schéma ; enums en String)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class EventModel(Base):
    __tablename__ = "events"

    __table_args__ = (Index("ix_events_tenant_status", "tenant_id", "status"),)

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

    __table_args__ = (
        # **Une seule participation par personne.** La contrainte existait en base et pas ici :
        # la base de test, construite depuis ces modèles, ne l'avait donc jamais — et un
        # double-envoi concurrent aurait compté deux fois quelqu'un dans le tableau de bord.
        UniqueConstraint("event_id", "account_id", name="uq_event_participant"),
        Index("ix_event_participants_event", "event_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    event_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("events.id"))
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    account_id: Mapped[UUID] = mapped_column(Uuid)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EventReactionModel(Base):
    __tablename__ = "event_reactions"

    __table_args__ = (
        UniqueConstraint("event_id", "account_id", name="uq_event_reaction"),
        Index("ix_event_reactions_event", "event_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    event_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("events.id"))
    account_id: Mapped[UUID] = mapped_column(Uuid)
    kind: Mapped[str] = mapped_column(String)
    reacted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EventViewModel(Base):
    __tablename__ = "event_views"

    __table_args__ = (
        # Une vue par personne : le rayonnement compte des gens, pas des ouvertures d'écran.
        UniqueConstraint("event_id", "viewer_account_id", name="uq_event_view"),
        Index("ix_event_views_event", "event_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    event_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("events.id"))
    viewer_account_id: Mapped[UUID] = mapped_column(Uuid)
    denomination: Mapped[str | None] = mapped_column(String, nullable=True)
    viewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EventReportModel(Base):
    __tablename__ = "event_reports"

    __table_args__ = (
        # Un signalement par personne : sans elle, dix clics d'un même compte pèseraient dix fois
        # sur la modération.
        UniqueConstraint("event_id", "reporter_account_id", name="uq_event_report"),
        Index("ix_event_reports_event", "event_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    event_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("events.id"))
    reporter_account_id: Mapped[UUID] = mapped_column(Uuid)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
