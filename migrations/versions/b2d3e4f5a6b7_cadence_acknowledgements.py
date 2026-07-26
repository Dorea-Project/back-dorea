"""cadence_acknowledgements table (P1 — Fondation A : l'occurrence acquittée)

Une occurrence attendue **non tenue, motif connu** (état ACQUITTEE). Motif enum, jamais de note.
Un acquittement par (groupe, occurrence).

Revision ID: b2d3e4f5a6b7
Revises: a1c2e3f4a5b6
Create Date: 2026-07-25 10:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2d3e4f5a6b7'
down_revision: Union[str, Sequence[str], None] = 'a1c2e3f4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cadence_acknowledgements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("group_id", sa.Uuid(), nullable=False),
        sa.Column("occurrence_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("suspension_id", sa.Uuid(), nullable=True),
        sa.Column("acknowledged_by_account_id", sa.Uuid(), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("group_id", "occurrence_date", name="uq_ack_per_occurrence"),
    )
    op.create_index("ix_cadence_acks_group", "cadence_acknowledgements", ["group_id"])
    op.create_index("ix_cadence_acks_tenant", "cadence_acknowledgements", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_cadence_acks_tenant", table_name="cadence_acknowledgements")
    op.drop_index("ix_cadence_acks_group", table_name="cadence_acknowledgements")
    op.drop_table("cadence_acknowledgements")
