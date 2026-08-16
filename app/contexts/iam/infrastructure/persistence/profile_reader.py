"""Lire son propre profil : un `SELECT` sur `accounts`, sans `birth_year`.

L'année est absente du `SELECT` et non pas simplement absente du DTO. Ce qui n'est pas lu
ne peut pas fuir dans un log, une trace, ou un DTO écrit trop vite — même règle que
`SqlBirthdayDirectory`, et pour la même raison.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.iam.application.ports import ProfileReader, ProfileRow
from app.contexts.iam.infrastructure.persistence.models import AccountModel


class SqlProfileReader(ProfileReader):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def read(self, account_id: UUID) -> ProfileRow | None:
        row = (
            await self._session.execute(
                select(
                    AccountModel.id,
                    AccountModel.phone_number,
                    AccountModel.first_name,
                    AccountModel.last_name,
                    AccountModel.email,
                    AccountModel.birth_day,
                    AccountModel.birth_month,
                    AccountModel.birthday_scope,
                    AccountModel.language,
                ).where(AccountModel.id == account_id)
            )
        ).first()
        if row is None:
            return None
        return ProfileRow(
            account_id=row.id,
            phone_number=row.phone_number,
            first_name=row.first_name,
            last_name=row.last_name,
            email=row.email,
            birth_day=row.birth_day,
            birth_month=row.birth_month,
            birthday_scope=row.birthday_scope,
            language=row.language,
        )
