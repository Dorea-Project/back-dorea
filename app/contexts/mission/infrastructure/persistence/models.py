"""Modèles ORM du contexte Mission (M9). Enums en String (le backend possède le schéma)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MissionLinkModel(Base):
    __tablename__ = "mission_links"

    __table_args__ = (
        Index("ix_mission_links_account", "inviter_account_id"),
        Index("ix_mission_links_group", "inviter_group_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    inviter_account_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    inviter_group_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    message: Mapped[str] = mapped_column(String)
    media_urls: Mapped[list[str]] = mapped_column(JSON, default=list)
    place_label: Mapped[str | None] = mapped_column(String, nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    code: Mapped[str] = mapped_column(String, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SeekerModel(Base):
    __tablename__ = "seekers"

    __table_args__ = (
        Index("ix_seekers_person", "person_account_id"),
        Index("ix_seekers_inviter_account", "inviter_account_id"),
        Index("ix_seekers_inviter_group", "inviter_group_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    link_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("mission_links.id"))
    inviter_account_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    inviter_group_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    name: Mapped[str] = mapped_column(String)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accompanied_by_account_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    accompanied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # La **personne**, créée dès l'acceptation. Tant qu'elle n'existait qu'à l'intégration,
    # l'inviteur ne devenait référent qu'au moment où elle en avait le moins besoin — et
    # ces gens restaient hors du dénominateur de couverture, c'est-à-dire les plus fragiles.
    person_account_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    integrated_account_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    integrated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MissionReactionModel(Base):
    __tablename__ = "mission_reactions"

    __table_args__ = (Index("ix_mission_reactions_link", "link_id"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    link_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("mission_links.id"))
    kind: Mapped[str] = mapped_column(String)
    reacted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
