"""Schémas HTTP du module Sermon."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.contexts.sermon.application.dtos import CompanionCardDTO, SermonDTO
from app.contexts.sermon.domain.digest import SermonDigest


class DepositSermonBody(BaseModel):
    title: str = Field(examples=["L'amour qui pardonne"])
    content: str = Field(description="Le texte / les notes du sermon (S-0 : texte)")
    preached_on: date = Field(description="Le dimanche (culte) concerné")
    reference: str | None = Field(default=None, examples=["Luc 15.11-32"])


class CapsuleView(BaseModel):
    title: str
    body: str


class CompanionQuestionView(BaseModel):
    prompt: str
    guidance: str


class DigestView(BaseModel):
    """Le brouillon IA que le pasteur relit avant d'approuver."""

    summary: str
    key_points: list[str]
    capsules: list[CapsuleView]
    questions: list[CompanionQuestionView]

    @classmethod
    def from_digest(cls, d: SermonDigest) -> DigestView:
        return cls(
            summary=d.summary,
            key_points=list(d.key_points),
            capsules=[CapsuleView(title=c.title, body=c.body) for c in d.capsules],
            questions=[
                CompanionQuestionView(prompt=q.prompt, guidance=q.guidance) for q in d.questions
            ],
        )


class SermonView(BaseModel):
    id: UUID
    tenant_id: UUID
    author_account_id: UUID
    title: str
    reference: str | None
    source_kind: str
    raw_text: str
    preached_on: date
    status: str
    created_at: datetime
    updated_at: datetime
    approved_at: datetime | None
    digest: DigestView | None

    @classmethod
    def from_dto(cls, d: SermonDTO) -> SermonView:
        return cls(
            id=d.id,
            tenant_id=d.tenant_id,
            author_account_id=d.author_account_id,
            title=d.title,
            reference=d.reference,
            source_kind=d.source_kind,
            raw_text=d.raw_text,
            preached_on=d.preached_on,
            status=d.status,
            created_at=d.created_at,
            updated_at=d.updated_at,
            approved_at=d.approved_at,
            digest=DigestView.from_digest(d.digest) if d.digest is not None else None,
        )


class SermonListView(BaseModel):
    total: int
    sermons: list[SermonView]

    @classmethod
    def from_dtos(cls, dtos: list[SermonDTO]) -> SermonListView:
        return cls(total=len(dtos), sermons=[SermonView.from_dto(d) for d in dtos])


class AnswerAttendanceBody(BaseModel):
    attended: bool = Field(description="As-tu vécu le culte aujourd'hui ? (oui / non)")


class CompanionCardView(BaseModel):
    """Une étape du compagnon — ce que le membre voit (déterministe, jamais d'IA au runtime)."""

    session_id: UUID
    stage: str
    prompt: str
    guidance: str | None
    index: int
    total: int
    done: bool

    @classmethod
    def from_dto(cls, d: CompanionCardDTO) -> CompanionCardView:
        return cls(
            session_id=d.session_id,
            stage=d.stage,
            prompt=d.prompt,
            guidance=d.guidance,
            index=d.index,
            total=d.total,
            done=d.done,
        )


# R0 — `DepositGratitudeBody` et `GratitudeDepositedView` ont suivi la commande dans `watch`.
# L'alias déprécié de `mobile_router` les y importe : **un seul schéma pour deux URL**, sinon les
# deux versions divergeraient et le client verrait deux contrats pour un même geste.
