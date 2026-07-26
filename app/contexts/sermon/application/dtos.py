"""DTO applicatifs du module Sermon."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from app.contexts.sermon.domain.digest import SermonDigest


@dataclass(frozen=True)
class SermonDTO:
    id: UUID
    tenant_id: UUID
    author_account_id: UUID
    title: str
    reference: str | None
    source_kind: str  # text | pdf | pptx | audio
    raw_text: str
    preached_on: date
    status: str  # draft | approved | published
    created_at: datetime
    updated_at: datetime
    approved_at: datetime | None
    digest: SermonDigest | None  # le produit IA (résumé/capsules/Q&R), None avant digestion


@dataclass(frozen=True)
class CompanionCardDTO:
    """Une « carte » du compagnon — ce que le membre voit à chaque étape (déterministe)."""

    session_id: UUID
    stage: str  # attendance | consolidation | teaching | closing
    prompt: str  # question d'entrée, question de réflexion, point essentiel, ou mot de clôture
    guidance: str | None  # la réponse préparée (branche consolidation seulement)
    index: int  # position dans la branche (0-based)
    total: int  # nombre d'étapes de la branche
    done: bool  # la session est terminée
