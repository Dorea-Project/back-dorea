"""Modèle ORM du module Notifications — l'appareil (jeton push)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DeviceModel(Base):
    __tablename__ = "devices"

    __table_args__ = (Index("ix_devices_account", "account_id"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    account_id: Mapped[UUID] = mapped_column(Uuid)
    token: Mapped[str] = mapped_column(String, unique=True)
    platform: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ScheduledNotificationModel(Base):
    __tablename__ = "scheduled_notifications"

    # L'index du worker : ce qui est du, pas encore parti.
    __table_args__ = (Index("ix_scheduled_notifications_due", "status", "scheduled_for"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    account_ids: Mapped[list[str]] = mapped_column(JSON)  # comptes cibles (UUID en str)
    # La **clé** du catalogue et le contenu humain à y glisser — jamais la phrase. Une phrase
    # écrite ici se figerait dans la langue du jour où le rappel a été posé, des semaines avant
    # d'être lu (voir `ScheduledNotification`).
    message_key: Mapped[str | None] = mapped_column(String, nullable=True)
    params: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # ⚠️ Transitoires : le texte déjà rendu des lignes planifiées **avant** le bilingue. Elles
    # partent telles quelles, puis la file se draine (24 h au plus) et ces deux colonnes s'en
    # vont. Nullables depuis la même migration : rien de neuf ne les remplit.
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
