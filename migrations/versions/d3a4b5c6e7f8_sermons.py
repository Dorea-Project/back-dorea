"""sermons : socle du sermon qui vit au-delà du dimanche (S-0)

Le pasteur dépose son sermon (texte) ; cycle de vie brouillon → approuvé → publié. Le digest IA,
les capsules et le compagnon viendront (S-1…S-4) au-dessus de ce socle.

Revision ID: d3a4b5c6e7f8
Revises: c2930415c6d7
Create Date: 2026-07-18 23:59:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd3a4b5c6e7f8'
down_revision: Union[str, Sequence[str], None] = 'c2930415c6d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sermons",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("author_account_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("reference", sa.String(), nullable=True),
        sa.Column("source_kind", sa.String(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("preached_on", sa.Date(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sermons_tenant", "sermons", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_sermons_tenant", table_name="sermons")
    op.drop_table("sermons")
