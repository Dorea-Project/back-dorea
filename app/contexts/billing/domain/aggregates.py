"""Agrégat `BusinessAccount` — le tier d'une **personne** (un par compte).

Le compte devient **Business** dès qu'une **carte prépayée Visa** y est enregistrée — **pas encore
facturé** : enregistrer la carte suffit à ouvrir le tier (l'échafaudage de facturation viendra).
On ne stocke **jamais** le numéro complet (PCI) : seulement les 4 derniers, la marque, l'expiration
et un éventuel jeton de fournisseur.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app._shared.domain.entity import AggregateRoot
from app.contexts.billing.domain.enums import AccountTier
from app.contexts.billing.domain.errors import (
    InvalidPaymentCardError,
    PrepaidVisaRequiredError,
)


@dataclass(frozen=True)
class PaymentCard:
    """Un moyen de paiement enregistré — **données non sensibles seulement** (pas de PAN)."""

    brand: str  # doit être « visa »
    last4: str  # 4 derniers chiffres
    prepaid: bool  # doit être vrai (carte prépayée)
    exp_month: int
    exp_year: int
    added_at: datetime
    provider_token: str | None = None  # référence tokenisée d'un futur PSP

    def validate(self) -> None:
        if self.brand.strip().lower() != "visa" or not self.prepaid:
            raise PrepaidVisaRequiredError(
                "Une carte prépayée Visa est requise pour activer le compte Business."
            )
        if not (len(self.last4) == 4 and self.last4.isdigit()):
            raise InvalidPaymentCardError("Les 4 derniers chiffres sont invalides.")
        if not (1 <= self.exp_month <= 12):
            raise InvalidPaymentCardError("Mois d'expiration invalide.")


class BusinessAccount(AggregateRoot):
    def __init__(
        self,
        *,
        id: UUID,
        account_id: UUID,
        card: PaymentCard | None,
        created_at: datetime,
        updated_at: datetime,
    ) -> None:
        super().__init__()
        self.id = id
        self.account_id = account_id  # une personne = un compte de facturation
        self.card = card
        self.created_at = created_at
        self.updated_at = updated_at

    @classmethod
    def open_free(cls, *, id: UUID, account_id: UUID, now: datetime) -> BusinessAccount:
        return cls(id=id, account_id=account_id, card=None, created_at=now, updated_at=now)

    @property
    def is_business(self) -> bool:
        return self.card is not None

    @property
    def tier(self) -> AccountTier:
        return AccountTier.BUSINESS if self.is_business else AccountTier.FREE

    def add_card(self, card: PaymentCard, *, now: datetime) -> None:
        card.validate()
        self.card = card  # carte enregistrée → tier Business (non facturé)
        self.updated_at = now

    def remove_card(self, *, now: datetime) -> None:
        self.card = None  # retour au tier gratuit
        self.updated_at = now
