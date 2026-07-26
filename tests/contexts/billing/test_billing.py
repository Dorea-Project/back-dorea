"""Module Billing — le compte Business d'une personne, par carte prépayée Visa (non facturé)."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.contexts.billing.application.commands.manage_card import (
    AddPaymentCard,
    RemovePaymentCard,
)
from app.contexts.billing.application.queries.business_status import GetBusinessStatus
from app.contexts.billing.domain.aggregates import PaymentCard
from app.contexts.billing.domain.errors import (
    InvalidPaymentCardError,
    PrepaidVisaRequiredError,
)
from app.contexts.billing.domain.repositories import BusinessAccountRepository

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


class _FakeAccounts(BusinessAccountRepository):
    def __init__(self, items=()):
        self._a = list(items)

    async def get_by_account(self, account_id):
        return next((x for x in self._a if x.account_id == account_id), None)

    async def add(self, account):
        self._a.append(account)

    async def save(self, account):
        pass  # muté en mémoire (même instance)


def _visa(**over):
    args = dict(
        actor_account_id=uuid4(), brand="visa", last4="4242",
        prepaid=True, exp_month=12, exp_year=2030,
    )
    args.update(over)
    return args


# --- Le domaine : la carte ---


def test_a_prepaid_visa_is_valid():
    PaymentCard(
        brand="visa", last4="4242", prepaid=True, exp_month=12, exp_year=2030, added_at=_NOW
    ).validate()  # ne lève pas


def test_a_non_visa_or_non_prepaid_card_is_refused():
    with pytest.raises(PrepaidVisaRequiredError):
        PaymentCard(
            brand="mastercard", last4="4242", prepaid=True, exp_month=12, exp_year=2030,
            added_at=_NOW,
        ).validate()
    with pytest.raises(PrepaidVisaRequiredError):
        PaymentCard(
            brand="visa", last4="4242", prepaid=False, exp_month=12, exp_year=2030, added_at=_NOW
        ).validate()


def test_bad_last4_is_refused():
    with pytest.raises(InvalidPaymentCardError):
        PaymentCard(
            brand="visa", last4="42", prepaid=True, exp_month=12, exp_year=2030, added_at=_NOW
        ).validate()


# --- Les use cases ---


async def test_adding_a_prepaid_visa_activates_business():
    accounts = _FakeAccounts()
    dto = await AddPaymentCard(accounts, clock=lambda: _NOW).execute(**_visa())
    assert dto.is_business is True and dto.tier == "business"
    assert dto.card_brand == "visa" and dto.card_last4 == "4242"


async def test_a_non_prepaid_visa_does_not_activate():
    add = AddPaymentCard(_FakeAccounts(), clock=lambda: _NOW)
    with pytest.raises(PrepaidVisaRequiredError):
        await add.execute(**_visa(prepaid=False))


async def test_removing_the_card_returns_to_free():
    actor = uuid4()
    accounts = _FakeAccounts()
    await AddPaymentCard(accounts, clock=lambda: _NOW).execute(**_visa(actor_account_id=actor))
    dto = await RemovePaymentCard(accounts, clock=lambda: _NOW).execute(actor_account_id=actor)
    assert dto.is_business is False and dto.tier == "free"


async def test_default_status_is_free():
    dto = await GetBusinessStatus(_FakeAccounts()).execute(actor_account_id=uuid4())
    assert dto.is_business is False and dto.tier == "free" and dto.card_last4 is None
