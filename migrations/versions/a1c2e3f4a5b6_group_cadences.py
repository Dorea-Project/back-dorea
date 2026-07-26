"""group_cadences table (P1 — Fondation A : le `Programme`, rythme attendu d'un groupe)

Stocke la **règle** de rythme d'un groupe (jamais le roster : l'interdit M6 tient). Au plus une
cadence active par groupe (index partiel sur canceled_at IS NULL).

Revision ID: a1c2e3f4a5b6
Revises: e5f6a7b8c9d0
Create Date: 2026-07-25 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1c2e3f4a5b6'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "group_cadences",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("group_id", sa.Uuid(), nullable=False),
        sa.Column("frequency", sa.String(), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=True),
        sa.Column("day_of_month", sa.Integer(), nullable=True),
        sa.Column("anchor_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("active_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("active_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_account_id", sa.Uuid(), nullable=False),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_group_cadences_tenant", "group_cadences", ["tenant_id"])
    op.create_index("ix_group_cadences_group", "group_cadences", ["group_id"])
    op.create_index(
        "uq_one_active_cadence_per_group",
        "group_cadences",
        ["group_id"],
        unique=True,
        postgresql_where=sa.text("canceled_at IS NULL"),
        sqlite_where=sa.text("canceled_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_one_active_cadence_per_group", table_name="group_cadences")
    op.drop_index("ix_group_cadences_group", table_name="group_cadences")
    op.drop_index("ix_group_cadences_tenant", table_name="group_cadences")
    op.drop_table("group_cadences")
