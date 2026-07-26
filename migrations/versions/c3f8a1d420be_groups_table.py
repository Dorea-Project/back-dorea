"""groups table (M4 G-0 — arbre typé récursif, chemin matérialisé)

Crée `groups` : nœud typé (cellule/ministere/classe), récursif (`parent_group_id`),
avec chemin matérialisé (`path`) pour l'autorisation par sous-arbre et lien de lignée
(`multiplied_from_id`, crochet G-3).

Revision ID: c3f8a1d420be
Revises: b7c9d1e2f3a4
Create Date: 2026-07-16 06:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3f8a1d420be'
down_revision: Union[str, Sequence[str], None] = 'b7c9d1e2f3a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "groups",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("parent_group_id", sa.Uuid(), nullable=True),
        sa.Column("path", sa.String(), nullable=False),
        sa.Column("multiplied_from_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_account_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["parent_group_id"], ["groups.id"]),
        sa.ForeignKeyConstraint(["multiplied_from_id"], ["groups.id"]),
    )
    op.create_index("ix_groups_tenant", "groups", ["tenant_id"])
    op.create_index("ix_groups_parent", "groups", ["parent_group_id"])


def downgrade() -> None:
    op.drop_index("ix_groups_parent", table_name="groups")
    op.drop_index("ix_groups_tenant", table_name="groups")
    op.drop_table("groups")
