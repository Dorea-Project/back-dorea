"""announcements + announcement_responses (M8 — annonces à deux voix)

Crée `announcements` (intention + portée sous-arbre + statut) et `announcement_responses`
(la seconde voix : une ligne = « je viens / je sers / je porte »).

Revision ID: f8e4a5b2c9d1
Revises: e7d3f4a1b6c8
Create Date: 2026-07-17 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f8e4a5b2c9d1'
down_revision: Union[str, Sequence[str], None] = 'e7d3f4a1b6c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "announcements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("intent", sa.String(), nullable=False),
        sa.Column("scope_group_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("body", sa.String(), nullable=True),
        sa.Column("author_account_id", sa.Uuid(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("event_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("gathering_id", sa.Uuid(), nullable=True),
        sa.Column("slots_needed", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_announcements_tenant", "announcements", ["tenant_id"])

    op.create_table(
        "announcement_responses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("announcement_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["announcement_id"], ["announcements.id"]),
        sa.UniqueConstraint("announcement_id", "account_id", name="uq_response_per_account"),
    )
    op.create_index(
        "ix_announcement_responses_announcement",
        "announcement_responses",
        ["announcement_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_announcement_responses_announcement", table_name="announcement_responses"
    )
    op.drop_table("announcement_responses")
    op.drop_index("ix_announcements_tenant", table_name="announcements")
    op.drop_table("announcements")
