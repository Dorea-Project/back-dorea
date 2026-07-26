"""Implémentation SQLAlchemy de `SignalStore`.

L'agrégat `Signal` porte les règles ; ce fichier ne fait que les persister. En particulier c'est
`Signal.close` qui refuse une clôture sans humain — le dépôt ne rejoue pas cette décision, il
demande à l'agrégat et respecte sa réponse.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.watch.application.ports import SignalStore
from app.contexts.watch.domain.effects import CasePriority, ExtinguishCause
from app.contexts.watch.domain.errors import HumanClosureRequiredError
from app.contexts.watch.domain.signal import (
    LIVE_STATUSES,
    Signal,
    SignalStatus,
    outcome_for,
)
from app.contexts.watch.infrastructure.persistence.models import (
    CareMemoryModel,
    SignalModel,
)

_LIVE = tuple(s.value for s in LIVE_STATUSES)


def _aware(dt):
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _to_signal(row: SignalModel) -> Signal:
    from app.contexts.watch.domain.signal import SignalOutcome

    return Signal(
        id=row.id,
        tenant_id=row.tenant_id,
        subject_id=row.subject_id,
        origin=CasePriority(row.origin),
        reason=row.reason,
        opened_at=_aware(row.opened_at),
        status=SignalStatus(row.status),
        expires_at=_aware(row.expires_at),
        owner_account_id=row.owner_account_id,
        source_refs=[UUID(r) for r in (row.source_refs or [])],
        gestures_count=row.gestures_count,
        outcome=SignalOutcome(row.outcome) if row.outcome else None,
        closed_at=_aware(row.closed_at),
        closed_by_account_id=row.closed_by_account_id,
        retracted_at=_aware(row.retracted_at),
    )


class SqlSignalStore(SignalStore):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _live_row(self, subject_id: UUID, tenant_id: UUID) -> SignalModel | None:
        stmt = (
            select(SignalModel)
            .where(
                SignalModel.tenant_id == tenant_id,
                SignalModel.subject_id == subject_id,
                SignalModel.status.in_(_LIVE),
            )
            .order_by(SignalModel.opened_at)
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def open_case(
        self,
        *,
        subject_id: UUID,
        tenant_id: UUID,
        origin: str,
        reason: str,
        opened_at: datetime,
        expires_at: datetime | None,
        source_ref: UUID,
        held: bool,
    ) -> None:
        existing = await self._live_row(subject_id, tenant_id)
        if existing is not None:
            # Un seul cas par personne : on enrichit celui qui est là. Sinon deux responsables
            # appelleraient la même personne le même soir, chacun se croyant seul.
            await self._merge(existing, source_ref=source_ref, extend_to=expires_at)
            return

        self._session.add(
            SignalModel(
                id=uuid4(),
                tenant_id=tenant_id,
                subject_id=subject_id,
                origin=origin,
                status=(SignalStatus.HELD if held else SignalStatus.OPEN).value,
                reason=reason,
                opened_at=opened_at,
                expires_at=expires_at,
                owner_account_id=None,  # `Referent` n'existe pas encore — NULL est la vérité
                source_refs=[str(source_ref)],
                gestures_count=0,
            )
        )
        await self._session.flush()

    async def enrich_case(
        self, *, subject_id: UUID, tenant_id: UUID, source_ref: UUID, extend_to: datetime | None
    ) -> None:
        existing = await self._live_row(subject_id, tenant_id)
        if existing is None:
            return
        await self._merge(existing, source_ref=source_ref, extend_to=extend_to)

    async def _merge(
        self, row: SignalModel, *, source_ref: UUID, extend_to: datetime | None
    ) -> None:
        signal = _to_signal(row)
        if signal.enrich(source_ref=source_ref, expires_at=extend_to):
            row.source_refs = [str(r) for r in signal.source_refs]
            row.expires_at = signal.expires_at
            await self._session.flush()

    async def extinguish(
        self, *, subject_id: UUID, tenant_id: UUID, cause: str, at: datetime
    ) -> None:
        row = await self._live_row(subject_id, tenant_id)
        if row is None:
            return
        parsed = ExtinguishCause(cause)
        signal = _to_signal(row)
        try:
            signal.close(outcome=outcome_for(parsed), at=at, cause=parsed)
        except HumanClosureRequiredError:
            # La cause n'autorise pas de clôture système : le cas **reste ouvert**, et c'est
            # voulu. Fermer ici serait exactement le « nettoyage automatique » qu'on s'interdit.
            return
        row.status = signal.status.value
        row.outcome = signal.outcome.value if signal.outcome else None
        row.closed_at = signal.closed_at
        await self._session.flush()

    async def record_memory(
        self, *, subject_id: UUID, tenant_id: UUID, item: str, at: datetime, reason: str
    ) -> None:
        self._session.add(
            CareMemoryModel(
                id=uuid4(),
                tenant_id=tenant_id,
                subject_id=subject_id,
                item=item,
                reason=reason,
                occurred_at=at,
            )
        )
        await self._session.flush()

    async def live_cases(
        self, tenant_id: UUID
    ) -> list[tuple[UUID, UUID, UUID | None, str, bool]]:
        stmt = select(SignalModel).where(
            SignalModel.tenant_id == tenant_id, SignalModel.status.in_(_LIVE)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [
            (r.id, r.subject_id, r.owner_account_id, r.origin, r.status == SignalStatus.HELD.value)
            for r in rows
        ]

    async def purge_projected(self, tenant_id: UUID) -> None:
        await self._session.execute(
            delete(SignalModel).where(SignalModel.tenant_id == tenant_id)
        )
        await self._session.execute(
            delete(CareMemoryModel).where(CareMemoryModel.tenant_id == tenant_id)
        )
        await self._session.flush()
