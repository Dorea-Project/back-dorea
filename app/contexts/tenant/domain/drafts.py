"""Brouillons de données (form snapshots) partagés : provisionnement & onboarding."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class TenantDraft:
    name: str
    denomination: str | None = None
    country: str | None = None
    city: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    contact_email: str | None = None
    estimated_member_count: int | None = None
    parent_id: UUID | None = None  # filiation (émancipation) ; null = indépendante
    # --- Champs M0 §2.2 ---
    logo_url: str | None = None
    short_description: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    timezone: str = "Africa/Abidjan"
    language: str = "fr"
    currency: str = "XOF"
    operates_annexes: bool = False


@dataclass(frozen=True)
class OwnerDraft:
    email: str
    phone: str
    first_name: str | None = None
    last_name: str | None = None
    years_of_experience: int | None = None
