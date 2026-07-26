"""Mappage agrégat → DTO (module Sermon)."""

from __future__ import annotations

from app.contexts.sermon.application.dtos import SermonDTO
from app.contexts.sermon.domain.aggregates import Sermon


def to_sermon_dto(s: Sermon) -> SermonDTO:
    return SermonDTO(
        id=s.id,
        tenant_id=s.tenant_id,
        author_account_id=s.author_account_id,
        title=s.title,
        reference=s.reference,
        source_kind=s.source_kind.value,
        raw_text=s.raw_text,
        preached_on=s.preached_on,
        status=s.status.value,
        created_at=s.created_at,
        updated_at=s.updated_at,
        approved_at=s.approved_at,
        digest=s.digest,
    )
