"""Backfill du ledger depuis les sujets d'annonce déjà écrits.

Les effets de veille posés **avant** le moteur n'ont pas de fait derrière eux. Sans ce script,
le ledger serait incomplet — et la première reprojection effacerait des neutralisations
légitimes sans savoir les reconstruire. On rejoue donc l'histoire connue : un fait par sujet
effectif, daté de l'événement.

Idempotent : `fact_id` est dérivé de `(annonce, personne)`, donc relancer ne duplique rien.
Le script **n'écrit pas** de neutralisation — il pose les faits, et l'intake en tire ce qu'il
faut, en réutilisant les mêmes gardes qu'en direct (idempotence par `source_ref`, prolongation
jamais cumul). Ce qui existe déjà est reconnu, pas recréé.

Usage :
    python -m scripts.backfill_watch_ledger            # toutes les églises
    python -m scripts.backfill_watch_ledger <tenant>   # une seule
"""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from app.contexts.announcements.application.watch_effects import build_fact
from app.contexts.announcements.infrastructure.persistence.models import AnnouncementModel
from app.contexts.announcements.infrastructure.persistence.repositories import (
    SqlAnnouncementRepository,
    SqlAnnouncementSubjectRepository,
)
from app.contexts.watch.interface.dependencies import build_intake
from app.core.database import async_session_factory


async def _backfill(tenant_id: UUID | None) -> tuple[int, int]:
    seen = admitted = 0
    async with async_session_factory() as session:
        intake = build_intake(session)
        announcements = SqlAnnouncementRepository(session)
        subjects = SqlAnnouncementSubjectRepository(session)

        stmt = select(AnnouncementModel.id).where(AnnouncementModel.tenant_id.isnot(None))
        if tenant_id is not None:
            stmt = stmt.where(AnnouncementModel.tenant_id == tenant_id)
        # Ordre de publication : le passé est rejoué dans le sens où il s'est produit.
        stmt = stmt.order_by(AnnouncementModel.published_at)

        for announcement_id in (await session.execute(stmt)).scalars().all():
            announcement = await announcements.get(announcement_id)
            if announcement is None:
                continue
            for subject in await subjects.list_for(announcement_id):
                if not subject.is_effective:
                    continue  # accord attendu ou refusé : il n'y a jamais eu d'effet
                seen += 1
                fact = build_fact(
                    announcement,
                    subject,
                    # On date l'ingestion du rattachement du sujet, pas de maintenant : c'est
                    # bien à ce moment-là que le système a appris la chose.
                    recorded_at=subject.attached_at or datetime.now(UTC),
                )
                result = await intake.submit(fact)
                if result.accepted:
                    admitted += 1

        await session.commit()
    return seen, admitted


async def main() -> None:
    tenant_id = UUID(sys.argv[1]) if len(sys.argv) > 1 else None
    seen, admitted = await _backfill(tenant_id)
    scope = str(tenant_id) if tenant_id else "toutes les églises"
    print(f"Backfill {scope} : {seen} sujets parcourus, {admitted} faits ajoutés au ledger.")


if __name__ == "__main__":
    asyncio.run(main())
