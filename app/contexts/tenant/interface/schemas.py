"""Schémas HTTP backoffice — provisionnement d'un tenant."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from app.contexts.tenant.application.dtos import (
    OnboardingResult,
    ProvisionTenantResult,
    TenantDetailDTO,
)


class SubmitOnboardingSchema(BaseModel):
    tenant_name: str = Field(examples=["Église Bethel"])
    owner_email: str = Field(examples=["pasteur@bethel.ci"])
    owner_phone: str = Field(examples=["+2250700000001"])
    owner_password: str = Field(examples=["MotDePasse#2026"], description="≥ 8 caractères")
    owner_first_name: str | None = Field(default=None, examples=["Emmanuel"])
    owner_last_name: str | None = None
    owner_years_of_experience: int | None = Field(default=None, ge=0, examples=[12])
    denomination: str | None = Field(default=None, examples=["Assemblées de Dieu"])
    contact_email: str | None = None
    estimated_member_count: int | None = Field(default=None, ge=0, examples=[150])
    country: str | None = Field(default=None, examples=["CI"])
    city: str | None = Field(default=None, examples=["Abidjan"])
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    # --- Champs M0 §2.2 (parité avec le provisionnement direct ; slug auto-généré) ---
    logo_url: str | None = None
    short_description: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    timezone: str = Field(default="Africa/Abidjan", examples=["Africa/Abidjan"])
    language: str = Field(default="fr", examples=["fr"])
    currency: str = Field(default="XOF", description="ISO 4217 — XOF (BCEAO) / XAF (BEAC)")
    operates_annexes: bool = False


class VerifyOnboardingEmailSchema(BaseModel):
    request_id: UUID
    otp: str = Field(examples=["123456"])


class RejectOnboardingSchema(BaseModel):
    reason: str = Field(examples=["Église non vérifiable"])


class OnboardingResponse(BaseModel):
    request_id: UUID
    status: str

    @classmethod
    def from_result(cls, result: OnboardingResult) -> OnboardingResponse:
        return cls(request_id=result.request_id, status=result.status)


class TenantDetailResponse(BaseModel):
    tenant_id: UUID
    name: str
    status: str
    denomination: str | None
    contact_email: str | None
    estimated_member_count: int | None
    country: str | None
    city: str | None
    address: str | None
    latitude: float | None
    longitude: float | None
    is_independent: bool
    slug: str | None = None
    logo_url: str | None = None
    short_description: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    timezone: str = "Africa/Abidjan"
    language: str = "fr"
    currency: str = "XOF"
    operates_annexes: bool = False

    @classmethod
    def from_dto(cls, dto: TenantDetailDTO) -> TenantDetailResponse:
        return cls(**dto.__dict__)


class UpdateTenantSchema(BaseModel):
    denomination: str | None = None
    contact_email: str | None = None
    estimated_member_count: int | None = Field(default=None, ge=0)
    country: str | None = None
    city: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    logo_url: str | None = None
    short_description: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    timezone: str | None = None
    language: str | None = None
    currency: str | None = None


class ProvisionTenantRequestSchema(BaseModel):
    tenant_name: str = Field(examples=["Église Bethel"])
    owner_phone: str = Field(examples=["+2250700000001"])
    owner_email: str = Field(examples=["pasteur@bethel.ci"], description="Connexion backoffice")
    owner_password: str = Field(examples=["MotDePasse#2026"], description="≥ 8 caractères")
    owner_first_name: str | None = Field(default=None, examples=["Emmanuel"])
    owner_last_name: str | None = Field(default=None, examples=["K."])
    parent_id: UUID | None = Field(
        default=None,
        description="Filiation (émancipation). Vide pour une église indépendante.",
    )
    # --- Attributs de l'église ---
    denomination: str | None = Field(
        default=None, examples=["Assemblées de Dieu"], description="Vide = indépendante"
    )
    contact_email: str | None = Field(default=None, examples=["contact@bethel.org"])
    estimated_member_count: int | None = Field(default=None, ge=0, examples=[150])
    country: str | None = Field(default=None, examples=["CI"])
    city: str | None = Field(default=None, examples=["Abidjan"])
    address: str | None = Field(default=None, examples=["Rue X, Cocody"])
    latitude: float | None = Field(default=None, examples=[5.35])
    longitude: float | None = Field(default=None, examples=[-4.0])
    # --- Champs M0 §2.2 (le slug est auto-généré, non saisi) ---
    logo_url: str | None = Field(default=None, examples=["/media/logo.png"])
    short_description: str | None = Field(default=None, examples=["Une église de la grâce"])
    contact_name: str | None = Field(default=None, examples=["Frère Jean"])
    contact_phone: str | None = Field(default=None, examples=["+2250700000009"])
    timezone: str = Field(default="Africa/Abidjan", examples=["Africa/Abidjan"])
    language: str = Field(default="fr", examples=["fr"])
    currency: str = Field(default="XOF", description="ISO 4217 — XOF (BCEAO) / XAF (BEAC)")
    operates_annexes: bool = Field(default=False, description="Déclare des annexes (plan famille)")


class ProvisionTenantResponse(BaseModel):
    tenant_id: UUID
    owner_account_id: UUID
    owner_membership_id: UUID

    @classmethod
    def from_result(cls, result: ProvisionTenantResult) -> ProvisionTenantResponse:
        return cls(
            tenant_id=result.tenant_id,
            owner_account_id=result.owner_account_id,
            owner_membership_id=result.owner_membership_id,
        )
