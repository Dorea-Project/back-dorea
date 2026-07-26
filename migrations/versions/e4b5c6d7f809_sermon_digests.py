"""sermon_digests : le digest IA d'un sermon (S-1)

Généré en un seul appel au dépôt (résumé, points essentiels, capsules, Q&R de consolidation),
relu et approuvé par le pasteur, puis gelé. 1:1 avec le sermon.

Revision ID: e4b5c6d7f809
Revises: d3a4b5c6e7f8
Create Date: 2026-07-19 00:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e4b5c6d7f809'
down_revision: Union[str, Sequence[str], None] = 'd3a4b5c6e7f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sermon_digests",
        sa.Column("sermon_id", sa.Uuid(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("key_points", sa.JSON(), nullable=False),
        sa.Column("capsules", sa.JSON(), nullable=False),
        sa.Column("questions", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["sermon_id"], ["sermons.id"]),
        sa.PrimaryKeyConstraint("sermon_id"),
    )


def downgrade() -> None:
    op.drop_table("sermon_digests")
