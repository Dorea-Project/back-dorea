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

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
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
        Index("ix_watch_signals_episode", "tenant_id", "episode_id"),
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
    # L'urgence, distincte de l'origine : un cas d'absence qu'un rendez-vous annulé rend
    # soudain le plus urgent de la file garde son origine et change de priorité.
    priority: Mapped[str] = mapped_column(String)
    # Ce qu'on a appris **depuis** l'ouverture — ajouté, jamais substitué à la raison.
    annotations: Mapped[list[str]] = mapped_column(JSON, default=list)
    # Les deux métriques du pilote : le taux d'ignorés (le seul qui **anticipe** l'abandon)
    # et le délai détection → premier contact.
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_contact_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # L'**épisode** : la chaîne des cas successifs sur une même personne. Il n'existe que pour la
    # réouverture — sans lui, le troisième cas d'affilée s'affiche comme le premier, et celui qui
    # a déjà appelé deux fois recommence de zéro. Trois champs, pas une histoire complète.
    episode_id: Mapped[UUID] = mapped_column(Uuid)
    occurrence_number: Mapped[int] = mapped_column(Integer, default=1)
    previous_outcome: Mapped[str | None] = mapped_column(String, nullable=True)
    previous_closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    gestures_count: Mapped[int] = mapped_column(Integer, default=0)
    outcome: Mapped[str | None] = mapped_column(String, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by_account_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    retracted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


LIVE_STATUS_VALUES: tuple[str, ...] = tuple(s.value for s in LIVE_STATUSES)


class GroupTypePolicyModel(Base):
    """La politique de veille d'un **type** de groupe — le rang est une donnée, pas du code.

    `resolve_primary_group` lit cette table et ne connaît le nom d'aucun type. Enrichir
    `GroupType` devient une insertion de ligne : zéro code touché, zéro régression possible.
    """

    __tablename__ = "watch_group_type_policies"

    __table_args__ = (
        UniqueConstraint("tenant_id", "group_type", name="uq_watch_group_type_policy"),
        # En SQL, `NULL != NULL` dans une contrainte d'unicité : sans cet index partiel, la
        # politique **par défaut** pourrait être insérée deux fois (re-seed, aller-retour de
        # migration, script d'init rejoué). `all_for()` renverrait alors deux rangs concurrents
        # pour un même type, et le résolveur deviendrait non déterministe selon l'ordre de
        # lecture — ce qui casse la rejouabilité du ledger.
        Index(
            "uq_watch_group_type_policy_default",
            "group_type",
            unique=True,
            postgresql_where=text("tenant_id IS NULL"),
            sqlite_where=text("tenant_id IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    # NULL = politique **par défaut**, valable pour toute église qui n'a pas la sienne.
    tenant_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    group_type: Mapped[str] = mapped_column(String)
    # Ce type peut-il fonder un lien de veille ? Un type qui ne porte pas de politique
    # d'alerte (commission, association) ne le peut pas — la personne dont c'est la seule
    # appartenance est alors un trou de couverture, et c'est juste.
    bears_veille: Mapped[bool] = mapped_column(Boolean, default=True)
    # Ordonné par **durabilité du lien**, pas par intensité : une classe s'achève, un
    # ministère dure.
    primacy_rank: Mapped[int] = mapped_column(Integer)


class WatchParameterModel(Base):
    """Un paramètre calibrable. `tenant_id` NULL = la valeur par défaut du produit.

    Même piège que les politiques de type de groupe : `NULL != NULL` en SQL, donc l'index
    partiel est indispensable pour que le défaut ne puisse pas être inséré deux fois."""

    __tablename__ = "watch_parameters"

    __table_args__ = (
        UniqueConstraint("tenant_id", "param", name="uq_watch_parameter"),
        Index(
            "uq_watch_parameter_default",
            "param",
            unique=True,
            postgresql_where=text("tenant_id IS NULL"),
            sqlite_where=text("tenant_id IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    tenant_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    param: Mapped[str] = mapped_column(String)
    value: Mapped[int] = mapped_column(Integer)


class CoverageGapModel(Base):
    """Un trou du dispositif. `subject_id` NULL = le défaut porte sur l'**église entière**.

    Consigné ici et pas dans un journal applicatif : un défaut qui n'apparaît pas sur l'écran de
    couverture n'existe pour personne."""

    __tablename__ = "watch_coverage_gaps"

    __table_args__ = (
        Index("ix_watch_coverage_gaps_tenant", "tenant_id", "resolved_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    scope: Mapped[str] = mapped_column(String)  # person | group | tenant
    subject_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    gap: Mapped[str] = mapped_column(String)
    reason: Mapped[str] = mapped_column(String)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ReferentOverrideModel(Base):
    """Une désignation explicite. Stockée **seulement parce qu'elle existe**."""

    __tablename__ = "watch_referent_overrides"

    __table_args__ = (
        Index("ix_watch_referent_overrides_person", "tenant_id", "person_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    person_id: Mapped[UUID] = mapped_column(Uuid)
    referent_person_id: Mapped[UUID] = mapped_column(Uuid)
    origin: Mapped[str] = mapped_column(String)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_by_account_id: Mapped[UUID] = mapped_column(Uuid)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_reason: Mapped[str | None] = mapped_column(String, nullable=True)


class PrimaryGroupOverrideModel(Base):
    """« C'est ce groupe-là qui compte pour elle. » Stocké seulement s'il existe.

    Il n'y a **pas** de drapeau `is_primary` sur l'appartenance : un champ que personne n'a
    intérêt à maintenir pourrit, et on retrouve des gens à zéro ou deux primaires."""

    __tablename__ = "watch_primary_group_overrides"

    __table_args__ = (Index("ix_watch_primary_group_person", "tenant_id", "person_id"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    person_id: Mapped[UUID] = mapped_column(Uuid)
    group_id: Mapped[UUID] = mapped_column(Uuid)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_by_account_id: Mapped[UUID] = mapped_column(Uuid)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ReferentHistoryModel(Base):
    """Append-only. `referent_person_id` NULL = **début d'un trou**, daté.

    « Sans référent » n'est pas actionnable ; « sans référent depuis quatre mois » l'est."""

    __tablename__ = "watch_referent_history"

    __table_args__ = (
        Index("ix_watch_referent_history_person", "tenant_id", "person_id", "observed_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    person_id: Mapped[UUID] = mapped_column(Uuid)
    referent_person_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    origin: Mapped[str | None] = mapped_column(String, nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    cause: Mapped[str] = mapped_column(String)


class ContactAttemptModel(Base):
    """Une tentative de contact — écrite **au départ**, pas au retour.

    On sort vers WhatsApp ou le téléphone et on ne revient pas. Sans cette ligne posée avant de
    perdre la main, le produit conclurait à un échec de veille là où il y a eu un appel de vingt
    minutes : le pire des faux négatifs, celui qui invalide un succès réel."""

    __tablename__ = "watch_contact_attempts"

    __table_args__ = (
        Index("ix_watch_contact_signal", "signal_id"),
        Index("ix_watch_contact_pending", "tenant_id", "by_account_id", "result"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    signal_id: Mapped[UUID] = mapped_column(Uuid)
    by_account_id: Mapped[UUID] = mapped_column(Uuid)
    channel: Mapped[str] = mapped_column(String)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    result: Mapped[str] = mapped_column(String)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


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
