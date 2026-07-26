"""scheduled_notifications : outbox du fan-out asynchrone (rappels, diffusions différées)

Un contexte planifie un envoi (cible déjà résolue + quand) ; un dispatcher (cron externe via la
route Plateforme) envoie ce qui est dû et marque le job. Le rappel de RDV en est le premier client.

Revision ID: c2930415c6d7
Revises: b1829304b5c6
Create Date: 2026-07-18 23:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c2930415c6d7'
down_revision: Union[str, Sequence[str], None] = 'b1829304b5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "scheduled_notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_ids", sa.JSON(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=True),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_scheduled_notifications_due",
        "scheduled_notifications",
        ["status", "scheduled_for"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_scheduled_notifications_due", table_name="scheduled_notifications"
    )
    op.drop_table("scheduled_notifications")
