"""Schémas HTTP du contexte Groupes (projection des DTO applicatifs)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.contexts.groups.application.dtos import (
    CellReportDTO,
    ChurchPlantDTO,
    GroupDTO,
    GroupMemberDTO,
    LeadershipDTO,
    MultiplicationDTO,
)
from app.contexts.groups.domain.enums import GroupStatus, GroupType
from app.contexts.groups.domain.leadership import GroupLeadershipGrade


class CreateGroupRequest(BaseModel):
    name: str = Field(examples=["Jeunesse"])
    type: GroupType = Field(description="cellule | ministere | classe")
    parent_group_id: UUID | None = Field(
        default=None,
        description="Nul = groupe racine (Owner/Admin) ; sinon sous-groupe (responsable scopé)",
    )


class GroupResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    type: str
    status: str
    parent_group_id: UUID | None

    @classmethod
    def from_dto(cls, dto: GroupDTO) -> GroupResponse:
        return cls(
            id=dto.id,
            tenant_id=dto.tenant_id,
            name=dto.name,
            type=dto.type,
            status=dto.status,
            parent_group_id=dto.parent_group_id,
        )


class AddGroupMemberRequest(BaseModel):
    account_id: UUID = Field(description="Compte à rattacher (membre existant de l'église)")


class GroupMemberResponse(BaseModel):
    group_id: UUID
    account_id: UUID
    status: str
    joined_at: datetime

    @classmethod
    def from_dto(cls, dto: GroupMemberDTO) -> GroupMemberResponse:
        return cls(
            group_id=dto.group_id,
            account_id=dto.account_id,
            status=dto.status,
            joined_at=dto.joined_at,
        )


class ModifyGroupRequest(BaseModel):
    name: str | None = Field(default=None, examples=["Jeunesse (rebaptisée)"])
    status: GroupStatus | None = Field(default=None, description="active | dormant")


class AppointLeadershipRequest(BaseModel):
    account_id: UUID = Field(description="Compte à nommer (membre existant de l'église)")
    grade: GroupLeadershipGrade = Field(
        description="leader (responsable, cap 6) | in_training (responsable-en-formation)"
    )


class RevokeLeadershipRequest(BaseModel):
    account_id: UUID
    grade: GroupLeadershipGrade = Field(description="leader | in_training")


class LeadershipResponse(BaseModel):
    group_id: UUID
    account_id: UUID
    grade: str
    role: str
    role_assignment_id: UUID

    @classmethod
    def from_dto(cls, dto: LeadershipDTO) -> LeadershipResponse:
        return cls(
            group_id=dto.group_id,
            account_id=dto.account_id,
            grade=dto.grade,
            role=dto.role,
            role_assignment_id=dto.role_assignment_id,
        )


class MultiplyCellRequest(BaseModel):
    daughter_name: str = Field(examples=["Famille de Koffi (fille)"])
    new_leader_account_id: UUID = Field(description="Futur responsable de la fille (le Timothée)")
    member_account_ids: list[UUID] = Field(
        default_factory=list, description="Membres de la mère à emmener vers la fille"
    )


class MultiplicationResponse(BaseModel):
    mother_group_id: UUID
    daughter_group_id: UUID
    daughter_name: str
    generation: int
    moved_members: int
    new_leader_account_id: UUID

    @classmethod
    def from_dto(cls, dto: MultiplicationDTO) -> MultiplicationResponse:
        return cls(
            mother_group_id=dto.mother_group_id,
            daughter_group_id=dto.daughter_group_id,
            daughter_name=dto.daughter_name,
            generation=dto.generation,
            moved_members=dto.moved_members,
            new_leader_account_id=dto.new_leader_account_id,
        )


class PromoteToChurchRequest(BaseModel):
    church_name: str = Field(examples=["Église Bethel Cocody"])
    owner_account_id: UUID = Field(description="Futur Owner (membre actif de l'église source)")


class ChurchPlantResponse(BaseModel):
    source_group_id: UUID
    tenant_id: UUID
    parent_tenant_id: UUID
    owner_account_id: UUID
    owner_membership_id: UUID
    member_count: int

    @classmethod
    def from_dto(cls, dto: ChurchPlantDTO) -> ChurchPlantResponse:
        return cls(
            source_group_id=dto.source_group_id,
            tenant_id=dto.tenant_id,
            parent_tenant_id=dto.parent_tenant_id,
            owner_account_id=dto.owner_account_id,
            owner_membership_id=dto.owner_membership_id,
            member_count=dto.member_count,
        )


class _DaughterCell(BaseModel):
    id: UUID
    name: str
    generation: int


class CellReportResponse(BaseModel):
    group_id: UUID
    type: str
    generation: int
    active_member_count: int
    ready_to_multiply: bool
    daughters: list[_DaughterCell]

    @classmethod
    def from_dto(cls, dto: CellReportDTO) -> CellReportResponse:
        return cls(
            group_id=dto.group_id,
            type=dto.type,
            generation=dto.generation,
            active_member_count=dto.active_member_count,
            ready_to_multiply=dto.ready_to_multiply,
            daughters=[
                _DaughterCell(id=d.id, name=d.name, generation=d.generation)
                for d in dto.daughters
            ],
        )
