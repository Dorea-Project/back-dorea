"""Modèles ORM du contexte Annonces (M8). Enums en String (le backend possède le schéma).

`tenant_id` est **nullable** : une annonce **plateforme** (Dorea, admin central) n'appartient à
aucune église. Les médias sont une liste d'**URL** (JSON) — l'upload vit ailleurs.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AnnouncementModel(Base):
    __tablename__ = "announcements"

    __table_args__ = (
        Index("ix_announcements_tenant", "tenant_id"),
        Index("ix_announcements_concerns", "concerns_account_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    tenant_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)  # None = plateforme
    category: Mapped[str] = mapped_column(String)
    intent: Mapped[str] = mapped_column(String)
    scope_group_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    title: Mapped[str] = mapped_column(String)
    body: Mapped[str | None] = mapped_column(String, nullable=True)
    media_urls: Mapped[list[str]] = mapped_column(JSON, default=list)
    author_account_id: Mapped[UUID] = mapped_column(Uuid)
    concerns_account_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String)
    event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    gathering_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    slots_needed: Mapped[int | None] = mapped_column(nullable=True)
    # **Quand c'est arrivé** — distinct de `event_at` (quand on se réunit) et de `published_at`
    # (quand on l'a dit). Toutes les durées de veille courent depuis là.
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AnnouncementSubjectModel(Base):
    """Qui est nommé dans l'annonce, et **à quel titre** — la clé de l'effet sur la veille."""

    __tablename__ = "announcement_subjects"

    __table_args__ = (
        # Une personne ne tient qu'un rôle par annonce ; c'est aussi la clé d'idempotence du
        # rejeu (annonce, personne) exigée par l'algorithme.
        UniqueConstraint("announcement_id", "account_id", name="uq_announcement_subject"),
        Index("ix_announcement_subjects_account", "account_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    announcement_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("announcements.id"))
    account_id: Mapped[UUID] = mapped_column(Uuid)
    role: Mapped[str] = mapped_column(String)
    effects: Mapped[list[str]] = mapped_column(JSON, default=list)  # après surcharge publicateur
    consent: Mapped[str] = mapped_column(String)
    declared_duration_days: Mapped[int | None] = mapped_column(nullable=True)
    attached_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consent_decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AnnouncementEngagementModel(Base):
    __tablename__ = "announcement_responses"  # « je viens / je sers / je porte »

    __table_args__ = (
        UniqueConstraint("announcement_id", "account_id", name="uq_response_per_account"),
        Index("ix_announcement_responses_announcement", "announcement_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    announcement_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("announcements.id"))
    account_id: Mapped[UUID] = mapped_column(Uuid)
    responded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AnnouncementReactionModel(Base):
    __tablename__ = "announcement_reactions"  # un emoji de la palette du type

    __table_args__ = (
        # Un emoji par personne et par annonce : c'est ce qui empêche la réaction de devenir un
        # compteur qu'on gonfle en cliquant.
        UniqueConstraint("announcement_id", "account_id", name="uq_reaction_per_account"),
        Index("ix_announcement_reactions_announcement", "announcement_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    announcement_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("announcements.id"))
    account_id: Mapped[UUID] = mapped_column(Uuid)
    emoji: Mapped[str] = mapped_column(String)
    reacted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
