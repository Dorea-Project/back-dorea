"""group_invitations table (M4 G-1b — lien d'invitation)

Crée `group_invitations` : code réutilisable, expirable, révocable, pour rejoindre un
groupe par lien (self-join mobile).

Revision ID: f6c2d9a10b34
Revises: e5b1c8f302a7
Create Date: 2026-07-16 07:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6c2d9a10b34'
down_revision: Union[str, Sequence[str], None] = 'e5b1c8f302a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "group_invitations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("group_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("created_by_account_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"]),
    )
    op.create_index("uq_group_invitation_code", "group_invitations", ["code"], unique=True)
    op.create_index("ix_group_invitations_group", "group_invitations", ["group_id"])


def downgrade() -> None:
    op.drop_index("ix_group_invitations_group", table_name="group_invitations")
    op.drop_index("uq_group_invitation_code", table_name="group_invitations")
    op.drop_table("group_invitations")
