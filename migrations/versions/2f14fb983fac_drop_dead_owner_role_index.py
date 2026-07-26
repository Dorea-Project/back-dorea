"""drop dead owner-role index

Revision ID: 2f14fb983fac
Revises: 73e05c44d72a
Create Date: 2026-07-15 15:56:31.153107

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2f14fb983fac'
down_revision: Union[str, Sequence[str], None] = '73e05c44d72a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Retire l'index partiel obsolète (l'owner n'est plus un rôle → invariant sur
    `tenant_ownerships`)."""
    op.drop_index("uq_one_active_owner_per_tenant", table_name="role_assignments")


def downgrade() -> None:
    op.create_index(
        "uq_one_active_owner_per_tenant",
        "role_assignments",
        ["tenant_id"],
        unique=True,
        postgresql_where=sa.text("role = 'owner' AND revoked_at IS NULL"),
        sqlite_where=sa.text("role = 'owner' AND revoked_at IS NULL"),
    )
