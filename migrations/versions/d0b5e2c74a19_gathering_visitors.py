"""gathering_visitors table (M6-3 — visages nouveaux)

Crée `gathering_visitors` : un présent hors-roster capturé au nom (l'entonnoir de croissance).

Revision ID: d0b5e2c74a19
Revises: c9a4f1b6d208
Create Date: 2026-07-16 09:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd0b5e2c74a19'
down_revision: Union[str, Sequence[str], None] = 'c9a4f1b6d208'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "gathering_visitors",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("gathering_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("captured_by_account_id", sa.Uuid(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["gathering_id"], ["gatherings.id"]),
    )
    op.create_index("ix_gathering_visitors_gathering", "gathering_visitors", ["gathering_id"])


def downgrade() -> None:
    op.drop_index("ix_gathering_visitors_gathering", table_name="gathering_visitors")
    op.drop_table("gathering_visitors")
