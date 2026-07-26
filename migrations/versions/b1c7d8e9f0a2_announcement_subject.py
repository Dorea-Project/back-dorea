"""annonces anti-vitrine (M8-2) : le sujet (concerns_account_id) ≠ l'auteur

Le décompte des réactions n'est plus un score sur le post : il est remis au **sujet** de
l'annonce (la famille en deuil, les parents). D'où `concerns_account_id`, distinct de
`author_account_id`. Le décès devient par ailleurs une **mobilisation** (veillée) — donnée,
pas schéma.

Revision ID: b1c7d8e9f0a2
Revises: a9f5b6c3d2e4
Create Date: 2026-07-17 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1c7d8e9f0a2'
down_revision: Union[str, Sequence[str], None] = 'a9f5b6c3d2e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "announcements", sa.Column("concerns_account_id", sa.Uuid(), nullable=True)
    )
    op.create_index(
        "ix_announcements_concerns", "announcements", ["concerns_account_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_announcements_concerns", table_name="announcements")
    op.drop_column("announcements", "concerns_account_id")
