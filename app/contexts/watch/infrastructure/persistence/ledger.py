"""Implémentation SQLAlchemy du ledger. Append-only : ni `save`, ni `delete`, par construction."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.watch.application.intake import FactLedger
from app.contexts.watch.domain.facts import (
    ConsentProof,
    ConsentScope,
    Fact,
    FactKind,
    SubjectKind,
)
from app.contexts.watch.infrastructure.persistence.models import FactLedgerModel


def _aware(dt):
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _to_consent(raw: dict | None) -> ConsentProof | None:
    if not raw:
        return None
    return ConsentProof(
        given_by=UUID(raw["given_by"]),
        scope=ConsentScope(raw["scope"]),
        given_at=_aware(_parse(raw["given_at"])),
        revocable=bool(raw.get("revocable", True)),
    )


def _parse(value: str):
    from datetime import datetime

    return datetime.fromisoformat(value)


def _to_fact(row: FactLedgerModel) -> Fact:
    return Fact(
        fact_id=row.fact_id,
        tenant_id=row.tenant_id,
        occurred_at=_aware(row.occurred_at),
        recorded_at=_aware(row.recorded_at),
        source=row.source,
        kind=FactKind(row.kind),
        subject_kind=SubjectKind(row.subject_kind),
        subject_id=row.subject_id,
        payload=dict(row.payload or {}),
        payload_version=row.payload_version,
        consent=_to_consent(row.consent),
        seq=row.seq,
    )


class SqlFactLedger(FactLedger):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(self, fact: Fact) -> Fact:
        row = FactLedgerModel(
            fact_id=fact.fact_id,
            tenant_id=fact.tenant_id,
            occurred_at=fact.occurred_at,
            recorded_at=fact.recorded_at,
            source=fact.source,
            kind=fact.kind.value,
            subject_kind=fact.subject_kind.value,
            subject_id=fact.subject_id,
            payload=dict(fact.payload),
            payload_version=fact.payload_version,
            consent=(
                {
                    "given_by": str(fact.consent.given_by),
                    "scope": fact.consent.scope.value,
                    "given_at": fact.consent.given_at.isoformat(),
                    "revocable": fact.consent.revocable,
                }
                if fact.consent is not None
                else None
            ),
        )
        self._session.add(row)
        await self._session.flush()  # assigne `seq` — la place du fait dans l'ordre total
        return fact.sealed(row.seq)

    async def exists(self, fact_id: UUID) -> bool:
        stmt = select(FactLedgerModel.seq).where(FactLedgerModel.fact_id == fact_id).limit(1)
        return (await self._session.execute(stmt)).scalar_one_or_none() is not None

    async def stream(self, tenant_id: UUID) -> AsyncIterator[Fact]:
        """Le journal d'une église, dans l'ordre où il a été écrit — **un flux**, pas une liste.

        Un curseur serveur : deux cent mille faits ne montent pas en mémoire pour être rejoués.
        L'ordre est celui de `seq`, le seul ordre total dont on dispose — les dates ne suffisent
        pas (`recorded_at` peut être à égalité, `occurred_at` peut remonter le temps), et sans
        ordre total l'invariant de déterminisme n'est pas testable.

        Le tri est donc fait par la base, une fois, au lieu d'être refait en mémoire après coup."""
        stmt = (
            select(FactLedgerModel)
            .where(FactLedgerModel.tenant_id == tenant_id)
            .order_by(FactLedgerModel.seq)
            .execution_options(yield_per=500)
        )
        result = await self._session.stream_scalars(stmt)
        async for row in result:
            yield _to_fact(row)
