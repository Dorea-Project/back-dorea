"""urim : la piece taillee dans un culte, et publiee

**D70, etape 6 du plan.** Un dimanche donne une heure et demie d'un seul tenant :
une predication enchainee par une priere, avec du bruit et des chants au
demarrage. On ne publie pas ca. Le pasteur ecoute, coupe, et en tire deux pieces
qui sortent a trois jours d'intervalle.

Jusqu'ici la piece n'existait que sur le telephone. Cette table est l'endroit ou
elle traverse.

## Aucune purge, et pas de colonne pour en accueillir une

La matiere brute expire a sept jours parce qu'*un micro capte la salle* et qu'un
temoignage peut s'y trouver. Une piece est ce que son auteur a **ecoute puis
choisi** : le decoupage est le consentement, et un objet consenti n'a pas de date
de peremption.

## `capture_id` n'est pas une cle etrangere, et c'est delibere

Depuis D71, **plus rien ne monte tout seul** : les fragments bruts restent sur
l'appareil. La piece est donc **le premier objet de ce culte qui traverse**, et
sa capture d'origine n'existe tres probablement pas dans `urim_capture`. Une
contrainte referentielle refuserait la publication d'un dimanche parfaitement
valide.

L'identifiant est garde quand meme : il dit **de quel culte** vient la piece, et
deux pieces du meme dimanche se reconnaissent entre elles. Il ne promet pas qu'on
puisse y retourner.

## L'identifiant vient de l'appareil

Meme raison que la capture (D64) : le telephone produit un UUIDv4 avant que le
reseau existe. Republier la meme piece ne cree donc pas de doublon — la cle
primaire le tient, et un pasteur qui appuie deux fois sur « publier » dans un
tunnel ne se retrouve pas avec deux prieres dans le fil de son assemblee.

## Les octets ne sont pas ici

`media_url` pointe vers le `MediaStore` — le magasin **durable**, celui des
annonces, jamais celui des fragments qui purge a sept jours. Une piece de
quarante-cinq minutes pese quatre-vingt-six megaoctets ; la base garde son nom,
pas son son.

Revision ID: a4d71c9e5b30
Revises: e8c15a72f0b4
Create Date: 2026-09-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a4d71c9e5b30'
down_revision: Union[str, Sequence[str], None] = 'e8c15a72f0b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "urim_piece",
        # Produit par l'appareil : republier ne duplique pas.
        sa.Column("id", sa.Uuid(), primary_key=True),
        # Le culte d'origine. Sans cle etrangere — voir l'en-tete.
        sa.Column("capture_id", sa.Uuid(), nullable=False),
        sa.Column("church_id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        # Le nom que le pasteur a ecrit. Jamais vide : deux pieces anonymes d'un
        # meme dimanche ne se distinguent pas, et c'est la mauvaise qu'il
        # publierait.
        sa.Column("title", sa.String(), nullable=False),
        # Les bornes dans le culte d'origine. Elles ne servent plus a retailler —
        # la matiere aura disparu — mais elles disent d'ou vient ce qu'on ecoute.
        sa.Column("start_ms", sa.Integer(), nullable=False),
        sa.Column("end_ms", sa.Integer(), nullable=False),
        sa.Column("media_url", sa.String(), nullable=False),
        # Deux dates, deux faits : il coupe le lundi et publie le vendredi.
        sa.Column("cut_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("end_ms > start_ms", name="piece_bornes_ordonnees"),
        sa.CheckConstraint("length(title) > 0", name="piece_titre_non_vide"),
    )
    # Le fil d'une assemblee : ce qu'elle a recu, du plus recent au plus ancien.
    op.create_index("ix_urim_piece_assemblee", "urim_piece", ["church_id", "published_at"])
    # Les pieces d'un meme dimanche, pour les montrer ensemble.
    op.create_index("ix_urim_piece_culte", "urim_piece", ["capture_id"])


def downgrade() -> None:
    # ⚠️ Ce qui part ici, ce sont **les predications publiees** — et depuis D71
    # leur matiere d'origine n'est jamais montee : rien, nulle part, ne permet de
    # les reconstituer. Les octets survivent dans le `MediaStore`, orphelins de
    # tout ce qui disait a qui ils appartiennent.
    op.drop_index("ix_urim_piece_culte", table_name="urim_piece")
    op.drop_index("ix_urim_piece_assemblee", table_name="urim_piece")
    op.drop_table("urim_piece")
