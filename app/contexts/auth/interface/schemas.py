"""Schémas HTTP du contexte Auth."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.contexts.auth.application.dtos import TokenPair

_DEVICE_ID = Field(description="Identifiant stable de l'appareil (généré par le mobile)")


class LoginRequest(BaseModel):
    phone_number: str = Field(examples=["+2250700000001"])
    secret_code: str = Field(examples=["1234"], description="Code secret (PIN 4 a 6 chiffres)")
    device_id: str = _DEVICE_ID


class VerifyDeviceRequest(BaseModel):
    phone_number: str = Field(examples=["+2250700000001"])
    otp: str = Field(examples=["123456"])
    device_id: str = _DEVICE_ID


class OtpRequiredResponse(BaseModel):
    status: str = "otp_required"


class RefreshRequest(BaseModel):
    refresh_token: str


class RegisterRequest(BaseModel):
    phone_number: str = Field(examples=["+2250700000001"])


class RegisterConfirmRequest(BaseModel):
    phone_number: str = Field(examples=["+2250700000001"])
    otp: str = Field(examples=["123456"])
    secret_code: str = Field(examples=["1234"], description="PIN choisi (4 à 6 chiffres)")
    device_id: str = _DEVICE_ID


class ResetSecretCodeRequest(BaseModel):
    """Le numéro, et rien d'autre — c'est tout ce que possède quelqu'un enfermé dehors."""

    phone_number: str = Field(examples=["+2250700000001"])


class ResetSecretCodeConfirm(BaseModel):
    phone_number: str = Field(examples=["+2250700000001"])
    otp: str = Field(examples=["123456"])
    new_secret_code: str = Field(
        examples=["4321"], description="Nouveau PIN (4 à 6 chiffres)"
    )
    device_id: str = _DEVICE_ID


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int

    @classmethod
    def from_pair(cls, pair: TokenPair) -> TokenResponse:
        return cls(
            access_token=pair.access_token,
            refresh_token=pair.refresh_token,
            token_type=pair.token_type,
            expires_in=pair.expires_in,
        )


class LogoutRequest(BaseModel):
    """Déconnexion (DOREA-016). Par défaut : **cet** appareil seulement."""

    everywhere: bool = Field(
        default=False,
        description="Révoquer TOUS les appareils du compte — en cas de vol.",
    )
