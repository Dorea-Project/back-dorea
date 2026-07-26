"""gathering_rsvps table (M6 — « je viens », pré-signal alimenté par M8 convoquer)

Un RSVP par (rencontre, compte) : pré-remplit le roster sans écrire de présence réelle.

Revision ID: d3e9f0a2b4c6
Revises: c2d8e9f1a3b5
Create Date: 2026-07-18 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd3e9f0a2b4c6'
down_revision: Union[str, Sequence[str], None] = 'c2d8e9f1a3b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "gathering_rsvps",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("gathering_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("rsvp_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["gathering_id"], ["gatherings.id"]),
        sa.UniqueConstraint("gathering_id", "account_id", name="uq_rsvp_per_account"),
    )
    op.create_index("ix_gathering_rsvps_gathering", "gathering_rsvps", ["gathering_id"])


def downgrade() -> None:
    op.drop_index("ix_gathering_rsvps_gathering", table_name="gathering_rsvps")
    op.drop_table("gathering_rsvps")
