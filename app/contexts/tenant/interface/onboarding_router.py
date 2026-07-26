"""Routes d'onboarding.

- **public** (`/api/onboarding`) : soumission + vérification email par l'aspirant Owner.
- **backoffice** (`/api/backoffice/onboarding`) : validation/rejet par Dorea (jeton de service).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.contexts.tenant.application.dtos import SubmitOnboardingInput
from app.contexts.tenant.interface.dependencies import require_platform_token
from app.contexts.tenant.interface.onboarding_dependencies import (
    ApproveOnboardingDep,
    RejectOnboardingDep,
    SubmitOnboardingDep,
    VerifyOnboardingEmailDep,
)
from app.contexts.tenant.interface.schemas import (
    OnboardingResponse,
    ProvisionTenantResponse,
    RejectOnboardingSchema,
    SubmitOnboardingSchema,
    VerifyOnboardingEmailSchema,
)

# --- Surface publique ---
public_router = APIRouter()


@public_router.post(
    "/submit",
    response_model=OnboardingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Soumettre une demande d'onboarding (aspirant Owner) — envoie un OTP email",
)
async def submit(
    payload: SubmitOnboardingSchema, command: SubmitOnboardingDep
) -> OnboardingResponse:
    result = await command.execute(SubmitOnboardingInput(**payload.model_dump()))
    return OnboardingResponse.from_result(result)


@public_router.post(
    "/verify-email",
    response_model=OnboardingResponse,
    summary="Vérifier l'email de la demande (OTP)",
)
async def verify_email(
    payload: VerifyOnboardingEmailSchema, command: VerifyOnboardingEmailDep
) -> OnboardingResponse:
    result = await command.execute(request_id=payload.request_id, otp=payload.otp)
    return OnboardingResponse.from_result(result)


# --- Surface backoffice (Dorea) ---
backoffice_router = APIRouter(dependencies=[Depends(require_platform_token)])


@backoffice_router.post(
    "/{request_id}/approve",
    response_model=ProvisionTenantResponse,
    summary="Valider une demande → matérialise le tenant + owner (Dorea)",
)
async def approve(request_id: UUID, command: ApproveOnboardingDep) -> ProvisionTenantResponse:
    result = await command.execute(request_id=request_id)
    return ProvisionTenantResponse.from_result(result)


@backoffice_router.post(
    "/{request_id}/reject",
    response_model=OnboardingResponse,
    summary="Rejeter une demande (Dorea)",
)
async def reject(
    request_id: UUID, payload: RejectOnboardingSchema, command: RejectOnboardingDep
) -> OnboardingResponse:
    result = await command.execute(request_id=request_id, reason=payload.reason)
    return OnboardingResponse.from_result(result)
