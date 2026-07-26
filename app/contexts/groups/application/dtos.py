"""DTO applicatifs du contexte Groupes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class GroupDTO:
    id: UUID
    tenant_id: UUID
    name: str
    type: str
    status: str
    parent_group_id: UUID | None


@dataclass(frozen=True)
class GroupMemberDTO:
    group_id: UUID
    account_id: UUID
    status: str
    joined_at: datetime


@dataclass(frozen=True)
class LeadershipDTO:
    group_id: UUID
    account_id: UUID
    grade: str
    role: str
    role_assignment_id: UUID


@dataclass(frozen=True)
class MultiplicationDTO:
    mother_group_id: UUID
    daughter_group_id: UUID
    daughter_name: str
    generation: int
    moved_members: int
    new_leader_account_id: UUID


@dataclass(frozen=True)
class DaughterCellDTO:
    id: UUID
    name: str
    generation: int


@dataclass(frozen=True)
class CellReportDTO:
    group_id: UUID
    type: str
    generation: int
    active_member_count: int
    ready_to_multiply: bool
    daughters: list[DaughterCellDTO]


@dataclass(frozen=True)
class ChurchPlantDTO:
    source_group_id: UUID
    tenant_id: UUID
    parent_tenant_id: UUID
    owner_account_id: UUID
    owner_membership_id: UUID
    member_count: int  # appartenances re-pointées (owner compris)


@dataclass(frozen=True)
class InvitationDTO:
    id: UUID
    group_id: UUID
    code: str
    expires_at: datetime


@dataclass(frozen=True)
class JoinResultDTO:
    group_id: UUID
    group_name: str
    tenant_id: UUID
    enrolled_in_church: bool  # True si l'appartenance église a été créée par le lien
