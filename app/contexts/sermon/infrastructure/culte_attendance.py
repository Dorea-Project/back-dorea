"""Adaptateur `CulteAttendancePort` — pose une présence **déclarée** dans Présence (S-4).

Le « oui » du compagnon (« j'ai vécu le culte ») → une présence au **culte du jour**. On
**rejoint ou crée** la rencontre église-entière (`group_id = None`, type `service`) datée du
dimanche, puis on marque le membre présent, **source `declared`** — idempotent (une ligne par
personne et rencontre). Sermon écrit dans les tables de Présence sans coupler les domaines (même
patron que les adaptateurs d'audience d'Event qui lisent iam).

C'est l'axe **physique**, distinct de la Résonance : `declared` est la confiance la plus basse,
**additive**, elle n'éteint jamais une alerte. Un scan reste roi.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.attendance.domain.enums import (
    AttendanceMark,
    AttendanceSource,
    GatheringStatus,
    GatheringType,
)
from app.contexts.attendance.infrastructure.persistence.models import (
    AttendanceRecordModel,
    GatheringModel,
)
from app.contexts.sermon.application.ports import CulteAttendancePort


class SermonCulteAttendanceAdapter(CulteAttendancePort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def mark_declared_present(
        self, *, tenant_id: UUID, member_account_id: UUID, on_date: date, now: datetime
    ) -> None:
        gathering = await self._get_or_create_culte(tenant_id, on_date, member_account_id, now)
        # Idempotence : une seule présence par (rencontre, compte) — déclarer deux fois = pareil.
        existing = (
            await self._session.execute(
                select(AttendanceRecordModel.id).where(
                    AttendanceRecordModel.gathering_id == gathering.id,
                    AttendanceRecordModel.account_id == member_account_id,
                )
            )
        ).first()
        if existing is not None:
            return
        self._session.add(
            AttendanceRecordModel(
                id=uuid4(),
                gathering_id=gathering.id,
                account_id=member_account_id,
                mark=AttendanceMark.PRESENT.value,
                source=AttendanceSource.DECLARED.value,
                reason=None,
                recorded_at=now,
                recorded_by_account_id=member_account_id,  # le membre lui-même (déclaration)
            )
        )
        await self._session.flush()

    async def _get_or_create_culte(
        self, tenant_id: UUID, on_date: date, member_account_id: UUID, now: datetime
    ) -> GatheringModel:
        # Le culte église-entière du jour : minuit UTC → clé déterministe par (tenant, jour).
        scheduled_at = datetime.combine(on_date, time.min, tzinfo=UTC)
        gathering = (
            await self._session.execute(
                select(GatheringModel).where(
                    GatheringModel.tenant_id == tenant_id,
                    GatheringModel.group_id.is_(None),
                    GatheringModel.type == GatheringType.SERVICE.value,
                    GatheringModel.scheduled_at == scheduled_at,
                )
            )
        ).scalars().first()
        if gathering is not None:
            return gathering
        gathering = GatheringModel(
            id=uuid4(),
            tenant_id=tenant_id,
            group_id=None,  # église-entière (culte)
            type=GatheringType.SERVICE.value,
            title="Culte",
            scheduled_at=scheduled_at,
            status=GatheringStatus.OPEN.value,
            created_by_account_id=member_account_id,  # le premier déclarant ouvre le culte
            created_at=now,
            check_in_code=None,
            closed_at=None,
        )
        self._session.add(gathering)
        await self._session.flush()
        return gathering
