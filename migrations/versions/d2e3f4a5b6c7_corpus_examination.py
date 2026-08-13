"""L'examen sans trouvaille — « on a regardé, et il n'y avait rien à dire »

Le lot des mises en garde a curé 4 396 unités ; 2 525 n'en appelaient aucune. Rien ne
l'enregistrait, et une unité examinée sans trouvaille était donc indiscernable d'une unité
jamais examinée : la couverture annonçait 41 % pour ~96 % de travail réel, et le lot n'était
pas reprenable.

Même distinction que `absent` sur les pesées (S38), mais rangée ailleurs : `absent` est une
information que le pasteur lit, l'examen sans trouvaille est une trace de curation.

Le rattrapage ne peut porter que sur ce qui est certain — les unités qui portent aujourd'hui
une mise en garde signée par l'IA. Les 2 525 vides sont perdues : l'information n'a jamais été
écrite. Elles seront réexaminées, ce qui coûte environ 1,30 €.

Revision ID: d2e3f4a5b6c7
Revises: c9d2e3f4a5b6
"""

import sqlalchemy as sa
from alembic import op

revision = "d2e3f4a5b6c7"
down_revision = "c9d2e3f4a5b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "urim_corpus_examination",
        sa.Column("pericope_id", sa.Uuid(), nullable=False),
        sa.Column("dimension", sa.String(), nullable=False),
        sa.Column("found", sa.Integer(), nullable=False),
        sa.Column("examined_by", sa.String(), nullable=False),
        sa.Column("examined_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["pericope_id"], ["urim_corpus_pericope.id"]),
        sa.PrimaryKeyConstraint("pericope_id", "dimension"),
        sa.CheckConstraint(
            "dimension IN ('caveat','context_note')", name="examination_dimension_close"
        ),
        sa.CheckConstraint("found >= 0", name="examination_found_positif"),
    )

    # Le rattrapage de ce qui est certain : une unité qui porte une mise en garde a forcément
    # été examinée. `examined_at` reprend la date de la curation elle-même — inventer un
    # « maintenant » ferait mentir la trace sur le jour où le travail a eu lieu.
    op.execute(
        """
        INSERT INTO urim_corpus_examination
            (pericope_id, dimension, found, examined_by, examined_at)
        SELECT pericope_id, 'caveat', count(*), min(reviewed_by), min(reviewed_at)
        FROM urim_corpus_doctrinal_caveat
        GROUP BY pericope_id
        """
    )


def downgrade() -> None:
    op.drop_table("urim_corpus_examination")
