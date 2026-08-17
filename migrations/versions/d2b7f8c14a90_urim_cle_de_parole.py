"""urim : une parole ne se rejoue pas deux fois

Decider et ecarter posent un etat : les renvoyer donne le meme resultat, et un
client sans reseau peut donc les mettre en file sans precaution. Une **parole**,
non. Le serveur y repond — repondeur, et parfois modele — et la renvoyer
coûterait un second passage, un second appel, et peut-etre une autre phrase.

D'ou cette colonne : la derniere cle d'idempotence vue sur cette preparation.
Une parole qui arrive avec la meme cle ne rejoue rien ; le serveur rend l'etat
courant, ce qui est exactement ce que le client attendait.

⚠️ **Ce qu'une seule colonne protege, et ce qu'elle ne protege pas.** Elle
suffit parce que le client vide sa file **dans l'ordre** et **s'arrete au
premier echec** : la seule parole qu'il puisse renvoyer est donc la derniere.
Elle ne protegerait pas deux appareils agissant en meme temps sur la meme
preparation — cas rare, et dont la consequence est un appel de modele en trop,
pas un etat faux. Une table de cles serait plus robuste ; elle demanderait une
politique de purge pour un risque que le protocole du client ecarte deja.

Revision ID: d2b7f8c14a90
Revises: 79652dada125
Create Date: 2026-08-17 21:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd2b7f8c14a90'
down_revision: Union[str, Sequence[str], None] = '79652dada125'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "urim_preparation",
        sa.Column("last_turn_key", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("urim_preparation", "last_turn_key")
