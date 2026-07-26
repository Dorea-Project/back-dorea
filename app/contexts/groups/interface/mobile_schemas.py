"""Schémas HTTP mobile du contexte Groupes (G-1b)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.contexts.groups.application.dtos import InvitationDTO, JoinResultDTO


class InvitationResponse(BaseModel):
    id: UUID
    group_id: UUID
    code: str = Field(description="À intégrer dans le lien partagé (deep-link mobile)")
    expires_at: datetime

    @classmethod
    def from_dto(cls, dto: InvitationDTO) -> InvitationResponse:
        return cls(id=dto.id, group_id=dto.group_id, code=dto.code, expires_at=dto.expires_at)


class JoinByCodeRequest(BaseModel):
    code: str = Field(examples=["Xa9kL2pQ7mZr"], description="Code du lien d'invitation")


class JoinResultResponse(BaseModel):
    group_id: UUID
    group_name: str
    tenant_id: UUID
    enrolled_in_church: bool

    @classmethod
    def from_dto(cls, dto: JoinResultDTO) -> JoinResultResponse:
        return cls(
            group_id=dto.group_id,
            group_name=dto.group_name,
            tenant_id=dto.tenant_id,
            enrolled_in_church=dto.enrolled_in_church,
        )
