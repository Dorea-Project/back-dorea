"""Modèle ORM du module Sermon (le backend possède le schéma ; enum en String)."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SermonModel(Base):
    __tablename__ = "sermons"

    __table_args__ = (Index("ix_sermons_tenant", "tenant_id"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    author_account_id: Mapped[UUID] = mapped_column(Uuid)
    title: Mapped[str] = mapped_column(String)
    reference: Mapped[str | None] = mapped_column(String, nullable=True)
    source_kind: Mapped[str] = mapped_column(String)
    raw_text: Mapped[str] = mapped_column(Text)
    preached_on: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SermonDigestModel(Base):
    """Le digest IA d'un sermon (1:1) — généré une fois, gelé après approbation."""

    __tablename__ = "sermon_digests"

    sermon_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("sermons.id"), primary_key=True
    )
    summary: Mapped[str] = mapped_column(Text)
    key_points: Mapped[list] = mapped_column(JSON)  # list[str]
    capsules: Mapped[list] = mapped_column(JSON)  # list[{title, body}]
    questions: Mapped[list] = mapped_column(JSON)  # list[{prompt, guidance}]


class CompanionSessionModel(Base):
    """La conversation privée d'un membre avec un sermon (S-3)."""

    __tablename__ = "companion_sessions"

    __table_args__ = (Index("ix_companion_member_sermon", "member_account_id", "sermon_id"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    sermon_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("sermons.id"))
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    member_account_id: Mapped[UUID] = mapped_column(Uuid)
    attended: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    step: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
