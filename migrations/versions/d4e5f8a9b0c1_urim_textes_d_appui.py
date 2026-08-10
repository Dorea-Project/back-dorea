"""urim_textes_d_appui : la chaîne de textes qu'un sermon convoque

Deux prédications du Pasteur X, huit textes puis douze, et un seul passage dans le modèle.
Tout le reste — l'antécédent, l'annonce, l'attestation — vivait dans ses notes.

⚠️ `raw` est conservé **même quand la référence ne résout pas**, et c'est l'objet de la table.
Ses notes portaient `Hb 2v29` (Hébreux 2 compte 18 versets) et `Ph 28v9` (Philippiens en
compte 4) : Urim savait détecter cela depuis le premier jour et ne l'avait jamais vu, faute
d'une surface où le pasteur soumette ses appuis. Ne stocker que ce qui résout effacerait
exactement ce qu'il faut lui montrer.

Les colonnes résolues sont nullables et le motif ne se fige pas : il se recalcule à
l'affichage, parce que le corpus peut apprendre demain un sigle qu'il ignore aujourd'hui.

Revision ID: d4e5f8a9b0c1
Revises: c3d4e5f8a9b0
Create Date: 2026-08-10 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd4e5f8a9b0c1'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f8a9b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "urim_preparation_support",
        sa.Column("preparation_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.SmallInteger(), nullable=False),
        sa.Column("raw", sa.String(), nullable=False),
        sa.Column("book_id", sa.SmallInteger(), nullable=True),
        sa.Column("chapter", sa.SmallInteger(), nullable=True),
        sa.Column("verse_start", sa.SmallInteger(), nullable=True),
        sa.Column("verse_end", sa.SmallInteger(), nullable=True),
        sa.ForeignKeyConstraint(
            ["preparation_id"], ["urim_preparation.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("preparation_id", "ordinal"),
    )


def downgrade() -> None:
    op.drop_table("urim_preparation_support")
