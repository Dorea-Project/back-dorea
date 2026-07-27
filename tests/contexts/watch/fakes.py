"""Doublures du moteur de veille : ledger en mémoire et dépôts M6."""

from __future__ import annotations

from uuid import UUID, uuid4

from app.contexts.attendance.domain.enums import AbsenceSource
from app.contexts.attendance.domain.repositories import (
    PlannedAbsenceRepository,
    WatchExclusionRepository,
)
from app.contexts.watch.application.intake import FactLedger
from app.contexts.watch.application.ports import SignalStore
from app.contexts.watch.domain.effects import CasePriority, ExtinguishCause
from app.contexts.watch.domain.errors import HumanClosureRequiredError
from app.contexts.watch.domain.facts import Fact
from app.contexts.watch.domain.signal import Signal, SignalStatus, outcome_for


class FakeLedger(FactLedger):
    """Append-only, comme le vrai : `seq` monte, rien ne se réécrit."""

    def __init__(self) -> None:
        self.rows: list[Fact] = []

    async def append(self, fact: Fact) -> Fact:
        sealed = fact.sealed(len(self.rows) + 1)
        self.rows.append(sealed)
        return sealed

    async def exists(self, fact_id: UUID) -> bool:
        return any(f.fact_id == fact_id for f in self.rows)

    async def stream(self, tenant_id: UUID) -> list[Fact]:
        return [f for f in self.rows if f.tenant_id == tenant_id]


class FakeAbsences(PlannedAbsenceRepository):
    def __init__(self) -> None:
        self.rows = []

    async def add(self, absence):
        self.rows.append(absence)

    async def get(self, absence_id):
        return next((a for a in self.rows if a.id == absence_id), None)

    async def save(self, absence):
        pass  # agrégat muté en mémoire

    async def list_active_by_tenant(self, tenant_id):
        return [a for a in self.rows if a.tenant_id == tenant_id and a.is_active]

    async def list_active_by_account(self, account_id, tenant_id):
        return [
            a
            for a in self.rows
            if a.account_id == account_id and a.tenant_id == tenant_id and a.is_active
        ]

    async def get_by_source(self, account_id, source_ref):
        return next(
            (
                a
                for a in self.rows
                if a.account_id == account_id and a.source_ref == source_ref
            ),
            None,
        )

    async def list_open_neutralizations(self, account_id, tenant_id):
        return [
            a
            for a in self.rows
            if a.account_id == account_id
            and a.tenant_id == tenant_id
            and a.is_neutralization
            and a.is_open
        ]

    async def list_open_neutralizations_by_tenant(self, tenant_id):
        return [
            a
            for a in self.rows
            if a.tenant_id == tenant_id and a.is_neutralization and a.is_open
        ]

    async def delete_projected(self, tenant_id):
        self.rows = [
            a
            for a in self.rows
            if not (a.tenant_id == tenant_id and a.source is AbsenceSource.ANNOUNCEMENT)
        ]


class FakeSignals(SignalStore):
    """Doublure du store de cas : mêmes règles que le SQL, l'agrégat tranche."""

    def __init__(self) -> None:
        self.rows: list[Signal] = []
        self.memory: list[tuple] = []

    def _live(self, subject_id, tenant_id) -> Signal | None:
        return next(
            (
                s
                for s in self.rows
                if s.subject_id == subject_id and s.tenant_id == tenant_id and s.is_live
            ),
            None,
        )

    async def open_case(
        self, *, subject_id, tenant_id, origin, reason, opened_at, expires_at, source_ref, held
    ):
        existing = self._live(subject_id, tenant_id)
        if existing is not None:
            existing.enrich(source_ref=source_ref, expires_at=expires_at)
            return
        self.rows.append(
            Signal(
                id=uuid4(), tenant_id=tenant_id, subject_id=subject_id,
                origin=CasePriority(origin), reason=reason, opened_at=opened_at,
                status=SignalStatus.HELD if held else SignalStatus.OPEN,
                expires_at=expires_at, source_refs=[source_ref],
            )
        )

    async def enrich_case(
        self, *, subject_id, tenant_id, source_ref, extend_to,
        annotation=None, priority=None, downgrade=False,
    ):
        existing = self._live(subject_id, tenant_id)
        if existing is not None:
            existing.enrich(
                source_ref=source_ref, expires_at=extend_to, annotation=annotation,
                priority=CasePriority(priority) if priority else None, downgrade=downgrade,
            )

    async def extinguish(self, *, subject_id, tenant_id, cause, at):
        signal = self._live(subject_id, tenant_id)
        if signal is None:
            return
        parsed = ExtinguishCause(cause)
        try:
            signal.close(outcome=outcome_for(parsed), at=at, cause=parsed)
        except HumanClosureRequiredError:
            return  # la cause n'autorise pas de clôture système : le cas reste ouvert

    async def record_memory(self, *, subject_id, tenant_id, item, at, reason):
        self.memory.append((tenant_id, subject_id, item, at, reason, None))

    async def live_cases(self, tenant_id):
        return [
            (s.id, s.subject_id, s.owner_account_id, s.origin.value, s.is_held)
            for s in self.rows
            if s.tenant_id == tenant_id and s.is_live
        ]

    async def purge_projected(self, tenant_id):
        self.rows = [s for s in self.rows if s.tenant_id != tenant_id]
        self.memory = [m for m in self.memory if m[0] != tenant_id]


class FakeExclusions(WatchExclusionRepository):
    def __init__(self) -> None:
        self.rows = []

    async def add(self, exclusion):
        self.rows.append(exclusion)

    async def get_for(self, account_id, tenant_id):
        return next(
            (
                e
                for e in self.rows
                if e.account_id == account_id and e.tenant_id == tenant_id
            ),
            None,
        )

    async def excluded_account_ids(self, tenant_id):
        return {e.account_id for e in self.rows if e.tenant_id == tenant_id}

    async def delete_all(self, tenant_id):
        self.rows = [e for e in self.rows if e.tenant_id != tenant_id]
