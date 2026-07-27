"""Modèle ORM du module Rendez-vous (le backend possède le schéma ; enum en String)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text, Uuid
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
    # Servi autrement (pas refusé) : vers qui la demande a été réorientée.
    oriented_to_account_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    # **Qui** a annulé. Le demandeur qui recule après avoir levé la main est le signal le plus
    # urgent du produit ; l'église qui ferme un rendez-vous caduc ne dit pas la même chose.
    cancelled_by_account_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    # Chez qui la demande est **actuellement**. Distinct de `with_pastor_account_id`, qui est le
    # pasteur du créneau une fois posé : une demande est routée avant d'être confirmée.
    routed_to_account_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    routed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    relay_count: Mapped[int] = mapped_column(Integer, default=0)
    # **Stocké** : un pasteur qui reçoit une demande sans savoir pourquoi elle lui arrive
    # l'ignore.
    relay_reason: Mapped[str | None] = mapped_column(String, nullable=True)


class PastorUnavailabilityModel(Base):
    """Une **absence déclarée** d'un pasteur — à ne pas confondre avec ses créneaux.

    `AvailabilityRuleModel` dit *quand il reçoit* ; ceci dit *quand il n'est pas là*. Les
    confondre coûte cher : sans cette table, un pasteur en voyage trois semaines ferait attendre
    **chaque** demande le délai de relais complet avant d'être contourné — alors qu'on savait
    dès le premier jour qu'il ne répondrait pas. L'absence est prévisible ; l'oubli se constate.
    """

    __tablename__ = "pastor_unavailabilities"

    __table_args__ = (
        Index("ix_pastor_unavailability", "tenant_id", "pastor_account_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    pastor_account_id: Mapped[UUID] = mapped_column(Uuid)
    unavailable_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    unavailable_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str | None] = mapped_column(String, nullable=True)  # court, jamais exigé
    declared_by_account_id: Mapped[UUID] = mapped_column(Uuid)
    declared_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PastorOverrideModel(Base):
    """« C'est ce pasteur-là qui la reçoit. » Stocké seulement parce que quelqu'un l'a décidé."""

    __tablename__ = "pastor_overrides"

    __table_args__ = (Index("ix_pastor_override_person", "tenant_id", "person_id"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    person_id: Mapped[UUID] = mapped_column(Uuid)
    pastor_account_id: Mapped[UUID] = mapped_column(Uuid)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_by_account_id: Mapped[UUID] = mapped_column(Uuid)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


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
