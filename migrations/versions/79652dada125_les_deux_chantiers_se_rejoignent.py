"""les deux chantiers se rejoignent

Deux branches ont travaille en parallele sur la meme base : le chantier
bilingue — la langue du compte, l'outbox qui porte la cle du message, le culte
qui n'a plus de titre francais — et le fil d'accueil d'Urim.

Elles ne se touchent nulle part. Aucune table commune, aucune colonne commune :
le bilingue s'arrete au verrou D, qui met Urim hors perimetre. Cette revision
n'a donc **rien a faire** — elle existe pour rendre a Alembic une tete unique.

Une base de developpement estampillee `c4e9a72b18f3` ne pouvait plus etre
migree depuis `main`, qui ne connaissait pas cette revision. C'est ce que
resout ce point de rencontre, et c'est la seule raison de son existence.

Revision ID: 79652dada125
Revises: c4e9a72b18f3, c7a1f4e2b903
Create Date: 2026-08-17 02:45:20.544505

"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = '79652dada125'
down_revision: Union[str, Sequence[str], None] = ('c4e9a72b18f3', 'c7a1f4e2b903')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rien : les deux chemins sont disjoints."""


def downgrade() -> None:
    """Rien non plus — separer les deux tetes suffit."""
