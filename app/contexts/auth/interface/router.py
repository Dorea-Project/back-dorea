"""Routes HTTP du contexte Auth (canal mobile)."""

from fastapi import APIRouter, Response, status

from app.contexts.auth.domain.secret_code import SecretCode
from app.contexts.auth.interface.dependencies import (
    LoginDep,
    RefreshTokenDep,
    RegisterMemberDep,
    VerifyDeviceLoginDep,
)
from app.contexts.auth.interface.schemas import (
    LoginRequest,
    OtpRequiredResponse,
    RefreshRequest,
    RegisterConfirmRequest,
    RegisterRequest,
    TokenResponse,
    VerifyDeviceRequest,
)

router = APIRouter()


@router.post(
    "/register",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Auto-inscription mobile — demander un OTP SMS",
)
async def register(payload: RegisterRequest, command: RegisterMemberDep) -> None:
    await command.request(phone_number=payload.phone_number)


@router.post(
    "/verify-registration",
    response_model=TokenResponse,
    summary="Auto-inscription mobile — confirmer l'OTP, poser le PIN et se connecter",
)
async def verify_registration(
    payload: RegisterConfirmRequest, command: RegisterMemberDep
) -> TokenResponse:
    pair = await command.confirm(
        phone_number=payload.phone_number,
        otp=payload.otp,
        secret_code=payload.secret_code,
        device_id=payload.device_id,
    )
    return TokenResponse.from_pair(pair)


@router.post(
    "/login",
    response_model=TokenResponse | OtpRequiredResponse,
    summary="Connexion mobile (téléphone + code secret + appareil)",
)
async def login(
    payload: LoginRequest, command: LoginDep, response: Response
) -> TokenResponse | OtpRequiredResponse:
    outcome = await command.execute(
        phone_number=payload.phone_number,
        secret_code=SecretCode(payload.secret_code),
        device_id=payload.device_id,
    )
    if outcome.otp_required:
        response.status_code = status.HTTP_202_ACCEPTED
        return OtpRequiredResponse()  # OTP SMS envoyé — appeler /verify-device
    return TokenResponse.from_pair(outcome.tokens)


@router.post(
    "/verify-device",
    response_model=TokenResponse,
    summary="Vérifier l'OTP d'un nouvel appareil → appareil de confiance + jetons",
)
async def verify_device(
    payload: VerifyDeviceRequest, command: VerifyDeviceLoginDep
) -> TokenResponse:
    pair = await command.execute(
        phone_number=payload.phone_number,
        otp=payload.otp,
        device_id=payload.device_id,
    )
    return TokenResponse.from_pair(pair)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Rafraîchir la session (rotation des jetons)",
)
async def refresh(payload: RefreshRequest, command: RefreshTokenDep) -> TokenResponse:
    pair = await command.execute(refresh_token=payload.refresh_token)
    return TokenResponse.from_pair(pair)
