"""Modèle ORM du module Billing — le tier + la carte (données non sensibles seulement)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class BusinessAccountModel(Base):
    __tablename__ = "business_accounts"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    account_id: Mapped[UUID] = mapped_column(Uuid, unique=True)
    # Carte (nullable = tier gratuit). Jamais de numéro complet : 4 derniers + marque + expiration.
    card_brand: Mapped[str | None] = mapped_column(String, nullable=True)
    card_last4: Mapped[str | None] = mapped_column(String, nullable=True)
    card_prepaid: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    card_exp_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    card_exp_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    card_provider_token: Mapped[str | None] = mapped_column(String, nullable=True)
    card_added_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
