"""Modèles ORM du moteur de veille — le **ledger**.

Une seule table, et une seule opération dessus : ajouter. Pas d'`UPDATE`, pas de `DELETE`. Tout
l'état aval (neutralisations, exclusions, et demain les signaux) en est une projection.

`seq` est la clé primaire **et** l'ordre du rejeu : c'est le seul ordre total dont on dispose.
Les dates ne suffisent pas — `recorded_at` peut être à égalité, `occurred_at` peut remonter le
temps. Sans ordre total, l'invariant de déterminisme n'est pas testable.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, BigInteger, DateTime, Index, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.contexts.watch.domain.signal import LIVE_STATUSES
from app.core.database import Base


class FactLedgerModel(Base):
    """Le journal immuable. Append-only — aucune écriture ne modifie une ligne existante."""

    __tablename__ = "watch_fact_ledger"

    __table_args__ = (
        Index("ix_watch_ledger_tenant_seq", "tenant_id", "seq"),
        Index("ix_watch_ledger_subject", "tenant_id", "subject_id"),
        Index("ix_watch_ledger_fact", "fact_id", unique=True),
    )

    # BIGSERIAL en Postgres, INTEGER PRIMARY KEY en SQLite (tests) — dans les deux cas monotone.
    seq: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    fact_id: Mapped[UUID] = mapped_column(Uuid)  # idempotence : un fait n'entre qu'une fois
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String)
    subject_kind: Mapped[str] = mapped_column(String)
    subject_id: Mapped[UUID] = mapped_column(Uuid)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    payload_version: Mapped[int] = mapped_column(Integer, default=1)
    # Preuve de consentement, sérialisée. Une révocation ne supprime pas la ligne : elle sort le
    # fait des vues et le scelle — la dignité de l'historique n'est pas l'accès au contenu.
    consent: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class SignalModel(Base):
    """Un **cas ouvert**. Entièrement une projection du ledger : effaçable et reconstructible.

    `owner_account_id` est nullable et c'est **une donnée**, pas un manque : « personne ne
    connaît cette personne » est précisément ce qu'il faut voir.
    """

    __tablename__ = "watch_signals"

    __table_args__ = (
        Index("ix_watch_signals_tenant_status", "tenant_id", "status"),
        Index("ix_watch_signals_subject", "tenant_id", "subject_id"),
        Index("ix_watch_signals_owner", "tenant_id", "owner_account_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    subject_id: Mapped[UUID] = mapped_column(Uuid)
    origin: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    # Écrite à l'ouverture, **jamais** réécrite — un motif reformulé six semaines plus tard ne
    # dit plus la même chose.
    reason: Mapped[str] = mapped_column(String)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    owner_account_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    source_refs: Mapped[list[str]] = mapped_column(JSON, default=list)
    gestures_count: Mapped[int] = mapped_column(Integer, default=0)
    outcome: Mapped[str | None] = mapped_column(String, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by_account_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    retracted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


LIVE_STATUS_VALUES: tuple[str, ...] = tuple(s.value for s in LIVE_STATUSES)


class CareMemoryModel(Base):
    """La mémoire du lien — ce qui a été porté, à rendre **une fois** à qui cela console.

    `delivered_at` est le mécanisme de consommation : une fois remise, elle ne réapparaît jamais.
    C'est ce qui empêchera le Compagnon de devenir un compteur qu'on rafraîchit.
    """

    __tablename__ = "watch_care_memory"

    __table_args__ = (Index("ix_watch_care_memory_subject", "tenant_id", "subject_id"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    subject_id: Mapped[UUID] = mapped_column(Uuid)
    item: Mapped[str] = mapped_column(String)
    reason: Mapped[str] = mapped_column(String)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
