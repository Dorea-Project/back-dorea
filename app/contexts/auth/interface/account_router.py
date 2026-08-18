"""Routes mobile des **opérations sensibles** membre — montées sous `/api/mobile/account`.

Chaque opération : `request` (envoie un OTP SMS) puis `confirm` (OTP + application).
Authentifié par le JWT mobile (`CurrentActor`).
"""

from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from app.contexts.auth.interface.dependencies import (
    ChangePasswordDep,
    ChangePhoneDep,
    CurrentActor,
    DeleteAccountDep,
)

router = APIRouter()


class ChangePasswordConfirmSchema(BaseModel):
    otp: str = Field(examples=["123456"])
    new_secret_code: str = Field(examples=["4321"], description="Nouveau PIN (4-6 chiffres)")


class ChangePhoneRequestSchema(BaseModel):
    new_phone: str = Field(examples=["+2250700000099"])


class ChangePhoneConfirmSchema(BaseModel):
    new_phone: str
    otp: str = Field(examples=["123456"])


class DeleteAccountConfirmSchema(BaseModel):
    otp: str = Field(examples=["123456"])


@router.post(
    "/change-password/request",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Demander un OTP pour changer le code secret",
)
async def change_password_request(actor: CurrentActor, command: ChangePasswordDep) -> None:
    await command.request(account_id=actor.account_id)


@router.post(
    "/change-password/confirm",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Confirmer le changement de code secret (OTP)",
)
async def change_password_confirm(
    payload: ChangePasswordConfirmSchema, actor: CurrentActor, command: ChangePasswordDep
) -> None:
    await command.confirm(
        account_id=actor.account_id, otp=payload.otp, new_secret_code=payload.new_secret_code
    )


@router.post(
    "/change-phone/request",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Demander un OTP (envoyé au nouveau numéro) pour changer de numéro",
)
async def change_phone_request(
    payload: ChangePhoneRequestSchema, actor: CurrentActor, command: ChangePhoneDep
) -> None:
    await command.request(account_id=actor.account_id, new_phone=payload.new_phone)


@router.post(
    "/change-phone/confirm",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Confirmer le changement de numéro (OTP)",
)
async def change_phone_confirm(
    payload: ChangePhoneConfirmSchema, actor: CurrentActor, command: ChangePhoneDep
) -> None:
    await command.confirm(
        account_id=actor.account_id, new_phone=payload.new_phone, otp=payload.otp
    )


# --- Supprimer son compte -----------------------------------------------------------
#
# Deux temps comme les autres opérations sensibles, et pour une raison plus forte :
# celle-ci ne se défait pas. Un téléphone déverrouillé oublié sur une table ne doit pas
# suffire à effacer des années de préparations.


@router.post(
    "/delete/request",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Demander un OTP pour supprimer son compte",
)
async def delete_account_request(actor: CurrentActor, command: DeleteAccountDep) -> None:
    await command.request(account_id=actor.account_id)


@router.post(
    "/delete/confirm",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Confirmer la suppression du compte (OTP) — irréversible",
)
async def delete_account_confirm(
    payload: DeleteAccountConfirmSchema, actor: CurrentActor, command: DeleteAccountDep
) -> None:
    await command.confirm(account_id=actor.account_id, otp=payload.otp)
