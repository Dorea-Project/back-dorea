"""Adaptateur `CapsuleFeedPort` — publie les capsules du sermon **dans le fil** Annonces (S-2).

Chaque capsule → une **annonce église-entière** (type `sermon`, portée church, auteur = le pasteur).
Écrit **directement** via le dépôt Annonces (l'autorité vient déjà de `PUBLISH_SERMON` ; on ne
repasse pas par la commande d'annonce, que le pasteur n'a pas le droit d'appeler). Même patron que
les adaptateurs qui écrivent chez le voisin sans coupler les domaines.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.announcements.domain.aggregates import Announcement
from app.contexts.announcements.domain.enums import AnnouncementCategory
from app.contexts.announcements.infrastructure.persistence.repositories import (
    SqlAnnouncementRepository,
)
from app.contexts.sermon.application.ports import CapsuleFeedPort
from app.contexts.sermon.domain.digest import Capsule


class AnnouncementCapsuleFeedAdapter(CapsuleFeedPort):
    def __init__(self, session: AsyncSession) -> None:
        self._announcements = SqlAnnouncementRepository(session)

    async def publish_capsules(
        self, *, tenant_id: UUID, author_account_id: UUID, capsules: Sequence[Capsule]
    ) -> None:
        now = datetime.now(UTC)
        for capsule in capsules:
            announcement = Announcement.publish(
                id=uuid4(),
                tenant_id=tenant_id,
                category=AnnouncementCategory.SERMON,
                scope_group_id=None,  # église-entière
                title=capsule.title,
                body=capsule.body,
                author_account_id=author_account_id,
                now=now,
            )
            await self._announcements.add(announcement)
