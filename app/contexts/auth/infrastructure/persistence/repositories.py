"""Lecture des credentials sur la table `accounts` (schéma détenu par ce backend).

Auth lit un sous-ensemble de colonnes via une requête ciblée plutôt qu'en
important l'ORM d'IAM : les deux contextes restent découplés, la base partagée
étant le seul point d'intégration (spec §14).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.auth.domain.credentials import AuthCredentials
from app.contexts.auth.domain.login_attempt import LoginAttempt
from app.contexts.auth.domain.repositories import (
    AccountSecurityRepository,
    CredentialsRepository,
    LoginAttemptRepository,
)
from app.contexts.auth.infrastructure.persistence.models import LoginAttemptModel
from app.contexts.iam.domain.enums import AccountCreationSource, AccountStatus
from app.contexts.iam.infrastructure.persistence.models import AccountModel

_COLS = "id, phone_number, email, password_hash, pin_hash, hash_algo_version, status"
_SELECT_BY_PHONE = text(f"SELECT {_COLS} FROM accounts WHERE phone_number = :v LIMIT 1")
_SELECT_BY_EMAIL = text(f"SELECT {_COLS} FROM accounts WHERE email = :v LIMIT 1")


def _to_credentials(row) -> AuthCredentials:
    account_id = row["id"]
    return AuthCredentials(
        # La requête `text()` renvoie l'id en str sous SQLite → normaliser en UUID.
        account_id=account_id if isinstance(account_id, UUID) else UUID(str(account_id)),
        phone_number=row["phone_number"],
        email=row["email"],
        password_hash=row["password_hash"],
        pin_hash=row["pin_hash"],
        hash_algo_version=row["hash_algo_version"],
        is_active=row["status"] == "active",
    )


class SqlCredentialsRepository(CredentialsRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_phone(self, phone_number: str) -> AuthCredentials | None:
        row = (
            (await self._session.execute(_SELECT_BY_PHONE, {"v": phone_number})).mappings().first()
        )
        return _to_credentials(row) if row is not None else None

    async def get_by_email(self, email: str) -> AuthCredentials | None:
        row = (await self._session.execute(_SELECT_BY_EMAIL, {"v": email})).mappings().first()
        return _to_credentials(row) if row is not None else None

    async def get_by_account_id(self, account_id: UUID) -> AuthCredentials | None:
        # Par id → ORM (gère la conversion UUID selon le dialecte, ≠ SQL brut).
        row = await self._session.get(AccountModel, account_id)
        if row is None:
            return None
        return AuthCredentials(
            account_id=row.id,
            phone_number=row.phone_number,
            email=row.email,
            password_hash=row.password_hash,
            pin_hash=row.pin_hash,
            hash_algo_version=row.hash_algo_version,
            is_active=row.status == "active",
        )


class SqlLoginAttemptRepository(LoginAttemptRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, identifier: str) -> LoginAttempt | None:
        row = await self._session.get(LoginAttemptModel, identifier)
        if row is None:
            return None
        return LoginAttempt(
            identifier=row.identifier,
            failed_count=row.failed_count,
            locked_until=row.locked_until,
            updated_at=row.updated_at,
        )

    async def save(self, attempt: LoginAttempt) -> None:
        row = await self._session.get(LoginAttemptModel, attempt.identifier)
        if row is None:
            self._session.add(
                LoginAttemptModel(
                    identifier=attempt.identifier,
                    failed_count=attempt.failed_count,
                    locked_until=attempt.locked_until,
                    updated_at=attempt.updated_at,
                )
            )
        else:
            row.failed_count = attempt.failed_count
            row.locked_until = attempt.locked_until
            row.updated_at = attempt.updated_at
        await self._session.flush()


class SqlAccountSecurityRepository(AccountSecurityRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_self_registered(
        self, *, account_id, phone_number, pin_hash, hash_algo_version, created_at
    ) -> None:
        self._session.add(
            AccountModel(
                id=account_id,
                phone_number=phone_number,
                email=None,
                password_hash=None,
                pin_hash=pin_hash,
                hash_algo_version=hash_algo_version,
                is_phone_verified=True,  # le numéro vient d'être prouvé par OTP
                is_email_verified=False,
                created_at=created_at,
                created_by_type=AccountCreationSource.SELF_SERVICE.value,
                status=AccountStatus.ACTIVE.value,
            )
        )
        await self._session.flush()

    async def set_pin(self, account_id: UUID, pin_hash, hash_algo_version) -> None:
        await self._session.execute(
            update(AccountModel)
            .where(AccountModel.id == account_id)
            .values(pin_hash=pin_hash, hash_algo_version=hash_algo_version)
        )

    async def set_password(self, account_id: UUID, password_hash, hash_algo_version) -> None:
        await self._session.execute(
            update(AccountModel)
            .where(AccountModel.id == account_id)
            .values(password_hash=password_hash, hash_algo_version=hash_algo_version)
        )

    async def set_phone(self, account_id: UUID, phone_number) -> None:
        await self._session.execute(
            update(AccountModel)
            .where(AccountModel.id == account_id)
            .values(phone_number=phone_number)
        )
