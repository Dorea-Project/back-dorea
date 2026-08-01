"""Schémas Pydantic de la surface HTTP IAM (projection des DTO applicatifs)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.contexts.iam.application.dtos import (
    BulkEnrollResult,
    ChurchInvitationDTO,
    CloseMembershipResult,
    EnrollInvitedMemberResult,
    EnrollMemberResult,
    JoinChurchResult,
    MembershipStatusDTO,
    RevokeRoleResult,
    TransferDTO,
    TransferListDTO,
    TransitionResult,
)
from app.contexts.iam.domain.birthday import DEFAULT_SCOPE, BirthdayScope
from app.contexts.iam.domain.enums import (
    MembershipClosureReason,
    MembershipTransitionEvent,
    RoleCode,
)


class EnrollMemberRequest(BaseModel):
    role: RoleCode = Field(description="Rôle enrôlé (pastor/admin par l'Owner ; team par l'Admin)")
    phone_number: str = Field(examples=["+2250700000050"])
    group_id: UUID | None = Field(
        default=None, description="Obligatoire pour group_leader (portée du groupe)"
    )
    first_name: str | None = Field(default=None, examples=["Paul"])
    last_name: str | None = Field(default=None)


class EnrollMemberResponse(BaseModel):
    account_id: UUID
    membership_id: UUID
    role: str
    group_id: UUID | None

    @classmethod
    def from_result(cls, result: EnrollMemberResult) -> EnrollMemberResponse:
        return cls(
            account_id=result.account_id,
            membership_id=result.membership_id,
            role=result.role,
            group_id=result.group_id,
        )


class EnrollInvitedMemberRequest(BaseModel):
    phone_number: str = Field(examples=["+2250700000070"])
    first_name: str | None = Field(default=None, examples=["Awa"])
    last_name: str | None = Field(default=None)


class ImportMemberRow(BaseModel):
    phone_number: str
    first_name: str | None = None
    last_name: str | None = None


class BulkEnrollRequest(BaseModel):
    members: list[ImportMemberRow] = Field(description="Liste des fidèles à importer (invited)")


class _EnrolledRow(BaseModel):
    phone_number: str
    account_id: UUID


class _FailedRow(BaseModel):
    phone_number: str
    reason: str


class BulkEnrollResponse(BaseModel):
    enrolled_count: int
    failed_count: int
    enrolled: list[_EnrolledRow]
    failed: list[_FailedRow]

    @classmethod
    def from_result(cls, result: BulkEnrollResult) -> BulkEnrollResponse:
        return cls(
            enrolled_count=len(result.enrolled),
            failed_count=len(result.failed),
            enrolled=[
                _EnrolledRow(phone_number=r.phone_number, account_id=r.account_id)
                for r in result.enrolled
            ],
            failed=[
                _FailedRow(phone_number=r.phone_number, reason=r.reason) for r in result.failed
            ],
        )


class EnrollInvitedMemberResponse(BaseModel):
    account_id: UUID
    membership_id: UUID
    status: str

    @classmethod
    def from_result(cls, result: EnrollInvitedMemberResult) -> EnrollInvitedMemberResponse:
        return cls(
            account_id=result.account_id,
            membership_id=result.membership_id,
            status=result.status,
        )


class TransitionRequest(BaseModel):
    event: MembershipTransitionEvent = Field(
        description="Événement de transition (ex. qualify_sympathizer, confirm_member)"
    )


class TransitionResponse(BaseModel):
    membership_id: UUID
    status: str
    previous_status: str

    @classmethod
    def from_result(cls, result: TransitionResult) -> TransitionResponse:
        return cls(
            membership_id=result.membership_id,
            status=result.status,
            previous_status=result.previous_status,
        )


class RevokeRoleRequest(BaseModel):
    role: RoleCode
    group_id: UUID | None = Field(default=None, description="Requis pour group_leader")


class RevokeRoleResponse(BaseModel):
    membership_id: UUID
    role: str
    group_id: UUID | None

    @classmethod
    def from_result(cls, result: RevokeRoleResult) -> RevokeRoleResponse:
        return cls(membership_id=result.membership_id, role=result.role, group_id=result.group_id)


class CloseMembershipRequest(BaseModel):
    closure_reason: MembershipClosureReason


class CloseMembershipResponse(BaseModel):
    membership_id: UUID
    status: str
    closure_reason: str

    @classmethod
    def from_result(cls, result: CloseMembershipResult) -> CloseMembershipResponse:
        return cls(
            membership_id=result.membership_id,
            status=result.status,
            closure_reason=result.closure_reason,
        )


class RequestTransferRequest(BaseModel):
    account_id: UUID = Field(description="Le membre à transférer (identité globale)")
    from_tenant_id: UUID = Field(description="Église source (celle qui devra libérer)")
    to_group_id: UUID | None = Field(
        default=None, description="Cellule d'accueil optionnelle dans l'église destination"
    )


class TransferResponse(BaseModel):
    id: UUID
    account_id: UUID
    from_tenant_id: UUID
    to_tenant_id: UUID
    to_group_id: UUID | None
    status: str
    requested_at: datetime
    resolved_at: datetime | None

    @classmethod
    def from_dto(cls, dto: TransferDTO) -> TransferResponse:
        return cls(
            id=dto.id,
            account_id=dto.account_id,
            from_tenant_id=dto.from_tenant_id,
            to_tenant_id=dto.to_tenant_id,
            to_group_id=dto.to_group_id,
            status=dto.status,
            requested_at=dto.requested_at,
            resolved_at=dto.resolved_at,
        )


class TransferListResponse(BaseModel):
    tenant_id: UUID
    incoming: list[TransferResponse]  # on est la source : à accepter/refuser
    outgoing: list[TransferResponse]  # on est la destination : demandes émises

    @classmethod
    def from_dto(cls, dto: TransferListDTO) -> TransferListResponse:
        return cls(
            tenant_id=dto.tenant_id,
            incoming=[TransferResponse.from_dto(t) for t in dto.incoming],
            outgoing=[TransferResponse.from_dto(t) for t in dto.outgoing],
        )


class ChurchInvitationResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    code: str
    expires_at: datetime
    revoked: bool

    @classmethod
    def from_dto(cls, dto: ChurchInvitationDTO) -> ChurchInvitationResponse:
        return cls(
            id=dto.id,
            tenant_id=dto.tenant_id,
            code=dto.code,
            expires_at=dto.expires_at,
            revoked=dto.revoked,
        )


class JoinChurchRequest(BaseModel):
    code: str = Field(description="Le code d'invitation église partagé (lien)")


class JoinChurchResponse(BaseModel):
    account_id: UUID
    tenant_id: UUID
    membership_id: UUID
    status: str
    already_member: bool

    @classmethod
    def from_result(cls, result: JoinChurchResult) -> JoinChurchResponse:
        return cls(
            account_id=result.account_id,
            tenant_id=result.tenant_id,
            membership_id=result.membership_id,
            status=result.status,
            already_member=result.already_member,
        )


class RoleResponse(BaseModel):
    role: str
    group_id: UUID | None


class MembershipStatusResponse(BaseModel):
    membership_id: UUID
    account_id: UUID
    tenant_id: UUID
    status: str
    is_confirmed_member: bool
    active_absence_reason: str | None
    active_roles: list[RoleResponse]
    is_owner: bool = Field(description="Propriétaire du tenant (peut tout, sans portée)")
    permissions: list[str] = Field(
        description="Verbes résolus dans ce tenant (l'app affiche/masque selon cette liste)"
    )

    @classmethod
    def from_dto(cls, dto: MembershipStatusDTO) -> MembershipStatusResponse:
        return cls(
            membership_id=dto.membership_id,
            account_id=dto.account_id,
            tenant_id=dto.tenant_id,
            status=dto.status,
            is_confirmed_member=dto.is_confirmed_member,
            active_absence_reason=dto.active_absence_reason,
            active_roles=[RoleResponse(role=r.role, group_id=r.group_id) for r in dto.active_roles],
            is_owner=dto.is_owner,
            permissions=dto.permissions,
        )


class SetMyBirthdayRequest(BaseModel):
    """Jour, mois, et le cercle. L'année est **optionnelle et ne ressort jamais**."""

    day: int = Field(ge=1, le=31, examples=[12])
    month: int = Field(ge=1, le=12, examples=[6])
    year: int | None = Field(
        default=None,
        description=(
            "Facultative, et affichée nulle part : l'âge de quelqu'un n'est pas une donnée "
            "d'église. Elle n'existe que si le membre la donne."
        ),
    )
    scope: BirthdayScope = Field(
        default=DEFAULT_SCOPE,
        description="groups | referent_only | hidden — « hidden » éteint tout, sans exception",
    )


class BirthdayResponse(BaseModel):
    """Ce que le membre a posé, tel qu'il pourra le relire. Toujours sans l'année."""

    day: int
    month: int
    scope: str


class BirthdayOfTheDayResponse(BaseModel):
    """Un nom, et si c'est aujourd'hui. **Pas de champ pour l'âge**, ni pour souhaiter.

    Aucun message ne part de Dorea : l'encart porte le bouton d'appel standard, celui de partout
    ailleurs. Dorea rappelle aux humains d'aimer ; il n'aime jamais à leur place."""

    account_id: UUID
    first_name: str | None
    last_name: str | None
    is_today: bool = Field(description="False = demain, et seul le référent le voit")
