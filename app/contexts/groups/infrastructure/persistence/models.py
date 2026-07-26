"""Modèle ORM Groupes — table `groups` (schéma détenu par ce backend, M4).

`path` = chemin matérialisé (`/{racine}/…/{self}/`) pour l'autorisation par sous-arbre.
`parent_group_id` (structure) et `multiplied_from_id` (lignée) sont deux liens distincts (§2).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class GroupModel(Base):
    __tablename__ = "groups"

    __table_args__ = (
        Index("ix_groups_tenant", "tenant_id"),
        Index("ix_groups_parent", "parent_group_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    name: Mapped[str] = mapped_column(String)
    type: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    # Appartenance structurelle (récursif) — self-FK.
    parent_group_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("groups.id"), nullable=True
    )
    # Chemin matérialisé `/{racine}/…/{self}/` — portée sous-arbre en O(1).
    path: Mapped[str] = mapped_column(String)
    # Lignée (cellule qui se multiplie, G-3) — self-FK, distinct du parent structurel.
    multiplied_from_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("groups.id"), nullable=True
    )
    generation: Mapped[int] = mapped_column(Integer, default=1)  # G1 puis +1 par multiplication
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_by_account_id: Mapped[UUID] = mapped_column(Uuid)


class GroupMembershipModel(Base):
    """Appartenance « compte-groupe » (M4 §6), distincte de la Membership église."""

    __tablename__ = "group_memberships"

    __table_args__ = (
        Index("ix_group_memberships_group", "group_id"),
        Index("ix_group_memberships_account", "account_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    group_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("groups.id"))
    account_id: Mapped[UUID] = mapped_column(Uuid)
    tenant_id: Mapped[UUID] = mapped_column(Uuid)  # dénormalisé (portée)
    status: Mapped[str] = mapped_column(String)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    joined_by_account_id: Mapped[UUID] = mapped_column(Uuid)
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class GroupInvitationModel(Base):
    """Lien/code d'invitation à un groupe (M4 §6, G-1b)."""

    __tablename__ = "group_invitations"

    __table_args__ = (
        Index("uq_group_invitation_code", "code", unique=True),
        Index("ix_group_invitations_group", "group_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    group_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("groups.id"))
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    code: Mapped[str] = mapped_column(String)
    created_by_account_id: Mapped[UUID] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
