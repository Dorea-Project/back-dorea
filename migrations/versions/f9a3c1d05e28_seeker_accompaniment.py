"""seeker accompaniment : relais humain (M9-3 — Accompagner)

Colonnes d'accompagnement sur `seekers` : qui a pris le relais et quand, et la clôture
(sans jugement). Le chercheur `accepted` peut devenir `accompanied` puis `integrated`/`closed`.

Revision ID: f9a3c1d05e28
Revises: e4f0a1b2c3d7
Create Date: 2026-07-18 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f9a3c1d05e28'
down_revision: Union[str, Sequence[str], None] = 'e4f0a1b2c3d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "seekers",
        sa.Column("accompanied_by_account_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "seekers",
        sa.Column("accompanied_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "seekers",
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("seekers", "closed_at")
    op.drop_column("seekers", "accompanied_at")
    op.drop_column("seekers", "accompanied_by_account_id")
