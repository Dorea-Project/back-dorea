"""Modèle ORM du module Notifications — l'appareil (jeton push)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DeviceModel(Base):
    __tablename__ = "devices"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    account_id: Mapped[UUID] = mapped_column(Uuid)
    token: Mapped[str] = mapped_column(String, unique=True)
    platform: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ScheduledNotificationModel(Base):
    __tablename__ = "scheduled_notifications"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    account_ids: Mapped[list[str]] = mapped_column(JSON)  # comptes cibles (UUID en str)
    title: Mapped[str] = mapped_column(String)
    body: Mapped[str] = mapped_column(Text)
    data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
