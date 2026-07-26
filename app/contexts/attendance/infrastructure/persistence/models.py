"""Modèles ORM du contexte Présence — tables `gatherings` et `attendance_records` (M6)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class GatheringModel(Base):
    __tablename__ = "gatherings"

    __table_args__ = (
        Index("ix_gatherings_group", "group_id"),
        Index("ix_gatherings_tenant", "tenant_id"),
        Index("ix_gatherings_check_in_code", "check_in_code"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    group_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)  # None = église-entière
    type: Mapped[str] = mapped_column(String)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String)
    created_by_account_id: Mapped[UUID] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    check_in_code: Mapped[str | None] = mapped_column(String, nullable=True)  # M6-1
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AttendanceRecordModel(Base):
    """Un signal (présent / excusé) par personne et par rencontre."""

    __tablename__ = "attendance_records"

    __table_args__ = (
        Index("uq_attendance_gathering_account", "gathering_id", "account_id", unique=True),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    gathering_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("gatherings.id"))
    account_id: Mapped[UUID] = mapped_column(Uuid)
    mark: Mapped[str] = mapped_column(String)
    source: Mapped[str] = mapped_column(String)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recorded_by_account_id: Mapped[UUID] = mapped_column(Uuid)


class PlannedAbsenceModel(Base):
    """Absence pré-déclarée sur une période (M6-2) — tenant-large."""

    __tablename__ = "planned_absences"

    __table_args__ = (
        Index("ix_planned_absences_tenant", "tenant_id"),
        Index("ix_planned_absences_account", "account_id"),
        # Résolution de l'idempotence `(annonce, personne)` au rejeu d'une annonce.
        Index("ix_planned_absences_source_ref", "source_ref"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    account_id: Mapped[UUID] = mapped_column(Uuid)
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    reason: Mapped[str] = mapped_column(String)
    note: Mapped[str | None] = mapped_column(String, nullable=True)
    from_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    to_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    declared_by_account_id: Mapped[UUID] = mapped_column(Uuid)
    declared_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Origine : déclarée par le membre, ou **neutralisation** posée par une annonce (M8).
    source: Mapped[str] = mapped_column(String, default="self_declared")
    source_ref: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)  # l'annonce d'origine
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    outcome: Mapped[str | None] = mapped_column(String, nullable=True)


class WatchExclusionModel(Base):
    """Retrait **définitif** de la veille (décès annoncé) — statut de veille, pas d'appartenance."""

    __tablename__ = "watch_exclusions"

    __table_args__ = (
        # Une seule exclusion par personne et par église : l'absorbant est idempotent.
        UniqueConstraint("tenant_id", "account_id", name="uq_watch_exclusion"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    account_id: Mapped[UUID] = mapped_column(Uuid)
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    reason: Mapped[str] = mapped_column(String)
    excluded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    declared_by_account_id: Mapped[UUID] = mapped_column(Uuid)
    source_ref: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    note: Mapped[str | None] = mapped_column(String, nullable=True)


class GatheringVisitorModel(Base):
    """Un visage nouveau capturé à une rencontre (M6-3) — hors roster, sans compte."""

    __tablename__ = "gathering_visitors"

    __table_args__ = (Index("ix_gathering_visitors_gathering", "gathering_id"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    gathering_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("gatherings.id"))
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    name: Mapped[str] = mapped_column(String)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    captured_by_account_id: Mapped[UUID] = mapped_column(Uuid)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class GatheringRsvpModel(Base):
    """« Je viens » à une rencontre (pré-signal M8) — une ligne par rencontre et compte."""

    __tablename__ = "gathering_rsvps"

    __table_args__ = (
        Index("ix_gathering_rsvps_gathering", "gathering_id"),
        UniqueConstraint("gathering_id", "account_id", name="uq_rsvp_per_account"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    gathering_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("gatherings.id"))
    account_id: Mapped[UUID] = mapped_column(Uuid)
    rsvp_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class GroupCadenceModel(Base):
    """Le rythme attendu d'un groupe — le `Programme` (P1). Une cadence active par groupe.

    On stocke la **règle**, jamais le roster (l'interdit M6 tient). `group_id` sans FK, comme
    `gatherings.group_id` (convention attendance : pas de FK inter-contexte vers groups).
    """

    __tablename__ = "group_cadences"

    __table_args__ = (
        Index("ix_group_cadences_tenant", "tenant_id"),
        Index("ix_group_cadences_group", "group_id"),
        Index(
            "uq_one_active_cadence_per_group",
            "group_id",
            unique=True,
            postgresql_where=text("canceled_at IS NULL"),
            sqlite_where=text("canceled_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    group_id: Mapped[UUID] = mapped_column(Uuid)
    frequency: Mapped[str] = mapped_column(String)
    weekday: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0-6, weekly/biweekly
    day_of_month: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1-28, monthly
    anchor_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    active_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    active_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_by_account_id: Mapped[UUID] = mapped_column(Uuid)
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CadenceAcknowledgementModel(Base):
    """Une occurrence attendue non tenue, motif connu (ACQUITTEE) — P1. Motif enum, sans note."""

    __tablename__ = "cadence_acknowledgements"

    __table_args__ = (
        Index("ix_cadence_acks_group", "group_id"),
        Index("ix_cadence_acks_tenant", "tenant_id"),
        UniqueConstraint("group_id", "occurrence_date", name="uq_ack_per_occurrence"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    group_id: Mapped[UUID] = mapped_column(Uuid)
    occurrence_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str] = mapped_column(String)
    suspension_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    acknowledged_by_account_id: Mapped[UUID] = mapped_column(Uuid)
    acknowledged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ChurchSuspensionModel(Base):
    """Période église (Noël, deuil) qui acquitte en cascade — P1. Cascade calculée à la lecture."""

    __tablename__ = "church_suspensions"

    __table_args__ = (Index("ix_church_suspensions_tenant", "tenant_id"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    reason: Mapped[str] = mapped_column(String)
    from_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    to_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    declared_by_account_id: Mapped[UUID] = mapped_column(Uuid)
    declared_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
