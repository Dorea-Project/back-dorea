"""church_invitations table (M-5 — rejoindre une église par lien/code)

Un lien réutilisable/expirable/révocable qui fait entrer un compte dans une église en `invited`,
sans forcer une cellule (pendant église-niveau de l'invitation de groupe).

Revision ID: c2d8e9f1a3b5
Revises: b1c7d8e9f0a2
Create Date: 2026-07-18 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c2d8e9f1a3b5'
down_revision: Union[str, Sequence[str], None] = 'b1c7d8e9f0a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "church_invitations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("created_by_account_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_church_invitation_code"),
    )
    op.create_index("ix_church_invitations_tenant", "church_invitations", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_church_invitations_tenant", table_name="church_invitations")
    op.drop_table("church_invitations")
