"""Niveau de compte (module Billing) — le tier porté par la personne."""

from enum import StrEnum


class AccountTier(StrEnum):
    """Le tier d'un compte. `business` s'obtient en enregistrant une carte prépayée Visa."""

    FREE = "free"  # par défaut — l'église, gratuitement
    BUSINESS = "business"  # rayonner plus loin (dénomination, plateforme)
