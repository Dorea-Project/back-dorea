"""urim : la demande d'interpretation d'une piece en langue locale

**D62, etape 7 du plan.** Le pasteur preche en francais ; une part de son
assemblee entend le dioula, le baoule ou le malinke. D62 a tranche que ce travail
est **un service tenu par l'equipe Dorea** — un interprete maitrise par langue —
et non un moteur : aucune synthese vocale ne dit ces langues, et faire semblant
serait pire que se taire.

## Pourquoi cette table est possible aujourd'hui, et pas la semaine derniere

🔴 **L'interprete ecoute la piece, il ne lit pas un transcript.** Tant que
l'interpretation partait d'une synthese validee, elle attendait le transcript,
qui attend la mesure dans trois eglises. D71 l'a fait partir de l'audio ecoute :
**elle n'attend plus rien**.

## Aucun delai n'est promis, et c'est une decision

⚠️ **Il n'y a pas de colonne d'echeance.** Le pasteur demande le samedi et
voudrait publier le samedi soir ; personne n'a encore dit si l'equipe tient la
journee. Un delai affiche est une promesse — l'etat, lui, est vrai a chaque
instant sans engager quiconque. La colonne s'ajoutera le jour ou l'engagement
existera, pas avant.

## Une piece, une langue, une fois

L'index unique tient la regle : redemander la meme chose n'ouvre pas un second
travail dans la file de l'equipe. Un pasteur qui appuie deux fois, ou dont la
reponse s'est perdue, retrouve sa demande — il n'en cree pas une seconde.

## Le refus porte son motif

🔴 *Un travail abandonne laisse une trace, jamais un silence.* Une demande qui
disparait est indiscernable d'une demande jamais partie, et le pasteur
attendrait un samedi soir devant un ecran muet.

Revision ID: b8e34f10c7d2
Revises: a4d71c9e5b30
Create Date: 2026-09-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8e34f10c7d2'
down_revision: Union[str, Sequence[str], None] = 'a4d71c9e5b30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "urim_interpretation",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("piece_id", sa.Uuid(), nullable=False),
        sa.Column("church_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by", sa.Uuid(), nullable=False),
        # Du texte libre : les langues de Cote d'Ivoire ne rentrent pas dans une
        # enumeration ecrite a Abidjan, et un nom mutile est une langue mal
        # ecrite rendue a celui qui l'a nommee.
        sa.Column("language", sa.String(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        # L'audio rendu par l'interprete. Nul tant que le travail n'est pas fini.
        sa.Column("media_url", sa.String(), nullable=True),
        # Pourquoi l'equipe a refuse. Nul sauf sur un refus.
        sa.Column("refused_reason", sa.String(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("taken_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "state IN ('demandée','prise','rendue','refusée')",
            name="interpretation_state",
        ),
        sa.CheckConstraint("length(language) > 0", name="interpretation_langue_non_vide"),
    )
    # Une piece, une langue, une fois.
    op.create_index(
        "ix_urim_interpretation_unique",
        "urim_interpretation",
        ["piece_id", "language"],
        unique=True,
    )
    # La file de l'equipe : ce qui attend, du plus ancien au plus recent.
    op.create_index(
        "ix_urim_interpretation_file", "urim_interpretation", ["state", "requested_at"]
    )


def downgrade() -> None:
    # ⚠️ Ce qui part ici, ce sont **des heures de travail humain** : un interprete
    # par langue, piece par piece. Les audios survivent dans le `MediaStore`,
    # orphelins de tout ce qui disait a quelle predication ils repondent.
    op.drop_index("ix_urim_interpretation_file", table_name="urim_interpretation")
    op.drop_index("ix_urim_interpretation_unique", table_name="urim_interpretation")
    op.drop_table("urim_interpretation")
