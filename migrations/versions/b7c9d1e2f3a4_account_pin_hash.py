"""account pin_hash (credential mobile — décision C)

Ajoute `accounts.pin_hash` : le PIN mobile, distinct du `password_hash` backoffice.
Colonne **nullable** (aucun credential posé à l'enrôlement, M-0) — pas de backfill.

Revision ID: b7c9d1e2f3a4
Revises: 2f14fb983fac
Create Date: 2026-07-15 16:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7c9d1e2f3a4'
down_revision: Union[str, Sequence[str], None] = '2f14fb983fac'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("accounts", sa.Column("pin_hash", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("accounts", "pin_hash")
