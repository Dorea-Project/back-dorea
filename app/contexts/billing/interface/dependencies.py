"""Injection de dépendances du module Billing."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends

from app.api.deps import DbSession
from app.contexts.billing.application.commands.manage_card import (
    AddPaymentCard,
    RemovePaymentCard,
)
from app.contexts.billing.application.queries.business_status import GetBusinessStatus
from app.contexts.billing.infrastructure.persistence.repository import (
    SqlBusinessAccountRepository,
)


def _now() -> datetime:
    return datetime.now(UTC)


def get_add_card_command(session: DbSession) -> AddPaymentCard:
    return AddPaymentCard(SqlBusinessAccountRepository(session), clock=_now)


def get_remove_card_command(session: DbSession) -> RemovePaymentCard:
    return RemovePaymentCard(SqlBusinessAccountRepository(session), clock=_now)


def get_status_query(session: DbSession) -> GetBusinessStatus:
    return GetBusinessStatus(SqlBusinessAccountRepository(session))


AddPaymentCardDep = Annotated[AddPaymentCard, Depends(get_add_card_command)]
RemovePaymentCardDep = Annotated[RemovePaymentCard, Depends(get_remove_card_command)]
GetBusinessStatusDep = Annotated[GetBusinessStatus, Depends(get_status_query)]
