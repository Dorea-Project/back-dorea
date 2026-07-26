"""Erreurs du module Billing — codes préfixés `BILL_`."""

from app._shared.domain.errors import DomainError


class BillingError(DomainError):
    code = "BILL_ERROR"


class PrepaidVisaRequiredError(BillingError):
    """Le compte Business s'active avec une **carte prépayée Visa** — pas une autre."""

    code = "BILL_PREPAID_VISA_REQUIRED"
    http_status = 422


class InvalidPaymentCardError(BillingError):
    """Données de carte incohérentes (4 derniers chiffres, expiration…)."""

    code = "BILL_CARD_INVALID"
    http_status = 422
