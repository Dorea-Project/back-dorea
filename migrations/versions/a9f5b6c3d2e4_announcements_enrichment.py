"""annonces enrichies (M8-1) : type+couleur, médias, expiration, portée plateforme, réactions

- `announcements` : + category, media_urls (JSON), expires_at ; tenant_id devient NULLABLE
  (annonce Dorea = aucune église) ; status open -> published, closed -> archived.
- `announcement_reactions` (nouvelle) : un emoji de la palette du type, 1 par (annonce, compte).

Revision ID: a9f5b6c3d2e4
Revises: f8e4a5b2c9d1
Create Date: 2026-07-17 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a9f5b6c3d2e4'
down_revision: Union[str, Sequence[str], None] = 'f8e4a5b2c9d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- announcements : les nouveaux axes ---
    op.add_column(
        "announcements",
        sa.Column("category", sa.String(), nullable=False, server_default="info"),
    )
    op.add_column(
        "announcements",
        sa.Column("media_urls", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "announcements", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True)
    )
    # Une annonce plateforme (Dorea) n'appartient à aucune église.
    op.alter_column("announcements", "tenant_id", existing_type=sa.Uuid(), nullable=True)
    # Statuts : open -> published, closed -> archived.
    op.execute("UPDATE announcements SET status = 'published' WHERE status = 'open'")
    op.execute("UPDATE announcements SET status = 'archived' WHERE status = 'closed'")
    op.alter_column("announcements", "category", server_default=None)
    op.alter_column("announcements", "media_urls", server_default=None)

    # --- réactions (emoji) ---
    op.create_table(
        "announcement_reactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("announcement_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("emoji", sa.String(), nullable=False),
        sa.Column("reacted_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["announcement_id"], ["announcements.id"]),
        sa.UniqueConstraint("announcement_id", "account_id", name="uq_reaction_per_account"),
    )
    op.create_index(
        "ix_announcement_reactions_announcement", "announcement_reactions", ["announcement_id"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_announcement_reactions_announcement", table_name="announcement_reactions"
    )
    op.drop_table("announcement_reactions")
    op.execute("UPDATE announcements SET status = 'open' WHERE status = 'published'")
    op.execute("UPDATE announcements SET status = 'closed' WHERE status = 'archived'")
    op.alter_column("announcements", "tenant_id", existing_type=sa.Uuid(), nullable=False)
    op.drop_column("announcements", "expires_at")
    op.drop_column("announcements", "media_urls")
    op.drop_column("announcements", "category")
