"""Modèles ORM IAM — définition des tables détenues par ce backend (M1 §1).

Les valeurs d'enum sont stockées en `String` : ce backend possède le schéma et
choisit ce mapping ; on lit/écrit les chaînes brutes et le mapper
(`repositories.py`) les convertit en enums du domaine.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AccountModel(Base):
    __tablename__ = "accounts"

    # Unicité de l'e-mail **quand il est présent** : le login backoffice se fait
    # par e-mail, deux comptes ne peuvent le partager. Index *partiel* → plusieurs
    # comptes tél-only (email NULL) restent permis.
    __table_args__ = (
        Index(
            "uq_accounts_email_not_null",
            "email",
            unique=True,
            postgresql_where=text("email IS NOT NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    phone_number: Mapped[str] = mapped_column(String, unique=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    last_name: Mapped[str | None] = mapped_column(String, nullable=True)
    first_name: Mapped[str | None] = mapped_column(String, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String, nullable=True)  # backoffice (email)
    pin_hash: Mapped[str | None] = mapped_column(String, nullable=True)  # mobile (phone)
    hash_algo_version: Mapped[int | None] = mapped_column(nullable=True)
    is_phone_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_by_type: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)


class MembershipModel(Base):
    __tablename__ = "memberships"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    account_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("accounts.id"))
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    status: Mapped[str] = mapped_column(String)
    previous_status: Mapped[str | None] = mapped_column(String, nullable=True)
    last_transition_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_by_account_id: Mapped[UUID] = mapped_column(Uuid)
    active_absence_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closure_reason: Mapped[str | None] = mapped_column(String, nullable=True)

    role_assignments: Mapped[list[RoleAssignmentModel]] = relationship(
        back_populates="membership", lazy="selectin"
    )


class MemberTransferModel(Base):
    __tablename__ = "member_transfers"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    account_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("accounts.id"))
    from_tenant_id: Mapped[UUID] = mapped_column(Uuid)
    to_tenant_id: Mapped[UUID] = mapped_column(Uuid)
    to_group_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    status: Mapped[str] = mapped_column(String)
    requested_by_account_id: Mapped[UUID] = mapped_column(Uuid)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved_by_account_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ChurchInvitationModel(Base):
    __tablename__ = "church_invitations"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    code: Mapped[str] = mapped_column(String, unique=True)
    created_by_account_id: Mapped[UUID] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RoleAssignmentModel(Base):
    __tablename__ = "role_assignments"

    # NB : l'invariant « 1 owner / tenant » vit désormais sur `tenant_ownerships`
    # (l'owner n'est plus un rôle). `tenant_id` reste dénormalisé pour les requêtes
    # de portée (ex. comptage des group_leaders).

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    membership_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("memberships.id"))
    tenant_id: Mapped[UUID] = mapped_column(Uuid)  # dénormalisé (P0.2)
    role: Mapped[str] = mapped_column(String)
    group_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    assigned_by_account_id: Mapped[UUID] = mapped_column(Uuid)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_reason: Mapped[str | None] = mapped_column(String, nullable=True)

    membership: Mapped[MembershipModel] = relationship(back_populates="role_assignments")
