"""le rodage : une église observe avant de parler

**Le problème.** Une église qui installe Dorea n'a jamais vu ses propres seuils. Lui envoyer des cas
dès le premier jour, c'est lui demander de faire confiance à des nombres que personne n'a mesurés
chez elle — et le premier faux positif coûte plus cher que les dix vrais qui suivront.

`SHADOW` n'éteint rien : le pipeline tourne entier, tout est détecté, journalisé et écrit. Seule la
**sortie** est retenue, et le pasteur reçoit « voici ce que Dorea aurait signalé ». C'est la
différence entre « ça ne marche pas encore » et « ça observe ».

**Deux colonnes, pas un état de plus.** « Détecté mais non émis » est déjà un concept du moteur
(`HELD`) : on ajoute une *raison* de rétention, et la machine à états ne bouge pas. `held_reason`
distingue « retenu par le plafond du responsable » — que la passe nocturne relâche — de « retenu
parce que l'église est en rodage », qu'elle ne doit jamais toucher. Les confondre ferait parler
toute seule, pendant la nuit, une église qui observait.

**L'absence de ligne vaut `SHADOW`.** Le rodage est le défaut sans dépendre d'un provisionnement ni
d'un backfill : aucune église existante ou future ne peut se mettre à parler par oubli.

Revision ID: a9fc0c1d2e3f
Revises: f8fc0c1d2e3f
Create Date: 2026-07-31 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a9fc0c1d2e3f'
down_revision: Union[str, Sequence[str], None] = 'f8fc0c1d2e3f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("watch_signals", sa.Column("held_reason", sa.String(), nullable=True))
    op.create_table(
        "watch_tenant_regimes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("regime", sa.String(), nullable=False),
        sa.Column("since", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed_by_account_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id"),
    )


def downgrade() -> None:
    op.drop_table("watch_tenant_regimes")
    op.drop_column("watch_signals", "held_reason")
