"""attendance tables (M6-0 — rencontres & présence)

Crée `gatherings` (la rencontre : réunion/formation/culte/événement) et
`attendance_records` (un signal présent/excusé par personne et par rencontre ; l'absence
est déduite du roster, non stockée).

Revision ID: a1e7d4c05f92
Revises: f6c2d9a10b34
Create Date: 2026-07-16 08:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1e7d4c05f92'
down_revision: Union[str, Sequence[str], None] = 'f6c2d9a10b34'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "gatherings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("group_id", sa.Uuid(), nullable=True),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_by_account_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_gatherings_group", "gatherings", ["group_id"])
    op.create_index("ix_gatherings_tenant", "gatherings", ["tenant_id"])

    op.create_table(
        "attendance_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("gathering_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("mark", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("reason", sa.String(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_by_account_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["gathering_id"], ["gatherings.id"]),
    )
    op.create_index(
        "uq_attendance_gathering_account",
        "attendance_records",
        ["gathering_id", "account_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_attendance_gathering_account", table_name="attendance_records")
    op.drop_table("attendance_records")
    op.drop_index("ix_gatherings_tenant", table_name="gatherings")
    op.drop_index("ix_gatherings_group", table_name="gatherings")
    op.drop_table("gatherings")
