"""Modèles ORM du contexte Auth — table `otp_challenges` (les credentials vivent
sur `accounts`, détenue par le contexte IAM)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Index, Integer, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DeviceModel(Base):
    """Appareil de confiance d'un compte (vérifié par OTP)."""

    __tablename__ = "trusted_devices"

    # DOREA-016 — l'unicité ne porte que sur les appareils **encore de confiance** :
    # un appareil révoqué garde sa ligne (trace), et le même appareil peut redevenir
    # de confiance plus tard (nouvel OTP) sans buter sur l'index.
    __table_args__ = (
        Index(
            "uq_account_device",
            "account_id",
            "device_id",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
            sqlite_where=text("revoked_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    account_id: Mapped[UUID] = mapped_column(Uuid)
    device_id: Mapped[str] = mapped_column(String)
    trusted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # DOREA-016 — la révocation de l'appareil **tue les jetons** qui le portent
    # (access, refresh et session meurent ensemble : ils désignent le même appareil).
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class LoginAttemptModel(Base):
    """Compteur d'échecs de login par identifiant (anti-brute-force, DOREA-004)."""

    __tablename__ = "login_attempts"

    identifier: Mapped[str] = mapped_column(String, primary_key=True)  # téléphone ou e-mail
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OtpChallengeModel(Base):
    __tablename__ = "otp_challenges"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    purpose: Mapped[str] = mapped_column(String)
    channel: Mapped[str] = mapped_column(String)
    target: Mapped[str] = mapped_column(String)  # email ou numéro
    code_hash: Mapped[str] = mapped_column(String)
    account_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    device_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
