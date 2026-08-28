"""urim : le plan qu'Urim propose — a cote du sien, jamais dedans

**D55, seconde moitie.** L'etage 6 tranche desormais la mise en forme et dit
pourquoi ; il restait le plus utile et le plus dangereux : proposer les points.

Le fondateur l'a demande dans ces termes — *« avant de generer le document, il
faut proposer le plan, le titre, avec les versets qui soutiennent chaque point ;
ça peut etre un sujet a discussion, le user aussi peut corriger »*.

## Pourquoi une table, et pas des colonnes sur l'element

C'est la meme raison que `urim_plan_suggestion`, et elle vaut d'etre repetee
parce qu'elle se defait sans bruit : **le livrable n'imprime que
`urim_preparation_element`**. Une proposition rangee dans la meme colonne que le
plan du pasteur ferait imprimer la machine sous son nom, et la regle centrale du
livrable tomberait sans que personne ait ecrit une ligne pour la lever.

Separee, elle n'atteint un fichier que par un geste de reprise — point par
point, `POST /studies/{id}/squelette/reprises`. *L'IA propose, l'homme dispose.*

## Une ligne par preparation

Le squelette est une proposition d'**ensemble** : deux lignes voudraient dire
deux plans concurrents, et l'ecran devrait choisir lequel montrer. Changer de
passage ou de mise en forme **remplace**, ça n'empile pas.

## Ce que `input_hash` empeche

Il porte les quatre choses dont la proposition depend : la reference servie,
l'axe retenu, le couple plan x matiere, l'etat du corpus. Deux effets, et le
second compte plus que le premier :

- un rejeu ne rappelle pas le modele, donc ne refacture pas ;
- **le pasteur ne voit pas ses points changer sous lui** a chaque phrase qu'il
  ecrit dans le fil. Un plan qui bouge a chaque tour n'est pas un plan.

## Ce qui a ete verifie avant d'arriver ici

Les versets de `points` ont ete **relus contre le texte servi** : ce que le
modele a cite ailleurs est retire, pas signale. Un verset invente sur l'ecran
d'un pasteur est fatal, et il est detectable — on a le texte qu'on vient de
servir. Le point, lui, reste : son titre ne depend pas de ses appuis.

Revision ID: b5e1f92a047c
Revises: a1c7d3e50b94
Create Date: 2026-08-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b5e1f92a047c'
down_revision: Union[str, Sequence[str], None] = 'a1c7d3e50b94'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "urim_proposed_skeleton",
        # Une seule ligne par preparation : la cle primaire **est** la regle.
        sa.Column("preparation_id", sa.Uuid(), primary_key=True),
        # Ce dont la proposition depend : reference | axe | plan | matiere | corpus.
        sa.Column("input_hash", sa.String(length=32), nullable=False),
        # Ce que `corpus_snapshot` est a la preparation : de quoi savoir plus tard
        # quelle machine a ecrit ces mots-la.
        sa.Column("model", sa.String(), nullable=False),
        # Propose, jamais pose : « un theme, jamais un titre — le titre, c'est
        # votre voix ». Nul quand le modele n'en a pas rendu.
        sa.Column("title", sa.Text(), nullable=True),
        # [{titre, versets: [...]}] — les versets ont ete relus contre le texte servi.
        sa.Column("points", sa.JSON(), nullable=False),
        sa.Column("suggested_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["preparation_id"], ["urim_preparation.id"], ondelete="CASCADE"
        ),
    )


def downgrade() -> None:
    # Rien a sauver : ce que le pasteur a **repris** vit deja dans
    # `urim_preparation_element`, et c'est la seule chose qui compte.
    op.drop_table("urim_proposed_skeleton")
