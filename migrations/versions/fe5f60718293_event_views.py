"""event views : traçage des vues (tableau de bord de rayonnement de l'événement)

Une vue distincte par spectateur, portant sa dénomination — nourrit « les vus par dénomination ».

Revision ID: fe5f60718293
Revises: fd4e5f607182
Create Date: 2026-07-18 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fe5f60718293'
down_revision: Union[str, Sequence[str], None] = 'fd4e5f607182'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "event_views",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("viewer_account_id", sa.Uuid(), nullable=False),
        sa.Column("denomination", sa.String(), nullable=True),
        sa.Column("viewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"]),
        sa.UniqueConstraint("event_id", "viewer_account_id", name="uq_event_view"),
    )
    op.create_index("ix_event_views_event", "event_views", ["event_id"])


def downgrade() -> None:
    op.drop_index("ix_event_views_event", table_name="event_views")
    op.drop_table("event_views")
