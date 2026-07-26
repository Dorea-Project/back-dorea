"""group_memberships table (M4 G-1 — appartenance compte × groupe)

Crée `group_memberships` : « X est dans le groupe G » (active/left), distincte de la
Membership église (IAM).

Revision ID: d4a2b7e9c1f0
Revises: c3f8a1d420be
Create Date: 2026-07-16 06:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4a2b7e9c1f0'
down_revision: Union[str, Sequence[str], None] = 'c3f8a1d420be'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "group_memberships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("group_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("joined_by_account_id", sa.Uuid(), nullable=False),
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"]),
    )
    op.create_index("ix_group_memberships_group", "group_memberships", ["group_id"])
    op.create_index("ix_group_memberships_account", "group_memberships", ["account_id"])


def downgrade() -> None:
    op.drop_index("ix_group_memberships_account", table_name="group_memberships")
    op.drop_index("ix_group_memberships_group", table_name="group_memberships")
    op.drop_table("group_memberships")
