"""Schémas HTTP du contexte Mission (M9)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.contexts.mission.application.dtos import (
    IntegrateSeekerResult,
    MissionCardDTO,
    MissionLinkDTO,
    MySeekersDTO,
    SeekerDTO,
    VerseCardDTO,
)
from app.contexts.mission.domain.enums import SeekerOutcome, SeekerReaction


class CreateLinkRequest(BaseModel):
    # Une carte = message et/ou image (au moins l'un). Le message peut être un texte propre
    # ou le verset renvoyé par /generate-card ; l'image, une photo uploadée ou la carte-verset.
    message: str = Field(default="", examples=["Viens découvrir l'amour de Dieu avec nous"])
    media_urls: list[str] | None = Field(default=None, description="Image(s) de la carte (URL)")
    place_label: str | None = Field(default=None, examples=["Temple AD, Yopougon"])
    latitude: float | None = Field(default=None)
    longitude: float | None = Field(default=None)


class MissionLinkResponse(BaseModel):
    id: UUID
    code: str
    inviter_kind: str
    message: str
    media_urls: list[str]
    place_label: str | None
    latitude: float | None
    longitude: float | None
    expires_at: datetime
    revoked: bool

    @classmethod
    def from_dto(cls, dto: MissionLinkDTO) -> MissionLinkResponse:
        return cls(
            id=dto.id,
            code=dto.code,
            inviter_kind=dto.inviter_kind,
            message=dto.message,
            media_urls=dto.media_urls,
            place_label=dto.place_label,
            latitude=dto.latitude,
            longitude=dto.longitude,
            expires_at=dto.expires_at,
            revoked=dto.revoked,
        )


class MissionCardResponse(BaseModel):
    inviter_label: str
    inviter_kind: str
    church_label: str
    message: str
    media_urls: list[str]
    place_label: str | None
    latitude: float | None
    longitude: float | None
    active: bool

    @classmethod
    def from_dto(cls, dto: MissionCardDTO) -> MissionCardResponse:
        return cls(
            inviter_label=dto.inviter_label,
            inviter_kind=dto.inviter_kind,
            church_label=dto.church_label,
            message=dto.message,
            media_urls=dto.media_urls,
            place_label=dto.place_label,
            latitude=dto.latitude,
            longitude=dto.longitude,
            active=dto.active,
        )


class GenerateCardRequest(BaseModel):
    query: str = Field(
        examples=["le verset ou Dieu a tellement aimé le monde", "jean 3 vers 16"],
        description="Citation approximative / mal décrite du verset — l'IA retrouve la référence.",
    )


class VerseCardResponse(BaseModel):
    reference: str  # « Jean 3.16 » reconnu par l'IA
    text: str  # le texte EXACT (Bible canonique)
    image_url: str  # la carte designée, prête à devenir le média du lien

    @classmethod
    def from_dto(cls, dto: VerseCardDTO) -> VerseCardResponse:
        return cls(reference=dto.reference, text=dto.text, image_url=dto.image_url)


class ReactRequest(BaseModel):
    kind: SeekerReaction = Field(description="touched | edified | amen")


class AcceptRequest(BaseModel):
    name: str = Field(examples=["Koffi"])
    phone: str | None = Field(default=None, examples=["+2250700000000"])


class AcceptResponse(BaseModel):
    seeker_id: UUID


class _Seeker(BaseModel):
    id: UUID
    name: str
    status: str
    created_at: datetime
    accompanied_by: UUID | None = None
    accompanied_at: datetime | None = None

    @classmethod
    def from_dto(cls, s: SeekerDTO) -> _Seeker:
        return cls(
            id=s.id,
            name=s.name,
            status=s.status,
            created_at=s.created_at,
            accompanied_by=s.accompanied_by,
            accompanied_at=s.accompanied_at,
        )


class SeekerResponse(_Seeker):
    """Un chercheur après une transition (accompagnement / clôture)."""


class CloseSeekerRequest(BaseModel):
    """**Comment** le parcours s'arrête. Optionnel : sans corps, le comportement d'hier.

    `known_and_followed` est la porte qui manquait — « elle vient, on la connaît par son nom,
    elle ne veut pas encore de cellule ». C'est une sortie **réussie**, pas un abandon. Sans
    elle, le module reste un entonnoir de conversion quelle que soit la propreté de
    l'architecture en dessous."""

    outcome: SeekerOutcome = SeekerOutcome.UNREACHABLE_ARCHIVED


class IntegrateRequest(BaseModel):
    # Téléphone requis pour l'identité membre — pris du Seeker s'il l'a laissé, sinon fourni ici.
    phone: str | None = Field(default=None, examples=["+2250700000000"])
    first_name: str | None = Field(default=None, examples=["Koffi"])
    last_name: str | None = Field(default=None)


class IntegrateResponse(BaseModel):
    account_id: UUID
    tenant_id: UUID
    group_id: UUID | None
    membership_status: str
    reused_account: bool
    seeker_status: str

    @classmethod
    def from_result(cls, r: IntegrateSeekerResult) -> IntegrateResponse:
        return cls(
            account_id=r.account_id,
            tenant_id=r.tenant_id,
            group_id=r.group_id,
            membership_status=r.membership_status,
            reused_account=r.reused_account,
            seeker_status=r.seeker_status,
        )


class MySeekersResponse(BaseModel):
    total: int
    seekers: list[_Seeker]
    reaction_counts: dict[str, int]

    @classmethod
    def from_dto(cls, dto: MySeekersDTO) -> MySeekersResponse:
        return cls(
            total=dto.total,
            seekers=[_Seeker.from_dto(s) for s in dto.seekers],
            reaction_counts=dto.reaction_counts,
        )
