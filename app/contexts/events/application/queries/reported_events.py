"""Requête `ListReportedEvents` — la file de revue de la Plateforme.

Les événements **publiés** qui ont récolté des signalements, du plus signalé au moins signalé —
pour que la Plateforme décide (retrait ou non).
"""

from __future__ import annotations

from app.contexts.events.application.dtos import ReportedEventDTO
from app.contexts.events.domain.enums import EventStatus
from app.contexts.events.domain.repositories import (
    EventReportRepository,
    EventRepository,
)


class ListReportedEvents:
    def __init__(
        self, events: EventRepository, reports: EventReportRepository
    ) -> None:
        self._events = events
        self._reports = reports

    async def execute(self) -> list[ReportedEventDTO]:
        counts = await self._reports.counts_by_event()
        out: list[ReportedEventDTO] = []
        for event_id, count in counts.items():
            event = await self._events.get(event_id)
            if event is None or event.status is not EventStatus.PUBLISHED:
                continue  # déjà retiré / annulé → hors file
            out.append(
                ReportedEventDTO(
                    id=event.id,
                    tenant_id=event.tenant_id,
                    author_account_id=event.author_account_id,
                    title=event.title,
                    scope=event.scope.value,
                    status=event.status.value,
                    starts_at=event.starts_at,
                    report_count=count,
                )
            )
        out.sort(key=lambda r: r.report_count, reverse=True)  # les plus signalés d'abord
        return out
