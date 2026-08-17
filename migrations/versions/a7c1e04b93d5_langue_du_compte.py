"""langue du compte : la personne peut ne pas parler la langue de son église (L-0 du bilingue)

`tenants.language` existait depuis le M0 et n'était lue par personne. On ajoute l'étage manquant :
la langue **de la personne**, nullable — et le `NULL` veut dire *« je suis la langue de mon
église »*, pas « français ». C'est ce qui permet à un anglophone d'exister dans une église
francophone, cas courant à Abidjan.

Aucun `server_default` : contrairement à `tenants.language`, on ne veut surtout pas que les
lignes existantes reçoivent une valeur. Elles doivent rester à `NULL` pour continuer à suivre
leur église — un défaut posé ici figerait des centaines de milliers de comptes en français, y
compris ceux des églises anglophones à venir.

Revision ID: a7c1e04b93d5
Revises: 0be963a24a19
Create Date: 2026-08-16 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7c1e04b93d5'
down_revision: Union[str, Sequence[str], None] = '0be963a24a19'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("accounts", sa.Column("language", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("accounts", "language")
