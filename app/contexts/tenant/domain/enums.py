"""Énumérations du contexte Tenant (M0)."""

from enum import StrEnum


class TenantStatus(StrEnum):
    """Cycle de vie d'un tenant — permet de désactiver une église sans la supprimer."""

    ACTIVE = "active"
    SUSPENDED = "suspended"


class OwnershipStatus(StrEnum):
    """Statut d'une propriété (siège Owner) : un seul `active` par tenant à la fois."""

    ACTIVE = "active"
    ENDED = "ended"


class OwnershipMode(StrEnum):
    """Mode d'attribution du siège (les 3 portes d'accès, M0 §3.1)."""

    BOOTSTRAP = "bootstrap"  # genèse (création de l'église)
    SUCCESSION = "succession"  # transfert entre deux titulaires
    EMANCIPATION = "emancipation"  # annexe devenue tenant
