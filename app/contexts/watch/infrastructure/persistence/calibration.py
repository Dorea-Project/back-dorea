"""Dépôt SQLAlchemy des propositions de calibration.

Rien de subtil ici, sauf une règle qui vaut d'être lue : **une seule proposition en attente par
`(église, paramètre)`**. Une passe quotidienne empilerait sinon trente fois la même phrase, et
l'écran du pasteur deviendrait un endroit qu'on ferme sans lire.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.watch.calibration.ports import (
    AbsenceEvidence,
    AbsenceEvidenceReader,
    CalibrationProposalStore,
)
from app.contexts.watch.calibration.proposal import CalibrationProposal, ProposalStatus
from app.contexts.watch.domain.effects import CasePriority
from app.contexts.watch.domain.parameters import WatchParam
from app.contexts.watch.infrastructure.persistence.models import (
    CalibrationProposalModel,
    FactLedgerModel,
    SignalModel,
)


def _aware(dt):
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _to_domain(row: CalibrationProposalModel) -> CalibrationProposal:
    return CalibrationProposal(
        id=row.id,
        tenant_id=row.tenant_id,
        param=WatchParam(row.param),
        current=row.current_value,
        proposed=row.proposed_value,
        evidence=row.evidence,
        status=ProposalStatus(row.status),
        decided_by_account_id=row.decided_by_account_id,
        decided_at=_aware(row.decided_at),
    )


class SqlAbsenceEvidenceReader(AbsenceEvidenceReader):
    """Deux requêtes, pas une jointure sur du JSON.

    `source_refs` est une colonne JSON : la joindre au journal marcherait en Postgres et pas en
    SQLite, et une requête qui ne tourne que sur la base de production est une requête qu'on ne
    teste pas. On lit les cas, puis les faits qui les ont ouverts, et on recolle en Python — sur
    une fenêtre d'un mois, il n'y a rien à optimiser ici."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def absence_evidence(
        self, *, tenant_id: UUID, since: datetime
    ) -> list[AbsenceEvidence]:
        stmt = select(SignalModel.source_refs, SignalModel.outcome).where(
            SignalModel.tenant_id == tenant_id,
            SignalModel.origin == CasePriority.ABSENCE.value,
            SignalModel.opened_at >= since,
        )
        cases = [
            (refs or [], outcome)
            for refs, outcome in (await self._session.execute(stmt)).all()
        ]
        wanted = {UUID(refs[0]) for refs, _ in cases if refs}
        if not wanted:
            return []

        facts = select(FactLedgerModel.fact_id, FactLedgerModel.payload).where(
            FactLedgerModel.tenant_id == tenant_id,
            FactLedgerModel.fact_id.in_(wanted),
        )
        payloads = {
            fact_id: payload or {}
            for fact_id, payload in (await self._session.execute(facts)).all()
        }

        evidence: list[AbsenceEvidence] = []
        for refs, outcome in cases:
            payload = payloads.get(UUID(refs[0])) if refs else None
            if not payload or "occurrences" not in payload:
                # Un cas d'absence né d'autre chose qu'une échéance de veille — ou d'un fait
                # antérieur à `CheckFiredV1`. Il n'a pas de contrefactuel, on ne l'invente pas.
                continue
            evidence.append(
                AbsenceEvidence(
                    occurrences=int(payload.get("occurrences") or 0),
                    threshold=int(payload.get("threshold") or 0),
                    outcome=outcome,
                )
            )
        return evidence


class SqlCalibrationProposalStore(CalibrationProposalStore):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_all(
        self, proposals: list[CalibrationProposal]
    ) -> list[CalibrationProposal]:
        if not proposals:
            return []
        tenant_id = proposals[0].tenant_id
        stmt = select(CalibrationProposalModel.param).where(
            CalibrationProposalModel.tenant_id == tenant_id,
            CalibrationProposalModel.status == ProposalStatus.PENDING.value,
        )
        waiting = set((await self._session.execute(stmt)).scalars().all())

        kept: list[CalibrationProposal] = []
        for proposal in proposals:
            if proposal.param.value in waiting:
                continue
            waiting.add(proposal.param.value)
            self._session.add(
                CalibrationProposalModel(
                    id=proposal.id,
                    tenant_id=proposal.tenant_id,
                    param=proposal.param.value,
                    current_value=proposal.current,
                    proposed_value=proposal.proposed,
                    evidence=proposal.evidence,
                    status=proposal.status.value,
                )
            )
            kept.append(proposal)
        await self._session.flush()
        return kept

    async def pending(self, tenant_id: UUID) -> list[CalibrationProposal]:
        stmt = select(CalibrationProposalModel).where(
            CalibrationProposalModel.tenant_id == tenant_id,
            CalibrationProposalModel.status == ProposalStatus.PENDING.value,
        )
        return [_to_domain(r) for r in (await self._session.execute(stmt)).scalars()]

    async def get(
        self, *, proposal_id: UUID, tenant_id: UUID
    ) -> CalibrationProposal | None:
        stmt = select(CalibrationProposalModel).where(
            CalibrationProposalModel.id == proposal_id,
            CalibrationProposalModel.tenant_id == tenant_id,
        )
        row = (await self._session.execute(stmt)).scalars().first()
        return _to_domain(row) if row is not None else None

    async def save(self, proposal: CalibrationProposal) -> None:
        stmt = select(CalibrationProposalModel).where(
            CalibrationProposalModel.id == proposal.id,
            CalibrationProposalModel.tenant_id == proposal.tenant_id,
        )
        row = (await self._session.execute(stmt)).scalars().first()
        if row is None:
            return
        # Seule la décision est modifiable : ni le nombre proposé, ni la phrase qui le justifie.
        # Une preuve réécrite après coup ne prouve plus rien.
        row.status = proposal.status.value
        row.decided_by_account_id = proposal.decided_by_account_id
        row.decided_at = proposal.decided_at
