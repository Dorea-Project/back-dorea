"""Modèles ORM du contexte Tenant — tables `tenants` et `annexes` (M0)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TenantModel(Base):
    __tablename__ = "tenants"

    # Unicité du `slug` quand présent (identifiant lisible pour liens/QR, M0 §2.2) —
    # index *partiel* : les tenants sans slug (lignes anciennes) restent permis.
    __table_args__ = (
        Index(
            "uq_tenants_slug_not_null",
            "slug",
            unique=True,
            postgresql_where=text("slug IS NOT NULL"),
            sqlite_where=text("slug IS NOT NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    slug: Mapped[str | None] = mapped_column(String, nullable=True)
    # server_default → les lignes existantes reçoivent 'active' lors de l'ADD COLUMN.
    status: Mapped[str] = mapped_column(String, server_default=text("'active'"))
    # Dénomination déclarée (null = indépendante) — descriptif, ≠ Network formel.
    denomination: Mapped[str | None] = mapped_column(String, nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String, nullable=True)  # email de l'église
    contact_name: Mapped[str | None] = mapped_column(String, nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String, nullable=True)
    estimated_member_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Branding (M0 §2.2).
    logo_url: Mapped[str | None] = mapped_column(String, nullable=True)
    short_description: Mapped[str | None] = mapped_column(String, nullable=True)
    # Régional (Church OS multi-pays, M0 §2.2) — défauts pour les lignes existantes.
    timezone: Mapped[str] = mapped_column(String, server_default=text("'Africa/Abidjan'"))
    language: Mapped[str] = mapped_column(String, server_default=text("'fr'"))
    currency: Mapped[str] = mapped_column(String, server_default=text("'XOF'"))
    # Localisation (value object `Location` à plat).
    country: Mapped[str | None] = mapped_column(String, nullable=True)
    city: Mapped[str | None] = mapped_column(String, nullable=True)
    address: Mapped[str | None] = mapped_column(String, nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Filiation tenant→tenant (annexe = église-fille, M0 §4.1). `null` = principal.
    parent_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    # Déclaré au signup, lu par le module subscription (plan famille). `false` pour une annexe.
    operates_annexes: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OnboardingRequestModel(Base):
    """Demande d'onboarding (avant matérialisation du tenant/owner)."""

    __tablename__ = "onboarding_requests"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    status: Mapped[str] = mapped_column(String)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    # Brouillon tenant
    tenant_name: Mapped[str] = mapped_column(String)
    denomination: Mapped[str | None] = mapped_column(String, nullable=True)
    country: Mapped[str | None] = mapped_column(String, nullable=True)
    city: Mapped[str | None] = mapped_column(String, nullable=True)
    address: Mapped[str | None] = mapped_column(String, nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String, nullable=True)
    estimated_member_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Brouillon tenant — champs M0 §2.2 (parité provisionnement direct)
    logo_url: Mapped[str | None] = mapped_column(String, nullable=True)
    short_description: Mapped[str | None] = mapped_column(String, nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String, nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String, nullable=True)
    timezone: Mapped[str] = mapped_column(String, server_default=text("'Africa/Abidjan'"))
    language: Mapped[str] = mapped_column(String, server_default=text("'fr'"))
    currency: Mapped[str] = mapped_column(String, server_default=text("'XOF'"))
    operates_annexes: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    # Brouillon owner
    owner_email: Mapped[str] = mapped_column(String)
    owner_phone: Mapped[str] = mapped_column(String)
    owner_first_name: Mapped[str | None] = mapped_column(String, nullable=True)
    owner_last_name: Mapped[str | None] = mapped_column(String, nullable=True)
    owner_years_of_experience: Mapped[int | None] = mapped_column(Integer, nullable=True)
    owner_password_hash: Mapped[str] = mapped_column(String)


class OwnershipModel(Base):
    """Propriété d'un tenant (siège Owner) — 1 seule `active` par tenant (index partiel)."""

    __tablename__ = "tenant_ownerships"

    __table_args__ = (
        Index(
            "uq_one_active_ownership_per_tenant",
            "tenant_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
            sqlite_where=text("status = 'active'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    account_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("accounts.id"))
    tenant_id: Mapped[UUID] = mapped_column(Uuid)  # convention repo : Uuid simple
    status: Mapped[str] = mapped_column(String)
    mode: Mapped[str] = mapped_column(String)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
