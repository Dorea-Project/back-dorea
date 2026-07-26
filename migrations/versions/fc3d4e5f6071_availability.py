"""appointments availability : disponibilité récurrente des pasteurs + pasteur du RDV

Le pasteur (ou la secrétaire) pose des plages hebdomadaires (`availability_rules`) qui engendrent
des créneaux ; un rendez-vous confirmé porte le pasteur du créneau (`with_pastor_account_id`).

Revision ID: fc3d4e5f6071
Revises: fb2c3d4e5f60
Create Date: 2026-07-18 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fc3d4e5f6071'
down_revision: Union[str, Sequence[str], None] = 'fb2c3d4e5f60'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "appointments",
        sa.Column("with_pastor_account_id", sa.Uuid(), nullable=True),
    )
    op.create_table(
        "availability_rules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("pastor_account_id", sa.Uuid(), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("start_minute", sa.Integer(), nullable=False),
        sa.Column("end_minute", sa.Integer(), nullable=False),
        sa.Column("slot_minutes", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_availability_tenant_active", "availability_rules", ["tenant_id", "active"]
    )
    op.create_index(
        "ix_availability_pastor", "availability_rules", ["pastor_account_id", "tenant_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_availability_pastor", table_name="availability_rules")
    op.drop_index("ix_availability_tenant_active", table_name="availability_rules")
    op.drop_table("availability_rules")
    op.drop_column("appointments", "with_pastor_account_id")
