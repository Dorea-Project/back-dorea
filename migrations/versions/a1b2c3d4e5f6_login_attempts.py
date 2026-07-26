"""login_attempts : verrou anti-brute-force du login (DOREA-004)

Compteur d'échecs par identifiant (téléphone/e-mail) + verrou temporaire à backoff. Le login
refuse si verrouillé, compte chaque échec, remet à zéro au succès.

Revision ID: a1b2c3d4e5f6
Revises: f5c6d7e8091a
Create Date: 2026-07-19 01:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'f5c6d7e8091a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "login_attempts",
        sa.Column("identifier", sa.String(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("identifier"),
    )


def downgrade() -> None:
    op.drop_table("login_attempts")
