"""drop_annexe_scaffolding : supprime le scaffolding annexe mort (dette D5, M0 §4.1)

L'annexe est désormais une église-fille (tenant à `parent_id` + Owner propre), plus
une partition interne. La table `annexes` et les colonnes `annexe_id` (jamais
écrites, 0 ligne) sont supprimées.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-07-23 12:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("memberships", "annexe_id")
    op.drop_column("role_assignments", "annexe_id")
    op.drop_table("annexes")


def downgrade() -> None:
    op.create_table(
        "annexes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.add_column("role_assignments", sa.Column("annexe_id", sa.Uuid(), nullable=True))
    op.add_column("memberships", sa.Column("annexe_id", sa.Uuid(), nullable=True))
