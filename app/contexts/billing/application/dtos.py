"""DTO applicatifs du module Billing."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BusinessStatusDTO:
    """Le statut de facturation d'une personne — jamais de donnée de carte sensible."""

    tier: str  # free | business
    is_business: bool
    card_brand: str | None
    card_last4: str | None
    card_prepaid: bool | None
