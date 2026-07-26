"""mission : mission_links + seekers + mission_reactions (M9-0 — la main tendue)

Liens d'invitation (personne|groupe) portant une carte (image/texte/lieu/géo) ; chercheurs
attribués (Seeker) ; réactions légères anonymes.

Revision ID: e4f0a1b2c3d7
Revises: d3e9f0a2b4c6
Create Date: 2026-07-18 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e4f0a1b2c3d7'
down_revision: Union[str, Sequence[str], None] = 'd3e9f0a2b4c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mission_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("inviter_account_id", sa.Uuid(), nullable=True),
        sa.Column("inviter_group_id", sa.Uuid(), nullable=True),
        sa.Column("message", sa.String(), nullable=False),
        sa.Column("media_urls", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("place_label", sa.String(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_mission_link_code"),
    )
    op.create_index("ix_mission_links_account", "mission_links", ["inviter_account_id"])
    op.create_index("ix_mission_links_group", "mission_links", ["inviter_group_id"])

    op.create_table(
        "seekers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("link_id", sa.Uuid(), nullable=False),
        sa.Column("inviter_account_id", sa.Uuid(), nullable=True),
        sa.Column("inviter_group_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["link_id"], ["mission_links.id"]),
    )
    op.create_index("ix_seekers_inviter_account", "seekers", ["inviter_account_id"])
    op.create_index("ix_seekers_inviter_group", "seekers", ["inviter_group_id"])

    op.create_table(
        "mission_reactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("link_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("reacted_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["link_id"], ["mission_links.id"]),
    )
    op.create_index("ix_mission_reactions_link", "mission_reactions", ["link_id"])


def downgrade() -> None:
    op.drop_index("ix_mission_reactions_link", table_name="mission_reactions")
    op.drop_table("mission_reactions")
    op.drop_index("ix_seekers_inviter_group", table_name="seekers")
    op.drop_index("ix_seekers_inviter_account", table_name="seekers")
    op.drop_table("seekers")
    op.drop_index("ix_mission_links_group", table_name="mission_links")
    op.drop_index("ix_mission_links_account", table_name="mission_links")
    op.drop_table("mission_links")
