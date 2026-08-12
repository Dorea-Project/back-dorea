"""Le registre de relecture — ce qu'un humain a jugé, et qui ne se rejuge pas

Le détecteur d'écarts signalait 291 unités et les resignalait à chaque passage : un relecteur
qui en traitait cinquante retrouvait les mêmes le lendemain. Une file qui ne décroît pas n'est
pas une file, c'est un reproche permanent.

`judged_fingerprint` périme le verdict quand la curation jugée change — même patron que
`corpus_snapshot` et que `input_hash` sur les suggestions du modèle.

Le `CHECK` sur `reviewed_by` est le cœur du dispositif : une machine ne vide pas la file
qu'elle a remplie.

Revision ID: c9d2e3f4a5b6
Revises: b8c9d2e3f4a5
"""

import sqlalchemy as sa
from alembic import op

revision = "c9d2e3f4a5b6"
down_revision = "b8c9d2e3f4a5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "urim_corpus_review",
        sa.Column("pericope_id", sa.Uuid(), nullable=False),
        sa.Column("scope", sa.String(), nullable=False),
        sa.Column("verdict", sa.String(), nullable=False),
        sa.Column("judged_fingerprint", sa.String(length=32), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.String(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["pericope_id"], ["urim_corpus_pericope.id"]),
        sa.PrimaryKeyConstraint("pericope_id", "scope"),
        sa.CheckConstraint(
            "verdict IN ('accepte','corrige','a_reprendre')", name="review_verdict_clos"
        ),
        sa.CheckConstraint("reviewed_by <> 'ia-mistral'", name="review_signature_humaine"),
    )
    op.create_index(
        "ix_urim_review_verdict", "urim_corpus_review", ["verdict", "reviewed_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_urim_review_verdict", table_name="urim_corpus_review")
    op.drop_table("urim_corpus_review")
