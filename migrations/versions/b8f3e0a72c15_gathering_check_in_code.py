"""gathering check_in_code (M6-1 — self-check-in)

Ajoute `gatherings.check_in_code` : le code de séance que le membre tape pour s'auto-marquer.

Revision ID: b8f3e0a72c15
Revises: a1e7d4c05f92
Create Date: 2026-07-16 08:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8f3e0a72c15'
down_revision: Union[str, Sequence[str], None] = 'a1e7d4c05f92'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("gatherings", sa.Column("check_in_code", sa.String(), nullable=True))
    op.create_index("ix_gatherings_check_in_code", "gatherings", ["check_in_code"])


def downgrade() -> None:
    op.drop_index("ix_gatherings_check_in_code", table_name="gatherings")
    op.drop_column("gatherings", "check_in_code")
