"""event moderation : signalements + retrait par la Plateforme (rayonnement gouverné)

Signalements des membres (`event_reports`) + retrait modéré (`taken_down`, motif + instant sur
`events`). Le garde-fou de la diffusion élargie.

Revision ID: a071829304b5
Revises: ff60718293a4
Create Date: 2026-07-18 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a071829304b5'
down_revision: Union[str, Sequence[str], None] = 'ff60718293a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("events", sa.Column("moderation_reason", sa.Text(), nullable=True))
    op.add_column(
        "events", sa.Column("taken_down_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_table(
        "event_reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("reporter_account_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"]),
        sa.UniqueConstraint("event_id", "reporter_account_id", name="uq_event_report"),
    )
    op.create_index("ix_event_reports_event", "event_reports", ["event_id"])


def downgrade() -> None:
    op.drop_index("ix_event_reports_event", table_name="event_reports")
    op.drop_table("event_reports")
    op.drop_column("events", "taken_down_at")
    op.drop_column("events", "moderation_reason")
