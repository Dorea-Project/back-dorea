"""group generation (M4 G-3 — lignée cellulaire)

Ajoute `groups.generation` (G1 à la création, +1 à chaque multiplication).

Revision ID: e5b1c8f302a7
Revises: d4a2b7e9c1f0
Create Date: 2026-07-16 07:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5b1c8f302a7'
down_revision: Union[str, Sequence[str], None] = 'd4a2b7e9c1f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "groups",
        sa.Column("generation", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_column("groups", "generation")
