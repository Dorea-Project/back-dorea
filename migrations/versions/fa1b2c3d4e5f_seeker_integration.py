"""seeker integration : le chercheur devient membre (M9-4 — Intégrer)

Back-link du chercheur vers le compte qu'il est devenu (`integrated_account_id`) et l'instant
de l'intégration. Ferme la boucle missionnaire : `accompanied` → `integrated`.

Revision ID: fa1b2c3d4e5f
Revises: f9a3c1d05e28
Create Date: 2026-07-18 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fa1b2c3d4e5f'
down_revision: Union[str, Sequence[str], None] = 'f9a3c1d05e28'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "seekers",
        sa.Column("integrated_account_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "seekers",
        sa.Column("integrated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("seekers", "integrated_at")
    op.drop_column("seekers", "integrated_account_id")
