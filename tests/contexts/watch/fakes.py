"""Doublures du moteur de veille : ledger en mémoire et dépôts M6."""

from __future__ import annotations

from uuid import UUID, uuid4

from app.contexts.attendance.domain.enums import AbsenceSource
from app.contexts.attendance.domain.repositories import (
    PlannedAbsenceRepository,
    WatchExclusionRepository,
)
from app.contexts.watch.application.intake import FactLedger
from app.contexts.watch.application.ports import (
    ContactAttemptStore,
    ScheduledCheckStore,
    SignalStore,
)
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

    async def stream(self, tenant_id: UUID):
        """Un flux trié par `seq`, comme le vrai — le rejeu ne retrie jamais après coup."""
        for fact in sorted(
            (f for f in self.rows if f.tenant_id == tenant_id),
            key=lambda f: f.seq if f.seq is not None else 0,
        ):
            yield fact


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
        self, *, subject_id, tenant_id, origin, reason, opened_at, expires_at, source_ref, held,
        owner_account_id=None, held_reason=None,
    ):
        existing = self._live(subject_id, tenant_id)
        if existing is not None:
            existing.enrich(source_ref=source_ref, expires_at=expires_at)
            return
        if held:
            status = SignalStatus.HELD
        elif owner_account_id is not None:
            status = SignalStatus.ASSIGNED
        else:
            status = SignalStatus.OPEN
        previous = self._last_resolved(subject_id, tenant_id)
        self.rows.append(
            Signal(
                id=uuid4(), tenant_id=tenant_id, subject_id=subject_id,
                origin=CasePriority(origin), reason=reason, opened_at=opened_at,
                status=status, owner_account_id=owner_account_id,
                expires_at=expires_at, source_refs=[source_ref],
                episode_id=previous.episode_id if previous else None,
                occurrence_number=(previous.occurrence_number + 1) if previous else 1,
                previous_outcome=previous.outcome if previous else None,
                previous_closed_at=previous.closed_at if previous else None,
            )
        )
        self.rows[-1].held_reason = held_reason if held else None

    def _last_resolved(self, subject_id, tenant_id):
        closed = [
            s
            for s in self.rows
            if s.subject_id == subject_id
            and s.tenant_id == tenant_id
            and s.status is SignalStatus.CLOSED
            and s.outcome is not None
            and s.closed_at is not None
        ]
        return max(closed, key=lambda s: s.closed_at) if closed else None

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

    async def case_of_subject(self, subject_id, tenant_id):
        s = self._live(subject_id, tenant_id)
        if s is None:
            return None
        return (s.id, s.subject_id, s.owner_account_id, s.origin.value, s.is_held)

    async def open_cases_count(self, owner_id, tenant_id):
        from app.contexts.watch.domain.signal import ON_SHOULDERS_STATUSES

        return sum(
            1
            for s in self.rows
            if s.tenant_id == tenant_id
            and s.owner_account_id == owner_id
            and s.status in ON_SHOULDERS_STATUSES
        )

    async def mark_contact_started(self, *, signal_id, tenant_id, at):
        signal = next((s for s in self.rows if s.id == signal_id), None)
        if signal is not None:
            signal.record_contact_attempt(at=at)

    async def origin_of(self, signal_id, tenant_id):
        signal = next((s for s in self.rows if s.id == signal_id), None)
        return signal.origin if signal is not None else None

    async def extinguish_by_id(self, *, signal_id, tenant_id, cause, at):
        signal = next((s for s in self.rows if s.id == signal_id), None)
        if signal is None:
            return
        parsed = ExtinguishCause(cause)
        try:
            signal.close(outcome=outcome_for(parsed), at=at, cause=parsed)
        except HumanClosureRequiredError:
            return

    async def do_not_contact_ids(self, tenant_id):
        from app.contexts.watch.domain.signal import SignalOutcome

        return {
            s.subject_id
            for s in self.rows
            if s.tenant_id == tenant_id and s.outcome is SignalOutcome.DO_NOT_CONTACT
        }

    async def cases_of_owner(self, *, account_id, tenant_id):
        from app.contexts.watch.domain.signal import ON_SHOULDERS_STATUSES, priority_rank

        mine = [
            s
            for s in self.rows
            if s.tenant_id == tenant_id
            and s.owner_account_id == account_id
            and s.status in ON_SHOULDERS_STATUSES
        ]
        mine.sort(key=lambda s: (priority_rank(s.priority), s.opened_at))
        return mine

    async def get_case(self, *, signal_id, tenant_id):
        return next(
            (s for s in self.rows if s.id == signal_id and s.tenant_id == tenant_id), None
        )

    async def live_case_of(self, *, subject_id, tenant_id):
        return self._live(subject_id, tenant_id)

    async def cases_by_subjects(self, *, subject_ids, tenant_id):
        wanted = {s for s in subject_ids if s is not None}
        return {
            s.subject_id: s
            for s in self.rows
            if s.tenant_id == tenant_id and s.subject_id in wanted and s.is_live
        }

    async def save_case(self, signal):
        pass  # agrégat muté en mémoire

    def _concerns(self, tenant_id):
        return [
            s
            for s in self.rows
            if s.tenant_id == tenant_id and s.origin is CasePriority.CONCERN
        ]

    async def stale_concerns(self, *, tenant_id, opened_before):
        return [
            (s.id, s.owner_account_id, s.opened_at)
            for s in self._concerns(tenant_id)
            if s.is_live and s.first_contact_at is None and s.opened_at <= opened_before
        ]

    async def concern_activity(self, *, tenant_id, since):
        return [
            (s.owner_account_id, s.first_contact_at is not None)
            for s in self._concerns(tenant_id)
            if s.opened_at >= since
        ]

    async def concern_outcomes(self, *, tenant_id, since):
        return [
            s.outcome.value
            for s in self._concerns(tenant_id)
            if s.status is SignalStatus.CLOSED
            and s.outcome is not None
            and s.closed_at is not None
            and s.closed_at >= since
        ]

    async def mark_contact_started_for_subject(self, *, subject_id, tenant_id, at):
        signal = self._live(subject_id, tenant_id)
        if signal is not None:
            signal.record_contact_attempt(at=at)

    async def mark_seen(self, *, subject_id, tenant_id, at):
        signal = self._live(subject_id, tenant_id)
        if signal is not None:
            signal.see(at=at)

    async def resolve_case(self, *, subject_id, tenant_id, outcome, at, by_account_id):
        from app.contexts.watch.domain.signal import SignalOutcome

        signal = self._live(subject_id, tenant_id)
        if signal is not None:
            signal.close(
                outcome=SignalOutcome(outcome), at=at, closed_by_account_id=by_account_id
            )

    async def retract_held(self, *, subject_id, tenant_id, at):
        from app.contexts.watch.domain.signal import RetractionCause

        signal = self._live(subject_id, tenant_id)
        if signal is not None and signal.is_held:
            signal.retract(at=at, cause=RetractionCause.SUPERSEDED_BY_LIFE_SIGN)

    async def held_cases(self, *, tenant_id):
        return [s for s in self.rows if s.tenant_id == tenant_id and s.is_held]

    async def human_traces(self, tenant_id):
        from app.contexts.watch.application.ports import HumanTraces

        mine = [s for s in self.rows if s.tenant_id == tenant_id]
        return HumanTraces(
            seen=sum(1 for s in mine if s.first_seen_at is not None),
            contacted=sum(1 for s in mine if s.first_contact_at is not None),
            closed=sum(1 for s in mine if s.closed_by_account_id is not None),
            gestures=sum(1 for s in mine if s.gestures_count > 0),
            # La doublure stocke la mémoire en tuples : le 6ᵉ champ est `delivered_at`.
            delivered_memories=sum(
                1 for m in self.memory if m[0] == tenant_id and m[5] is not None
            ),
        )

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


class FakeContactAttempts(ContactAttemptStore):
    def __init__(self) -> None:
        self.rows = []

    async def add(self, attempt):
        self.rows.append(attempt)

    async def get(self, attempt_id):
        return next((a for a in self.rows if a.id == attempt_id), None)

    async def save(self, attempt):
        pass  # agrégat muté en mémoire

    async def purge_projected(self, tenant_id):
        self.rows = [a for a in self.rows if a.tenant_id != tenant_id]

    async def record(self, *, attempt_id, subject_id, tenant_id, by_account_id, channel, at):
        from app.contexts.watch.domain.contact import ContactAttempt, ContactResult

        if any(a.id == attempt_id for a in self.rows):
            return  # rejouer n'empile pas : l'identifiant vient du journal
        self.rows.append(
            ContactAttempt(
                id=attempt_id,
                tenant_id=tenant_id,
                signal_id=self._signal_of(subject_id, tenant_id),
                by_account_id=by_account_id,
                channel=channel,
                attempted_at=at,
                result=ContactResult.PENDING,
            )
        )

    def _signal_of(self, subject_id, tenant_id):
        """Le cas vivant de la personne — la doublure porte la même règle que le SQL."""
        for signal in getattr(self, "signals", []) or []:
            if signal.subject_id == subject_id and signal.tenant_id == tenant_id and signal.is_live:
                return signal.id
        return subject_id

    async def resolve(self, *, attempt_id, result, at, commitment=None):
        from app.contexts.watch.domain.contact import ContactResult

        attempt = next((a for a in self.rows if a.id == attempt_id), None)
        if attempt is not None:
            attempt.resolve(result=ContactResult(result), at=at, commitment=commitment)

    async def count_not_reached(self, signal_id):
        from app.contexts.watch.domain.contact import ContactResult

        return sum(
            1
            for a in self.rows
            if a.signal_id == signal_id and a.result is ContactResult.NOT_REACHED
        )

    async def pending_for(self, *, account_id, tenant_id, since):
        return [
            a
            for a in self.rows
            if a.by_account_id == account_id
            and a.tenant_id == tenant_id
            and a.awaits_answer
            and a.attempted_at >= since
        ]


class FakeChecks(ScheduledCheckStore):
    """Les échéances en mémoire. Mêmes règles que le SQL : idempotence et exclusivité."""

    def __init__(self) -> None:
        self.rows = []

    def _pending(self, subject_id, tenant_id):
        return [
            c
            for c in self.rows
            if c["subject_id"] == subject_id
            and c["tenant_id"] == tenant_id
            and c["fired_at"] is None
            and c["cancelled_at"] is None
        ]

    async def schedule(
        self, *, subject_id, tenant_id, kind, reason, due_at, at, payload=None
    ):
        # Tous les états, tirées comprises : rejouer ne repose pas une échéance déjà tombée.
        already = [
            c
            for c in self.rows
            if c["subject_id"] == subject_id
            and c["tenant_id"] == tenant_id
            and c["kind"] == kind
            and c["due_at"] == due_at
        ]
        if already:
            return  # rejouer le ledger ne duplique pas une échéance
        self.rows.append(
            {
                "id": uuid4(), "tenant_id": tenant_id, "subject_id": subject_id,
                "kind": kind, "reason": reason, "payload": dict(payload or {}),
                "due_at": due_at, "scheduled_at": at,
                "fired_at": None, "cancelled_at": None,
            }
        )

    async def cancel_for(self, *, subject_id, tenant_id, kind, at):
        targets = [
            c for c in self._pending(subject_id, tenant_id) if kind is None or c["kind"] == kind
        ]
        for c in targets:
            c["cancelled_at"] = at
        return len(targets)

    async def due(self, *, tenant_id, now, limit):
        from app.contexts.watch.infrastructure.persistence.checks import DueCheck

        ready = sorted(
            (
                c
                for c in self.rows
                if c["tenant_id"] == tenant_id
                and c["due_at"] <= now
                and c["fired_at"] is None
                and c["cancelled_at"] is None
            ),
            key=lambda c: c["due_at"],
        )
        return [
            DueCheck(
                id=c["id"], tenant_id=c["tenant_id"], subject_id=c["subject_id"],
                kind=c["kind"], reason=c["reason"], due_at=c["due_at"],
                payload=dict(c.get("payload") or {}),
            )
            for c in ready[:limit]
        ]

    async def mark_fired(self, *, check_id, at):
        for c in self.rows:
            if c["id"] == check_id:
                c["fired_at"] = at

    async def pending_count(self, *, tenant_id, now):
        return sum(
            1
            for c in self.rows
            if c["tenant_id"] == tenant_id
            and c["due_at"] <= now
            and c["fired_at"] is None
            and c["cancelled_at"] is None
        )

    async def purge_projected(self, tenant_id):
        """Seul ce qui pend s'efface : le tir et l'annulation sont des actes, pas des dérivés."""
        self.rows = [
            c
            for c in self.rows
            if c["tenant_id"] != tenant_id
            or c["fired_at"] is not None
            or c["cancelled_at"] is not None
        ]


def case_acts_for(signals: FakeSignals, *, clock, attempts=None):
    """Les gestes du responsable, câblés sur le **vrai** chemin : fait → interpreter → écriture.

    Depuis le lot 3bis, « j'ai vu » et « je ferme » ne mutent plus la projection directement : ils
    entrent au journal. Un test qui construirait une commande sans ce chemin ne testerait plus ce
    que fait la production."""
    from app.contexts.watch.application.case_acts import RecordCaseAct
    from app.contexts.watch.application.intake import Intake
    from app.contexts.watch.application.interpretation import InterpreterRegistry
    from app.contexts.watch.application.interpreters.case_acts import (
        CaseClosedV1,
        CaseSeenV1,
    )
    from app.contexts.watch.domain.registry import default_registry
    from app.contexts.watch.infrastructure.neutralization_store import (
        AttendanceNeutralizationStore,
    )

    interpreters = InterpreterRegistry()
    interpreters.register(CaseSeenV1())
    interpreters.register(CaseClosedV1())
    from app.contexts.watch.application.interpreters.case_acts import (
        ContactAnsweredV1,
        ContactAttemptedV1,
    )

    interpreters.register(ContactAttemptedV1())
    interpreters.register(ContactAnsweredV1())
    if attempts is not None:
        # La doublure des tentatives a besoin de connaître les cas pour rattacher chacune au
        # sien — comme le SQL, qui retrouve le cas vivant de la personne.
        attempts.signals = signals.rows
    intake = Intake(
        FakeLedger(),
        default_registry(),
        interpreters,
        AttendanceNeutralizationStore(FakeAbsences(), FakeExclusions()),
        signals,
        attempts=attempts,
    )
    return RecordCaseAct(intake, clock=clock)
