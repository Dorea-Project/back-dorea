"""ce que le responsable s'engage à faire — le seul champ de texte libre de la veille

**Pourquoi il n'y en avait aucun jusqu'ici.** `RaiseConcern` le dit noir sur blanc : *« ce service
n'accepte aucun texte libre : il n'y a pas de champ où l'écrire »*. C'était la protection contre le
diagnostic — « je la sens fragile », conservé, devient une fiche.

**Pourquoi celui-ci ne rouvre pas cette porte.** Il ne porte pas sur la personne, il porte sur le
geste de celui qui écrit : *« je la rappelle jeudi »*, *« je passe déposer le colis »*. Et ce n'est
pas une consigne de rédaction, c'est le **typage** qui le tient :

- la colonne vit sur `watch_contact_attempts` — une tentative de contact, donc un acte déjà daté et
  attribué à `by_account_id`. Il n'existe toujours **aucune** colonne où écrire quelque chose *sur*
  un membre : ni sur `watch_signals`, ni sur une personne ;
- elle s'écrit à la résolution de la tentative, en même temps que l'issue, et une seule fois —
  `ContactAttempt.resolve` refuse la réécriture ;
- elle n'est pas listable par le membre : elle décrit l'engagement du responsable, et le membre
  garde son arrêt d'urgence inconditionnel (`DO_NOT_CONTACT`), qui n'exige de connaître aucun
  dossier.

Un invariant balaie les modèles du contexte pour que ça reste vrai.

Revision ID: f8fc0c1d2e3f
Revises: e7fc0c1d2e3f
Create Date: 2026-07-30 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f8fc0c1d2e3f'
down_revision: Union[str, Sequence[str], None] = 'e7fc0c1d2e3f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "watch_contact_attempts",
        sa.Column("commitment", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("watch_contact_attempts", "commitment")
