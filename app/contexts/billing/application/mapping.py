"""Mappage agrégat → DTO (module Billing)."""

from __future__ import annotations

from app.contexts.billing.application.dtos import BusinessStatusDTO
from app.contexts.billing.domain.aggregates import BusinessAccount


def to_status_dto(account: BusinessAccount | None) -> BusinessStatusDTO:
    # Pas de compte enregistré = tier gratuit (l'état par défaut de toute personne).
    if account is None or account.card is None:
        return BusinessStatusDTO(
            tier="free", is_business=False, card_brand=None, card_last4=None, card_prepaid=None
        )
    card = account.card
    return BusinessStatusDTO(
        tier=account.tier.value,
        is_business=True,
        card_brand=card.brand,
        card_last4=card.last4,
        card_prepaid=card.prepaid,
    )
