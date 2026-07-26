"""Schémas HTTP du contexte Présence (M6-0)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.contexts.attendance.application.dtos import (
    CareListDTO,
    CellHealthDTO,
    ChurchDashboardDTO,
    ConvertVisitorResult,
    GatheringDTO,
    GroupEffectifDTO,
    GroupPulseDTO,
    GroupTrendDTO,
    GroupVitalsDTO,
    LineageNodeDTO,
    MemberTrajectoryDTO,
    MultiplicationTreeDTO,
    PlannedAbsenceDTO,
    RosterDTO,
    SelfCheckInDTO,
    VisitorDTO,
)
from app.contexts.attendance.domain.enums import AbsenceReason, GatheringType


class CreateGatheringRequest(BaseModel):
    type: GatheringType = Field(description="meeting | training | service | event")
    scheduled_at: datetime = Field(description="Date/heure de la rencontre")
    title: str | None = Field(default=None, examples=["Réunion de cellule — jeudi"])


class GatheringResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    group_id: UUID | None
    type: str
    title: str | None
    scheduled_at: datetime
    status: str
    check_in_code: str | None = Field(description="Code à afficher pour le self-check-in")

    @classmethod
    def from_dto(cls, dto: GatheringDTO) -> GatheringResponse:
        return cls(
            id=dto.id,
            tenant_id=dto.tenant_id,
            group_id=dto.group_id,
            type=dto.type,
            title=dto.title,
            scheduled_at=dto.scheduled_at,
            status=dto.status,
            check_in_code=dto.check_in_code,
        )


class SelfCheckInRequest(BaseModel):
    code: str = Field(examples=["K7P2QM"], description="Code de séance affiché par le responsable")


class SelfCheckInResponse(BaseModel):
    gathering_id: UUID
    group_id: UUID | None
    title: str | None

    @classmethod
    def from_dto(cls, dto: SelfCheckInDTO) -> SelfCheckInResponse:
        return cls(gathering_id=dto.gathering_id, group_id=dto.group_id, title=dto.title)


class _RosterEntry(BaseModel):
    account_id: UUID
    present: bool
    excused: bool  # absent = ni présent ni excusé
    rsvp: bool  # a dit « je viens » (pré-signal M8)


class RosterResponse(BaseModel):
    gathering_id: UUID
    status: str
    total_expected: int
    present_count: int
    excused_count: int
    rsvp_count: int
    entries: list[_RosterEntry]

    @classmethod
    def from_dto(cls, dto: RosterDTO) -> RosterResponse:
        return cls(
            gathering_id=dto.gathering_id,
            status=dto.status,
            total_expected=dto.total_expected,
            present_count=dto.present_count,
            excused_count=dto.excused_count,
            rsvp_count=dto.rsvp_count,
            entries=[
                _RosterEntry(
                    account_id=e.account_id, present=e.present, excused=e.excused, rsvp=e.rsvp
                )
                for e in dto.entries
            ],
        )


class DeclareAbsenceRequest(BaseModel):
    reason: AbsenceReason = Field(
        description="sick | travel | work | family | studies | unavailable | moved | other"
    )
    from_date: datetime = Field(description="Début de la période d'absence")
    to_date: datetime = Field(description="Fin de la période d'absence")
    note: str | None = Field(default=None, description="Note libre facultative (surtout 'other')")


class PlannedAbsenceResponse(BaseModel):
    id: UUID
    account_id: UUID
    tenant_id: UUID
    reason: str
    gravity: str
    note: str | None
    from_date: datetime
    to_date: datetime

    @classmethod
    def from_dto(cls, dto: PlannedAbsenceDTO) -> PlannedAbsenceResponse:
        return cls(
            id=dto.id,
            account_id=dto.account_id,
            tenant_id=dto.tenant_id,
            reason=dto.reason,
            gravity=dto.gravity,
            note=dto.note,
            from_date=dto.from_date,
            to_date=dto.to_date,
        )


class _PulseEntry(BaseModel):
    account_id: UUID
    state: str
    missed: int
    needs_care: bool
    last_present_at: datetime | None


class GroupPulseResponse(BaseModel):
    group_id: UUID
    total: int
    needs_care_count: int
    entries: list[_PulseEntry]

    @classmethod
    def from_dto(cls, dto: GroupPulseDTO) -> GroupPulseResponse:
        return cls(
            group_id=dto.group_id,
            total=dto.total,
            needs_care_count=dto.needs_care_count,
            entries=[
                _PulseEntry(
                    account_id=e.account_id,
                    state=e.state,
                    missed=e.missed,
                    needs_care=e.needs_care,
                    last_present_at=e.last_present_at,
                )
                for e in dto.entries
            ],
        )


class _ReviewCandidate(BaseModel):
    account_id: UUID
    reason: str


class GroupEffectifResponse(BaseModel):
    group_id: UUID
    total_members: int
    active_count: int
    at_risk_count: int
    shared_count: int
    review_candidates: list[_ReviewCandidate]

    @classmethod
    def from_dto(cls, dto: GroupEffectifDTO) -> GroupEffectifResponse:
        return cls(
            group_id=dto.group_id,
            total_members=dto.total_members,
            active_count=dto.active_count,
            at_risk_count=dto.at_risk_count,
            shared_count=dto.shared_count,
            review_candidates=[
                _ReviewCandidate(account_id=c.account_id, reason=c.reason)
                for c in dto.review_candidates
            ],
        )


class _CareEntry(BaseModel):
    account_id: UUID
    group_id: UUID
    group_name: str
    state: str
    missed: int
    last_present_at: datetime | None


class CareListResponse(BaseModel):
    tenant_id: UUID
    count: int
    entries: list[_CareEntry]

    @classmethod
    def from_dto(cls, dto: CareListDTO) -> CareListResponse:
        return cls(
            tenant_id=dto.tenant_id,
            count=dto.count,
            entries=[
                _CareEntry(
                    account_id=e.account_id,
                    group_id=e.group_id,
                    group_name=e.group_name,
                    state=e.state,
                    missed=e.missed,
                    last_present_at=e.last_present_at,
                )
                for e in dto.entries
            ],
        )


class CellHealthResponse(BaseModel):
    group_id: UUID
    type: str
    roster_count: int
    active_count: int
    ready_to_multiply: bool

    @classmethod
    def from_dto(cls, dto: CellHealthDTO) -> CellHealthResponse:
        return cls(
            group_id=dto.group_id,
            type=dto.type,
            roster_count=dto.roster_count,
            active_count=dto.active_count,
            ready_to_multiply=dto.ready_to_multiply,
        )


class GroupVitalsResponse(BaseModel):
    group_id: UUID
    name: str
    type: str
    status: str
    generation: int
    roster_count: int
    active_count: int
    at_risk_count: int
    shared_count: int
    review_count: int
    ready_to_multiply: bool

    @classmethod
    def from_dto(cls, dto: GroupVitalsDTO) -> GroupVitalsResponse:
        return cls(
            group_id=dto.group_id,
            name=dto.name,
            type=dto.type,
            status=dto.status,
            generation=dto.generation,
            roster_count=dto.roster_count,
            active_count=dto.active_count,
            at_risk_count=dto.at_risk_count,
            shared_count=dto.shared_count,
            review_count=dto.review_count,
            ready_to_multiply=dto.ready_to_multiply,
        )


class ChurchDashboardResponse(BaseModel):
    tenant_id: UUID
    groups_count: int
    cells_ready_to_multiply: int
    members_needing_care: int
    groups: list[GroupVitalsResponse]

    @classmethod
    def from_dto(cls, dto: ChurchDashboardDTO) -> ChurchDashboardResponse:
        return cls(
            tenant_id=dto.tenant_id,
            groups_count=dto.groups_count,
            cells_ready_to_multiply=dto.cells_ready_to_multiply,
            members_needing_care=dto.members_needing_care,
            groups=[GroupVitalsResponse.from_dto(g) for g in dto.groups],
        )


class _TrendPoint(BaseModel):
    as_of: datetime
    roster_count: int
    active_count: int
    at_risk_count: int


class GroupTrendResponse(BaseModel):
    group_id: UUID
    points: list[_TrendPoint]

    @classmethod
    def from_dto(cls, dto: GroupTrendDTO) -> GroupTrendResponse:
        return cls(
            group_id=dto.group_id,
            points=[
                _TrendPoint(
                    as_of=p.as_of,
                    roster_count=p.roster_count,
                    active_count=p.active_count,
                    at_risk_count=p.at_risk_count,
                )
                for p in dto.points
            ],
        )


class _TrajectoryPoint(BaseModel):
    gathering_id: UUID
    scheduled_at: datetime
    outcome: str  # present | excused | absent
    title: str | None


class MemberTrajectoryResponse(BaseModel):
    account_id: UUID
    group_id: UUID
    state: str
    needs_care: bool
    missed: int
    last_present_at: datetime | None
    active_elsewhere: bool
    current_absence_reason: str | None
    current_absence_gravity: str | None
    points: list[_TrajectoryPoint]

    @classmethod
    def from_dto(cls, dto: MemberTrajectoryDTO) -> MemberTrajectoryResponse:
        return cls(
            account_id=dto.account_id,
            group_id=dto.group_id,
            state=dto.state,
            needs_care=dto.needs_care,
            missed=dto.missed,
            last_present_at=dto.last_present_at,
            active_elsewhere=dto.active_elsewhere,
            current_absence_reason=dto.current_absence_reason,
            current_absence_gravity=dto.current_absence_gravity,
            points=[
                _TrajectoryPoint(
                    gathering_id=p.gathering_id,
                    scheduled_at=p.scheduled_at,
                    outcome=p.outcome,
                    title=p.title,
                )
                for p in dto.points
            ],
        )


class LineageNode(BaseModel):
    vitals: GroupVitalsResponse
    children: list[LineageNode]

    @classmethod
    def from_dto(cls, dto: LineageNodeDTO) -> LineageNode:
        return cls(
            vitals=GroupVitalsResponse.from_dto(dto.vitals),
            children=[LineageNode.from_dto(c) for c in dto.children],
        )


class MultiplicationTreeResponse(BaseModel):
    tenant_id: UUID
    cells_count: int
    max_generation: int
    roots: list[LineageNode]

    @classmethod
    def from_dto(cls, dto: MultiplicationTreeDTO) -> MultiplicationTreeResponse:
        return cls(
            tenant_id=dto.tenant_id,
            cells_count=dto.cells_count,
            max_generation=dto.max_generation,
            roots=[LineageNode.from_dto(r) for r in dto.roots],
        )


class AddVisitorRequest(BaseModel):
    name: str = Field(examples=["Koffi (ami de Awa)"])
    phone: str | None = Field(default=None, examples=["+2250700000099"])


class VisitorResponse(BaseModel):
    id: UUID
    gathering_id: UUID
    name: str
    phone: str | None

    @classmethod
    def from_dto(cls, dto: VisitorDTO) -> VisitorResponse:
        return cls(id=dto.id, gathering_id=dto.gathering_id, name=dto.name, phone=dto.phone)


class ConvertVisitorRequest(BaseModel):
    phone: str | None = Field(
        default=None,
        description="Téléphone du membre (requis si le visiteur n'en avait pas)",
        examples=["+2250700000099"],
    )
    first_name: str | None = Field(default=None)
    last_name: str | None = Field(default=None)


class ConvertVisitorResponse(BaseModel):
    account_id: UUID
    tenant_id: UUID
    group_id: UUID
    status: str
    reused_account: bool

    @classmethod
    def from_dto(cls, dto: ConvertVisitorResult) -> ConvertVisitorResponse:
        return cls(
            account_id=dto.account_id,
            tenant_id=dto.tenant_id,
            group_id=dto.group_id,
            status=dto.status,
            reused_account=dto.reused_account,
        )
