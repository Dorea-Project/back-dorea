"""devices : appareils (jetons push) pour les notifications (transverse)

Une personne enregistre le jeton push de son appareil ; on pousse vers lui les notifications
(RDV confirmé, événement qui m'atteint, annonce…).

Revision ID: b1829304b5c6
Revises: a071829304b5
Create Date: 2026-07-18 23:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1829304b5c6'
down_revision: Union[str, Sequence[str], None] = 'a071829304b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "devices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("token", sa.String(), nullable=False),
        sa.Column("platform", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token", name="uq_device_token"),
    )
    op.create_index("ix_devices_account", "devices", ["account_id"])


def downgrade() -> None:
    op.drop_index("ix_devices_account", table_name="devices")
    op.drop_table("devices")
