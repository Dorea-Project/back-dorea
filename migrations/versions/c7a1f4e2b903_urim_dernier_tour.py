"""urim : ou en est chaque preparation, sans rejouer le moteur

Le fil d'accueil doit dire « celle-ci t'attend » sans faire tourner le pipeline
sur chaque ligne. Rejouer est le mode normal de lecture d'UNE preparation ; le
faire pour vingt a l'ouverture de l'application serait ruineux.

D'ou ces trois colonnes : une **projection** du dernier tour, ecrite quand le
moteur s'arrete, jamais recalculee a la lecture. Elles ne sont la source de
rien — la verite reste le rejeu — mais elles suffisent a ranger une liste.

`last_outcome` prend le vocabulaire du moteur (`continue`, `await_decision`,
`refuse`, `degrade`) plutot qu'un etat invente cote client : `await_decision`
**est** « rend la main ».

Trois colonnes, et **aucun index** : voir le commentaire dans `upgrade`.

Revision ID: c7a1f4e2b903
Revises: 0be963a24a19
Create Date: 2026-08-17 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7a1f4e2b903'
down_revision: Union[str, Sequence[str], None] = '0be963a24a19'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "urim_preparation",
        sa.Column("last_stage_code", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "urim_preparation",
        sa.Column("last_outcome", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "urim_preparation",
        sa.Column("last_turn_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Aucun index nouveau, et c'est un revirement : j'en avais cree un sur
    # `(author_id, status, last_turn_at)`. Il ne servait a rien.
    #
    # `ix_urim_prep_auteur` couvre deja `author_id`, et c'est tout ce que la
    # requete du fil peut tirer d'un index : `status <> 'abandonnee'` n'ouvre
    # aucune plage, et le tri porte sur `COALESCE(last_turn_at, opened_at)` —
    # une expression qu'aucun index ordinaire ne sert. Le tri se fait donc en
    # memoire sur les quelques dizaines de lignes d'un seul auteur, ce qui est
    # gratuit. Le second index n'aurait coute que des ecritures.


def downgrade() -> None:
    op.drop_column("urim_preparation", "last_turn_at")
    op.drop_column("urim_preparation", "last_outcome")
    op.drop_column("urim_preparation", "last_stage_code")
