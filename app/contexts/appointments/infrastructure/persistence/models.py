"""Modèle ORM du module Rendez-vous (le backend possède le schéma ; enum en String)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AppointmentModel(Base):
    __tablename__ = "appointments"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    # Émetteur : membre (compte) OU walk-in au bureau (nom + tél, sans compte).
    requester_account_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    requester_name: Mapped[str | None] = mapped_column(String, nullable=True)
    requester_phone: Mapped[str | None] = mapped_column(String, nullable=True)
    with_pastor_account_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    category: Mapped[str] = mapped_column(String)
    subject: Mapped[str] = mapped_column(Text)
    preferred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    handled_by_account_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AvailabilityRuleModel(Base):
    __tablename__ = "availability_rules"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    pastor_account_id: Mapped[UUID] = mapped_column(Uuid)
    weekday: Mapped[int] = mapped_column(Integer)  # 0 = lundi … 6 = dimanche
    start_minute: Mapped[int] = mapped_column(Integer)  # minutes depuis minuit (UTC)
    end_minute: Mapped[int] = mapped_column(Integer)
    slot_minutes: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
