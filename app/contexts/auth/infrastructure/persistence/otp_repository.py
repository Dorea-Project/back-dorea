"""Implémentation SQLAlchemy de `OtpChallengeRepository`."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.auth.domain.otp import OtpChallenge, OtpChannel, OtpPurpose
from app.contexts.auth.domain.repositories import OtpChallengeRepository
from app.contexts.auth.infrastructure.persistence.models import OtpChallengeModel


def _aware(dt: datetime | None) -> datetime | None:
    # SQLite relit les timestamps en naïf ; on les rattache à UTC pour comparer à `now`.
    return dt.replace(tzinfo=UTC) if dt is not None and dt.tzinfo is None else dt


def _to_challenge(row: OtpChallengeModel) -> OtpChallenge:
    return OtpChallenge(
        id=row.id,
        purpose=OtpPurpose(row.purpose),
        channel=OtpChannel(row.channel),
        target=row.target,
        code_hash=row.code_hash,
        created_at=_aware(row.created_at),
        expires_at=_aware(row.expires_at),
        account_id=row.account_id,
        device_id=row.device_id,
        consumed_at=_aware(row.consumed_at),
        attempts=row.attempts,
    )


class SqlOtpChallengeRepository(OtpChallengeRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def count_issued_since(self, target: str, since) -> int:
        stmt = select(func.count()).where(
            OtpChallengeModel.target == target, OtpChallengeModel.created_at >= since
        )
        return int((await self._session.execute(stmt)).scalar_one())

    async def add(self, challenge: OtpChallenge) -> None:
        self._session.add(
            OtpChallengeModel(
                id=challenge.id,
                purpose=challenge.purpose.value,
                channel=challenge.channel.value,
                target=challenge.target,
                code_hash=challenge.code_hash,
                account_id=challenge.account_id,
                device_id=challenge.device_id,
                created_at=challenge.created_at,
                expires_at=challenge.expires_at,
                consumed_at=challenge.consumed_at,
                attempts=challenge.attempts,
            )
        )
        await self._session.flush()

    async def get_active(
        self, purpose: OtpPurpose, target: str, now: datetime
    ) -> OtpChallenge | None:
        # Le plus récent défi non consommé pour (purpose, target).
        stmt = (
            select(OtpChallengeModel)
            .where(
                OtpChallengeModel.purpose == purpose.value,
                OtpChallengeModel.target == target,
                OtpChallengeModel.consumed_at.is_(None),
            )
            .order_by(OtpChallengeModel.created_at.desc())
            .limit(1)
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_challenge(row) if row is not None else None

    async def increment_attempts(self, challenge_id: UUID) -> None:
        await self._session.execute(
            update(OtpChallengeModel)
            .where(OtpChallengeModel.id == challenge_id)
            .values(attempts=OtpChallengeModel.attempts + 1)
        )

    async def mark_consumed(self, challenge_id: UUID, consumed_at: datetime) -> None:
        await self._session.execute(
            update(OtpChallengeModel)
            .where(OtpChallengeModel.id == challenge_id)
            .values(consumed_at=consumed_at)
        )
