"""events : événements + participants confirmés + réactions (module Event, E-0 portée église)

Le happening publié (date/lieu/géo/affiche) auquel les membres réagissent et confirment leur
présence. Portée CHURCH pour l'instant ; DENOMINATION/PLATFORM viendront avec le compte Business.

Revision ID: fd4e5f607182
Revises: fc3d4e5f6071
Create Date: 2026-07-18 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fd4e5f607182'
down_revision: Union[str, Sequence[str], None] = 'fc3d4e5f6071'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("author_account_id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("place_label", sa.String(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("media_urls", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("scope", sa.String(), nullable=False, server_default="church"),
        sa.Column("status", sa.String(), nullable=False, server_default="published"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_events_tenant_status", "events", ["tenant_id", "status"])

    op.create_table(
        "event_participants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"]),
        sa.UniqueConstraint("event_id", "account_id", name="uq_event_participant"),
    )
    op.create_index("ix_event_participants_event", "event_participants", ["event_id"])

    op.create_table(
        "event_reactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("reacted_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"]),
        sa.UniqueConstraint("event_id", "account_id", name="uq_event_reaction"),
    )
    op.create_index("ix_event_reactions_event", "event_reactions", ["event_id"])


def downgrade() -> None:
    op.drop_index("ix_event_reactions_event", table_name="event_reactions")
    op.drop_table("event_reactions")
    op.drop_index("ix_event_participants_event", table_name="event_participants")
    op.drop_table("event_participants")
    op.drop_index("ix_events_tenant_status", table_name="events")
    op.drop_table("events")
