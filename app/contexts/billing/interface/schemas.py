"""Schémas HTTP du module Billing. On ne reçoit ni ne renvoie **jamais** le numéro complet."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.contexts.billing.application.dtos import BusinessStatusDTO


class AddCardBody(BaseModel):
    """Données **non sensibles** d'une carte tokenisée côté client (jamais le PAN complet)."""

    brand: str = Field(default="visa", examples=["visa"])
    last4: str = Field(examples=["4242"], description="Les 4 derniers chiffres")
    prepaid: bool = Field(default=True, description="Doit être une carte prépayée")
    exp_month: int = Field(ge=1, le=12, examples=[12])
    exp_year: int = Field(examples=[2030])
    provider_token: str | None = Field(default=None, description="Jeton d'un futur PSP")


class BusinessStatusView(BaseModel):
    tier: str
    is_business: bool
    card_brand: str | None
    card_last4: str | None
    card_prepaid: bool | None

    @classmethod
    def from_dto(cls, d: BusinessStatusDTO) -> BusinessStatusView:
        return cls(
            tier=d.tier,
            is_business=d.is_business,
            card_brand=d.card_brand,
            card_last4=d.card_last4,
            card_prepaid=d.card_prepaid,
        )
