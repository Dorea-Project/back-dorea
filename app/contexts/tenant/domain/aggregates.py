"""Agrégat racine `Tenant` — l'Église dans Dorea (M0)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app._shared.domain.entity import AggregateRoot
from app.contexts.tenant.domain.enums import TenantStatus
from app.contexts.tenant.domain.value_objects import Location


class Tenant(AggregateRoot):
    """Tenant — l'Église (indépendante ou principale), racine de propriété.

    Créé par la Plateforme **avant** tout humain (il préexiste à son Owner) et
    **stable** : quand une personne part, le tenant ne bouge pas.

    - `denomination` : nom de la dénomination déclarée, ou `None` = **indépendante**.
      C'est une donnée descriptive d'inscription, distincte du futur `Network`
      (la fédération *formelle*, avec consentement).
    - `parent_id` : **filiation** tenant→tenant (église-mère ↔ fille issue d'une
      émancipation d'annexe). Ne sert jamais à la dénomination. Voir M0 §4.
    - `estimated_member_count` : taille **déclarée** à l'inscription (≠ nombre réel
      d'appartenances).
    - `contact_email` : email de l'**église** (≠ email d'un `Account`).
    """

    def __init__(
        self,
        *,
        id: UUID,
        name: str,
        created_at: datetime,
        status: TenantStatus = TenantStatus.ACTIVE,
        parent_id: UUID | None = None,
        denomination: str | None = None,
        contact_email: str | None = None,
        estimated_member_count: int | None = None,
        location: Location | None = None,
        # --- Champs M0 §2.2 (à plat ; regroupement conceptuel branding/contact/régional) ---
        slug: str | None = None,
        logo_url: str | None = None,
        short_description: str | None = None,
        contact_name: str | None = None,
        contact_phone: str | None = None,
        timezone: str = "Africa/Abidjan",
        language: str = "fr",
        currency: str = "XOF",  # FCFA Afrique de l'Ouest (BCEAO) ; XAF possible (BEAC)
        operates_annexes: bool = False,
    ) -> None:
        super().__init__()
        self.id = id
        self.name = name
        self.created_at = created_at
        self.status = status
        self.parent_id = parent_id
        self.denomination = denomination
        self.contact_email = contact_email
        self.estimated_member_count = estimated_member_count
        self.location = location or Location()
        self.slug = slug
        self.logo_url = logo_url
        self.short_description = short_description
        self.contact_name = contact_name
        self.contact_phone = contact_phone
        self.timezone = timezone
        self.language = language
        self.currency = currency
        self.operates_annexes = operates_annexes

    @property
    def is_independent(self) -> bool:
        """Église sans mère (filiation) — le cas simple couvert par la V1."""
        return self.parent_id is None

    @property
    def is_denominational(self) -> bool:
        """Rattachée (déclarativement) à une dénomination."""
        return self.denomination is not None

    @property
    def is_active(self) -> bool:
        return self.status is TenantStatus.ACTIVE

    def update_profile(
        self,
        *,
        denomination: str | None,
        contact_email: str | None,
        estimated_member_count: int | None,
        location: Location,
        logo_url: str | None = None,
        short_description: str | None = None,
        contact_name: str | None = None,
        contact_phone: str | None = None,
        timezone: str | None = None,
        language: str | None = None,
        currency: str | None = None,
    ) -> None:
        """Édition du profil par l'Owner (le nom, le slug et la filiation ne changent pas ici)."""
        self.denomination = denomination
        self.contact_email = contact_email
        self.estimated_member_count = estimated_member_count
        self.location = location
        self.logo_url = logo_url
        self.short_description = short_description
        self.contact_name = contact_name
        self.contact_phone = contact_phone
        # Régional : ne pas écraser par None (garde les défauts si non fournis).
        if timezone is not None:
            self.timezone = timezone
        if language is not None:
            self.language = language
        if currency is not None:
            self.currency = currency

    def suspend(self) -> None:
        self.status = TenantStatus.SUSPENDED

    def reactivate(self) -> None:
        self.status = TenantStatus.ACTIVE
