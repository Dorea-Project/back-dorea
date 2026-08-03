"""la couverture d'un événement : une image, un texte, ou trente secondes de vidéo

**Le problème.** Un événement n'avait qu'une liste d'URL indifférenciée (`media_urls`) : rien ne
disait laquelle est le visage de l'événement, ni si c'était une photo ou autre chose. Deux clients
auraient tranché différemment, et la même soirée n'aurait pas eu la même tête sur deux téléphones.

**Trois colonnes, pas un JSON.** La couverture se lit, se filtre et se migre. `cover_kind` NULL
signifie « pas de couverture » — un cas légitime : le client affiche alors le titre.

**Et `text` est un membre à part entière, pas un repli.** `IMAGE` et `VIDEO` supposent qu'on a de
quoi photographier ou filmer ; `TEXT` ne suppose rien. Une phrase sur un aplat de couleur, et
l'événement a un visage — c'est ce qui rend le produit utilisable par celui qui organise un repas
depuis un téléphone à faible connexion.

La limite des trente secondes de vidéo ne vit pas ici : elle est **mesurée** à l'upload, dans
l'en-tête du MP4, parce qu'une durée déclarée par le client n'est pas une limite.

Revision ID: e4fd0c1d2e3f
Revises: d3fd0c1d2e3f
Create Date: 2026-08-02 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e4fd0c1d2e3f'
down_revision: Union[str, Sequence[str], None] = 'd3fd0c1d2e3f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("events", sa.Column("cover_kind", sa.String(), nullable=True))
    op.add_column("events", sa.Column("cover_url", sa.String(), nullable=True))
    op.add_column("events", sa.Column("cover_text", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("events", "cover_text")
    op.drop_column("events", "cover_url")
    op.drop_column("events", "cover_kind")
