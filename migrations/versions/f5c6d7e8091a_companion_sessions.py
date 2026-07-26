"""companion_sessions : la conversation privée d'un membre avec un sermon (S-3)

Le compagnon déroule l'arbre gelé du digest : « as-tu vécu le culte ? » → consolidation (oui) ou
enseignement (non). L'agrégat porte l'état (répondu ? où en est-on ?) ; le contenu vient du digest.

Revision ID: f5c6d7e8091a
Revises: e4b5c6d7f809
Create Date: 2026-07-19 00:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f5c6d7e8091a'
down_revision: Union[str, Sequence[str], None] = 'e4b5c6d7f809'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "companion_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sermon_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("member_account_id", sa.Uuid(), nullable=False),
        sa.Column("attended", sa.Boolean(), nullable=True),
        sa.Column("step", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["sermon_id"], ["sermons.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_companion_member_sermon",
        "companion_sessions",
        ["member_account_id", "sermon_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_companion_member_sermon", table_name="companion_sessions")
    op.drop_table("companion_sessions")
