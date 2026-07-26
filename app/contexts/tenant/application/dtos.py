"""DTO d'entrée/sortie du provisionnement (découplés du framework)."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ProvisionTenantRequest:
    """Données d'un provisionnement d'église (surface backoffice, acte Plateforme)."""

    tenant_name: str
    owner_phone: str
    owner_email: str  # identifiant de connexion backoffice de l'Owner
    owner_password: str  # mot de passe initial de l'Owner
    owner_first_name: str | None = None
    owner_last_name: str | None = None
    parent_id: UUID | None = None  # filiation (émancipation) ; null = église indépendante
    # Attributs de l'église (optionnels sauf le nom).
    denomination: str | None = None  # null = indépendante
    contact_email: str | None = None
    estimated_member_count: int | None = None
    country: str | None = None
    city: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
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
class ProvisionTenantResult:
    tenant_id: UUID
    owner_account_id: UUID
    owner_membership_id: UUID


@dataclass(frozen=True)
class SubmitOnboardingInput:
    tenant_name: str
    owner_email: str
    owner_phone: str
    owner_password: str
    owner_first_name: str | None = None
    owner_last_name: str | None = None
    owner_years_of_experience: int | None = None
    denomination: str | None = None
    contact_email: str | None = None
    estimated_member_count: int | None = None
    country: str | None = None
    city: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    # --- Champs M0 §2.2 (parité avec le provisionnement direct) ---
    logo_url: str | None = None
    short_description: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    timezone: str = "Africa/Abidjan"
    language: str = "fr"
    currency: str = "XOF"
    operates_annexes: bool = False


@dataclass(frozen=True)
class OnboardingResult:
    request_id: UUID
    status: str


@dataclass(frozen=True)
class TenantDetailDTO:
    tenant_id: UUID
    name: str
    status: str
    denomination: str | None
    contact_email: str | None
    estimated_member_count: int | None
    country: str | None
    city: str | None
    address: str | None
    latitude: float | None
    longitude: float | None
    is_independent: bool
    # --- Champs M0 §2.2 ---
    slug: str | None = None
    logo_url: str | None = None
    short_description: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    timezone: str = "Africa/Abidjan"
    language: str = "fr"
    currency: str = "XOF"
    operates_annexes: bool = False


@dataclass(frozen=True)
class UpdateTenantInput:
    denomination: str | None = None
    contact_email: str | None = None
    estimated_member_count: int | None = None
    country: str | None = None
    city: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    # --- Champs M0 §2.2 (éditables) ---
    logo_url: str | None = None
    short_description: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    timezone: str | None = None
    language: str | None = None
    currency: str | None = None
