"""Implémentation SQLAlchemy de `SignalStore`.

L'agrégat `Signal` porte les règles ; ce fichier ne fait que les persister. En particulier c'est
`Signal.close` qui refuse une clôture sans humain — le dépôt ne rejoue pas cette décision, il
demande à l'agrégat et respecte sa réponse.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

# La liste des issues « non confirmées » est définie **une fois**, là où elle est raisonnée. La
# réécrire ici ferait deux vérités sur la même question, et celle qui arrange finirait par gagner.
from app.contexts.watch.application.concern_watchdog import UNCONFIRMED_OUTCOMES
from app.contexts.watch.application.ports import (
    ContactAttemptStore,
    HumanTraces,
    SignalStore,
)
from app.contexts.watch.domain.contact import (
    ContactAttempt,
    ContactChannel,
    ContactResult,
)
from app.contexts.watch.domain.effects import CasePriority, ExtinguishCause
from app.contexts.watch.domain.errors import HumanClosureRequiredError
from app.contexts.watch.domain.facts import FactKind
from app.contexts.watch.domain.signal import (
    LIVE_STATUSES,
    ON_SHOULDERS_STATUSES,
    RetractionCause,
    Signal,
    SignalOutcome,
    SignalStatus,
    outcome_for,
    priority_rank,
)
from app.contexts.watch.infrastructure.persistence.models import (
    CareMemoryModel,
    ContactAttemptModel,
    FactLedgerModel,
    SignalModel,
)

_LIVE = tuple(s.value for s in LIVE_STATUSES)
_ON_SHOULDERS = tuple(s.value for s in ON_SHOULDERS_STATUSES)


def _aware(dt):
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _to_signal(row: SignalModel) -> Signal:
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
        first_seen_at=_aware(row.first_seen_at),
        first_contact_at=_aware(row.first_contact_at),
        episode_id=row.episode_id,
        occurrence_number=row.occurrence_number,
        previous_outcome=(
            SignalOutcome(row.previous_outcome) if row.previous_outcome else None
        ),
        previous_closed_at=_aware(row.previous_closed_at),
        priority=CasePriority(row.priority) if row.priority else None,
        annotations=list(row.annotations or []),
        gestures_count=row.gestures_count,
        outcome=SignalOutcome(row.outcome) if row.outcome else None,
        closed_at=_aware(row.closed_at),
        closed_by_account_id=row.closed_by_account_id,
        retracted_at=_aware(row.retracted_at),
        retraction_cause=row.retraction_cause,
        held_reason=row.held_reason,
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

    async def _last_resolved_row(self, subject_id: UUID, tenant_id: UUID) -> SignalModel | None:
        """Le dernier cas **clos** de cette personne — jamais un cas rétracté.

        Une rétractation n'a rien résolu : la transmettre ferait porter à la réouverture une
        issue qui n'a jamais eu lieu."""
        stmt = (
            select(SignalModel)
            .where(
                SignalModel.tenant_id == tenant_id,
                SignalModel.subject_id == subject_id,
                SignalModel.status == SignalStatus.CLOSED.value,
                SignalModel.outcome.is_not(None),
            )
            .order_by(SignalModel.closed_at.desc())
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
        owner_account_id: UUID | None = None,
        held_reason: str | None = None,
    ) -> None:
        existing = await self._live_row(subject_id, tenant_id)
        if existing is not None:
            # Un seul cas par personne : on enrichit celui qui est là. Sinon deux responsables
            # appelleraient la même personne le même soir, chacun se croyant seul.
            await self._merge(existing, source_ref=source_ref, extend_to=expires_at)
            return

        # Un cas retenu par le plafond garde son propriétaire mais **pas** le statut `ASSIGNED` :
        # il est détecté, pas encore sur les épaules de quelqu'un.
        if held:
            status = SignalStatus.HELD
        elif owner_account_id is not None:
            status = SignalStatus.ASSIGNED
        else:
            status = SignalStatus.OPEN

        case_id = uuid4()
        previous = await self._last_resolved_row(subject_id, tenant_id)
        self._session.add(
            SignalModel(
                id=case_id,
                tenant_id=tenant_id,
                subject_id=subject_id,
                origin=origin,
                status=status.value,
                episode_id=previous.episode_id if previous is not None else case_id,
                occurrence_number=(
                    previous.occurrence_number + 1 if previous is not None else 1
                ),
                previous_outcome=previous.outcome if previous is not None else None,
                previous_closed_at=previous.closed_at if previous is not None else None,
                reason=reason,
                opened_at=opened_at,
                expires_at=expires_at,
                # NULL reste admis, et c'est **une donnée** : « personne ne connaît cette
                # personne » est précisément ce qu'il faut voir.
                owner_account_id=owner_account_id,
                source_refs=[str(source_ref)],
                priority=CasePriority(origin).value,
                annotations=[],
                gestures_count=0,
                held_reason=held_reason if held else None,
            )
        )
        await self._session.flush()

    async def enrich_case(
        self,
        *,
        subject_id: UUID,
        tenant_id: UUID,
        source_ref: UUID,
        extend_to: datetime | None,
        annotation: str | None = None,
        priority: str | None = None,
        downgrade: bool = False,
        gesture: bool = False,
    ) -> None:
        existing = await self._live_row(subject_id, tenant_id)
        if existing is None:
            return
        await self._merge(
            existing,
            source_ref=source_ref,
            extend_to=extend_to,
            annotation=annotation,
            priority=CasePriority(priority) if priority else None,
            downgrade=downgrade,
            gesture=gesture,
        )

    async def _merge(
        self,
        row: SignalModel,
        *,
        source_ref: UUID,
        extend_to: datetime | None,
        annotation: str | None = None,
        priority: CasePriority | None = None,
        downgrade: bool = False,
        gesture: bool = False,
    ) -> None:
        signal = _to_signal(row)
        changed = signal.enrich(
            source_ref=source_ref,
            expires_at=extend_to,
            annotation=annotation,
            priority=priority,
            downgrade=downgrade,
        )
        if changed:
            # **L'idempotence du comptage est portée par `enrich`**, qui déduplique sur
            # `source_ref` : rejouer le même fait ne change rien, donc n'incrémente rien. Compter
            # avant ce test empilerait un geste de plus à chaque reprojection.
            if gesture:
                signal.record_gesture()
                row.gestures_count = signal.gestures_count
            row.source_refs = [str(r) for r in signal.source_refs]
            row.expires_at = signal.expires_at
            row.annotations = list(signal.annotations)
            row.priority = signal.priority.value
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

    async def case_of_subject(
        self, subject_id: UUID, tenant_id: UUID
    ) -> tuple[UUID, UUID, UUID | None, str, bool] | None:
        """Le cas en cours de cette personne — `ix_watch_signals_subject`, une ligne au plus."""
        row = await self._live_row(subject_id, tenant_id)
        if row is None:
            return None
        return (
            row.id,
            row.subject_id,
            row.owner_account_id,
            row.origin,
            row.status == SignalStatus.HELD.value,
        )

    async def open_cases_count(self, owner_id: UUID | None, tenant_id: UUID) -> int:
        """Le plafond de débit en un COUNT — `ix_watch_signals_owner`.

        `HELD` est exclu par `_ON_SHOULDERS` : un cas retenu est détecté, pas encore porté."""
        stmt = select(func.count()).where(
            SignalModel.tenant_id == tenant_id,
            SignalModel.owner_account_id == owner_id,
            SignalModel.status.in_(_ON_SHOULDERS),
        )
        return int((await self._session.execute(stmt)).scalar_one())

    async def do_not_contact_ids(self, tenant_id: UUID) -> set[UUID]:
        """Absorbant : ce retrait vaut pour toutes les surfaces, moteur ou non."""
        stmt = select(SignalModel.subject_id).where(
            SignalModel.tenant_id == tenant_id,
            SignalModel.outcome == SignalOutcome.DO_NOT_CONTACT.value,
        )
        return set((await self._session.execute(stmt)).scalars().all())

    async def mark_contact_started(
        self, *, signal_id: UUID, tenant_id: UUID, at: datetime
    ) -> None:
        row = await self._session.get(SignalModel, signal_id)
        if row is None or row.tenant_id != tenant_id:
            return
        signal = _to_signal(row)
        signal.record_contact_attempt(at=at)
        row.status = signal.status.value
        row.first_seen_at = signal.first_seen_at
        row.first_contact_at = signal.first_contact_at
        await self._session.flush()

    async def origin_of(self, signal_id: UUID, tenant_id: UUID) -> CasePriority | None:
        row = await self._session.get(SignalModel, signal_id)
        if row is None or row.tenant_id != tenant_id:
            return None
        return CasePriority(row.origin)

    async def extinguish_by_id(
        self, *, signal_id: UUID, tenant_id: UUID, cause: str, at: datetime
    ) -> None:
        row = await self._session.get(SignalModel, signal_id)
        if row is None or row.tenant_id != tenant_id:
            return
        parsed = ExtinguishCause(cause)
        signal = _to_signal(row)
        try:
            signal.close(outcome=outcome_for(parsed), at=at, cause=parsed)
        except HumanClosureRequiredError:
            return
        row.status = signal.status.value
        row.outcome = signal.outcome.value if signal.outcome else None
        row.closed_at = signal.closed_at
        await self._session.flush()

    async def cases_of_owner(self, *, account_id: UUID, tenant_id: UUID) -> list[Signal]:
        stmt = select(SignalModel).where(
            SignalModel.tenant_id == tenant_id,
            SignalModel.owner_account_id == account_id,
            SignalModel.status.in_(_ON_SHOULDERS),
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        cases = [_to_signal(r) for r in rows]
        # Tri en Python : l'ordre est celui des **rangs de priorité**, qui vivent dans le
        # domaine. Le reproduire en SQL le dupliquerait, et les deux divergeraient.
        cases.sort(key=lambda s: (priority_rank(s.priority), s.opened_at))
        return cases

    async def get_case(self, *, signal_id: UUID, tenant_id: UUID) -> Signal | None:
        row = await self._session.get(SignalModel, signal_id)
        if row is None or row.tenant_id != tenant_id:
            return None
        return _to_signal(row)

    async def live_case_of(self, *, subject_id: UUID, tenant_id: UUID) -> Signal | None:
        row = await self._live_row(subject_id, tenant_id)
        return _to_signal(row) if row is not None else None

    async def cases_by_subjects(
        self, *, subject_ids, tenant_id: UUID
    ) -> dict[UUID, Signal]:
        ids = [s for s in subject_ids if s is not None]
        if not ids:
            return {}
        stmt = select(SignalModel).where(
            SignalModel.tenant_id == tenant_id,
            SignalModel.subject_id.in_(ids),
            SignalModel.status.in_(_LIVE),
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return {r.subject_id: _to_signal(r) for r in rows}

    async def mark_contact_started_for_subject(
        self, *, subject_id: UUID, tenant_id: UUID, at: datetime
    ) -> None:
        row = await self._live_row(subject_id, tenant_id)
        if row is None:
            return
        signal = _to_signal(row)
        signal.record_contact_attempt(at=at)
        await self.save_case(signal)

    async def mark_seen(self, *, subject_id: UUID, tenant_id: UUID, at: datetime) -> None:
        row = await self._live_row(subject_id, tenant_id)
        if row is None:
            return
        signal = _to_signal(row)
        signal.see(at=at)
        row.first_seen_at = signal.first_seen_at

    async def resolve_case(
        self,
        *,
        subject_id: UUID,
        tenant_id: UUID,
        outcome: str,
        at: datetime,
        by_account_id: UUID,
    ) -> None:
        row = await self._live_row(subject_id, tenant_id)
        if row is None:
            return
        signal = _to_signal(row)
        signal.close(
            outcome=SignalOutcome(outcome), at=at, closed_by_account_id=by_account_id
        )
        await self.save_case(signal)

    async def accompanied_since(
        self, *, subject_id: UUID, tenant_id: UUID
    ) -> datetime | None:
        stmt = (
            select(CareMemoryModel.occurred_at)
            .where(
                CareMemoryModel.tenant_id == tenant_id,
                CareMemoryModel.subject_id == subject_id,
            )
            .order_by(CareMemoryModel.occurred_at)
            .limit(1)
        )
        return _aware((await self._session.execute(stmt)).scalars().first())

    async def retract_held(
        self, *, subject_id: UUID, tenant_id: UUID, at: datetime
    ) -> None:
        row = await self._live_row(subject_id, tenant_id)
        if row is None or row.status != SignalStatus.HELD.value:
            return  # on n'efface jamais un cas que quelqu'un a pu lire
        signal = _to_signal(row)
        signal.retract(at=at, cause=RetractionCause.SUPERSEDED_BY_LIFE_SIGN)
        row.status = signal.status.value
        row.retracted_at = signal.retracted_at
        row.retraction_cause = signal.retraction_cause
        await self._session.flush()

    async def held_cases(self, *, tenant_id: UUID) -> list[Signal]:
        """Les cas retenus par le plafond — `ix_watch_signals_tenant_status`."""
        stmt = select(SignalModel).where(
            SignalModel.tenant_id == tenant_id,
            SignalModel.status == SignalStatus.HELD.value,
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_signal(r) for r in rows]

    async def save_case(self, signal: Signal) -> None:
        row = await self._session.get(SignalModel, signal.id)
        if row is None:
            return
        row.status = signal.status.value
        row.held_reason = signal.held_reason
        row.owner_account_id = signal.owner_account_id
        row.priority = signal.priority.value
        row.annotations = list(signal.annotations)
        row.gestures_count = signal.gestures_count
        row.first_seen_at = signal.first_seen_at
        row.first_contact_at = signal.first_contact_at
        row.outcome = signal.outcome.value if signal.outcome else None
        row.closed_at = signal.closed_at
        row.closed_by_account_id = signal.closed_by_account_id
        row.retracted_at = signal.retracted_at
        await self._session.flush()

    async def stale_concerns(
        self, *, tenant_id: UUID, opened_before: datetime
    ) -> list[tuple[UUID, UUID | None, datetime]]:
        stmt = select(SignalModel).where(
            SignalModel.tenant_id == tenant_id,
            SignalModel.origin == CasePriority.CONCERN.value,
            SignalModel.status.in_(_LIVE),
            SignalModel.first_contact_at.is_(None),
            SignalModel.opened_at <= opened_before,
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [(r.id, r.owner_account_id, _aware(r.opened_at)) for r in rows]

    async def concern_activity(
        self, *, tenant_id: UUID, since: datetime
    ) -> list[tuple[UUID | None, bool]]:
        stmt = select(SignalModel.owner_account_id, SignalModel.first_contact_at).where(
            SignalModel.tenant_id == tenant_id,
            SignalModel.origin == CasePriority.CONCERN.value,
            SignalModel.opened_at >= since,
        )
        rows = (await self._session.execute(stmt)).all()
        return [(owner, contacted is not None) for owner, contacted in rows]

    async def closed_cases_since(
        self, *, tenant_id: UUID, since: datetime
    ) -> list[tuple[str, str]]:
        # Les rétractées sont hors du calcul : un cas devenu faux n'a rien résolu, et le compter
        # comme une intuition ratée punirait le déclarant d'une erreur du système.
        stmt = select(SignalModel.origin, SignalModel.outcome).where(
            SignalModel.tenant_id == tenant_id,
            SignalModel.status == SignalStatus.CLOSED.value,
            SignalModel.closed_at >= since,
            SignalModel.outcome.is_not(None),
            SignalModel.closed_by_account_id.is_not(None),
        )
        return [(o, u) for o, u in (await self._session.execute(stmt)).all()]

    async def absences_confirmed_after_a_gesture(
        self, *, tenant_id: UUID, since: datetime, within: timedelta
    ) -> int:
        """Le rapprochement cas ↔ journal — **deux requêtes, et le recollement en Python**.

        La fenêtre se compte à partir de `opened_at`, qui est une colonne : l'écrire en SQL
        demanderait une arithmétique d'intervalle que Postgres sait faire et SQLite non. On
        obtiendrait une requête qui ne tourne que sur la base de production, donc une requête que
        personne ne teste — c'est exactement le raisonnement qui a déjà été tenu pour le
        recollement d'un cas à son tir d'échéance, et la réponse est la même.

        Aucun identifiant ne sort d'ici : ils servent au rapprochement et la méthode rend un
        entier. C'est ce qui préserve l'interdit structurel de `closed_cases_since`."""
        cases = (
            await self._session.execute(
                select(SignalModel.subject_id, SignalModel.opened_at).where(
                    SignalModel.tenant_id == tenant_id,
                    SignalModel.origin == CasePriority.ABSENCE.value,
                    SignalModel.status == SignalStatus.CLOSED.value,
                    SignalModel.closed_at >= since,
                    SignalModel.outcome.is_not(None),
                    SignalModel.closed_by_account_id.is_not(None),
                    SignalModel.outcome.not_in([o.value for o in UNCONFIRMED_OUTCOMES]),
                )
            )
        ).all()
        if not cases:
            return 0

        floor = min(_aware(opened) for _, opened in cases) - within
        gestures = (
            await self._session.execute(
                select(FactLedgerModel.subject_id, FactLedgerModel.occurred_at).where(
                    FactLedgerModel.tenant_id == tenant_id,
                    FactLedgerModel.kind == FactKind.GESTURE_DONE.value,
                    FactLedgerModel.occurred_at >= floor,
                )
            )
        ).all()
        by_subject: dict[UUID, list[datetime]] = {}
        for subject_id, at in gestures:
            by_subject.setdefault(subject_id, []).append(_aware(at))

        # `any` et non un décompte : trois visites avant le même cas ne font qu'**un** cas manqué.
        return sum(
            1
            for subject_id, opened in cases
            if any(
                _aware(opened) - within <= at < _aware(opened)
                for at in by_subject.get(subject_id, ())
            )
        )

    async def ignored_by_owner(
        self, *, tenant_id: UUID, older_than: datetime
    ) -> list[tuple[UUID | None, int, int]]:
        stmt = (
            select(
                SignalModel.owner_account_id,
                func.count().filter(SignalModel.first_seen_at.is_(None)),
                func.count(),
            )
            .where(
                SignalModel.tenant_id == tenant_id,
                SignalModel.status.in_(_ON_SHOULDERS),
                SignalModel.opened_at <= older_than,
            )
            .group_by(SignalModel.owner_account_id)
        )
        return [
            (owner, int(ignored or 0), int(borne or 0))
            for owner, ignored, borne in (await self._session.execute(stmt)).all()
        ]

    async def ignored_ratio(
        self, *, tenant_id: UUID, older_than: datetime
    ) -> tuple[int, int]:
        stmt = select(
            func.count().filter(SignalModel.first_seen_at.is_(None)),
            func.count(),
        ).where(
            SignalModel.tenant_id == tenant_id,
            SignalModel.status.in_(_ON_SHOULDERS),
            SignalModel.opened_at <= older_than,
        )
        ignored, borne = (await self._session.execute(stmt)).one()
        return int(ignored or 0), int(borne or 0)

    async def human_traces(self, tenant_id: UUID) -> HumanTraces:
        """Un COUNT par nature d'acte. Cinq scalaires, lus une seule fois avant une purge."""
        mine = SignalModel.tenant_id == tenant_id
        counted = await self._session.execute(
            select(
                func.count().filter(SignalModel.first_seen_at.is_not(None)),
                func.count().filter(SignalModel.first_contact_at.is_not(None)),
                func.count().filter(SignalModel.closed_by_account_id.is_not(None)),
                func.count().filter(SignalModel.gestures_count > 0),
            ).where(mine)
        )
        seen, contacted, closed, gestures = counted.one()
        delivered = (
            await self._session.execute(
                select(func.count()).where(
                    CareMemoryModel.tenant_id == tenant_id,
                    CareMemoryModel.delivered_at.is_not(None),
                )
            )
        ).scalar_one()
        return HumanTraces(
            seen=int(seen or 0),
            contacted=int(contacted or 0),
            closed=int(closed or 0),
            gestures=int(gestures or 0),
            delivered_memories=int(delivered or 0),
        )

    async def purge_projected(self, tenant_id: UUID) -> None:
        await self._session.execute(
            delete(SignalModel).where(SignalModel.tenant_id == tenant_id)
        )
        await self._session.execute(
            delete(CareMemoryModel).where(CareMemoryModel.tenant_id == tenant_id)
        )
        await self._session.flush()


def _to_attempt(row: ContactAttemptModel) -> ContactAttempt:
    return ContactAttempt(
        id=row.id,
        tenant_id=row.tenant_id,
        signal_id=row.signal_id,
        by_account_id=row.by_account_id,
        channel=ContactChannel(row.channel),
        attempted_at=_aware(row.attempted_at),
        result=ContactResult(row.result),
        answered_at=_aware(row.answered_at),
        commitment=row.commitment,
    )


class SqlContactAttemptStore(ContactAttemptStore):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, attempt: ContactAttempt) -> None:
        self._session.add(
            ContactAttemptModel(
                id=attempt.id,
                tenant_id=attempt.tenant_id,
                signal_id=attempt.signal_id,
                by_account_id=attempt.by_account_id,
                channel=attempt.channel.value,
                attempted_at=attempt.attempted_at,
                result=attempt.result.value,
                answered_at=attempt.answered_at,
            )
        )
        await self._session.flush()

    async def get(self, attempt_id: UUID) -> ContactAttempt | None:
        row = await self._session.get(ContactAttemptModel, attempt_id)
        return _to_attempt(row) if row is not None else None

    async def save(self, attempt: ContactAttempt) -> None:
        row = await self._session.get(ContactAttemptModel, attempt.id)
        if row is None:
            return
        row.result = attempt.result.value
        row.answered_at = attempt.answered_at
        row.commitment = attempt.commitment
        await self._session.flush()

    async def purge_projected(self, tenant_id: UUID) -> None:
        await self._session.execute(
            delete(ContactAttemptModel).where(ContactAttemptModel.tenant_id == tenant_id)
        )
        await self._session.flush()

    async def record(
        self,
        *,
        attempt_id: UUID,
        subject_id: UUID,
        tenant_id: UUID,
        by_account_id: UUID,
        channel: str,
        at: datetime,
    ) -> None:
        if await self._session.get(ContactAttemptModel, attempt_id) is not None:
            return  # rejouer n'empile pas : l'identifiant vient du journal
        signal_id = await self._live_signal_id(subject_id, tenant_id)
        self._session.add(
            ContactAttemptModel(
                id=attempt_id,
                tenant_id=tenant_id,
                signal_id=signal_id,
                by_account_id=by_account_id,
                channel=channel,
                attempted_at=at,
                result=ContactResult.PENDING.value,
            )
        )
        await self._session.flush()

    async def _live_signal_id(self, subject_id: UUID, tenant_id: UUID) -> UUID:
        """Le cas vivant de cette personne — retrouvé maintenant, jamais lu du payload.

        Un rejeu recrée les cas avec de nouveaux identifiants : rattacher la tentative à celui
        d'origine la laisserait orpheline."""
        stmt = (
            select(SignalModel.id)
            .where(
                SignalModel.tenant_id == tenant_id,
                SignalModel.subject_id == subject_id,
                SignalModel.status.in_(_LIVE),
            )
            .order_by(SignalModel.opened_at)
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def resolve(
        self, *, attempt_id: UUID, result: str, at: datetime, commitment: str | None = None
    ) -> None:
        row = await self._session.get(ContactAttemptModel, attempt_id)
        if row is None:
            return
        attempt = _to_attempt(row)
        attempt.resolve(result=ContactResult(result), at=at, commitment=commitment)
        await self.save(attempt)

    async def count_not_reached(self, signal_id: UUID) -> int:
        stmt = select(func.count()).where(
            ContactAttemptModel.signal_id == signal_id,
            ContactAttemptModel.result == ContactResult.NOT_REACHED.value,
        )
        return int((await self._session.execute(stmt)).scalar_one())

    async def pending_for(
        self, *, account_id: UUID, tenant_id: UUID, since: datetime
    ) -> list[ContactAttempt]:
        stmt = select(ContactAttemptModel).where(
            ContactAttemptModel.tenant_id == tenant_id,
            ContactAttemptModel.by_account_id == account_id,
            ContactAttemptModel.result == ContactResult.PENDING.value,
            ContactAttemptModel.attempted_at >= since,
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_attempt(r) for r in rows]
