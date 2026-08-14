"""L'archive du prédicateur — l'antichambre y entre, et l'unité s'y retient

`urim_preached` existait, était **lue par l'étage du thème** (« vous avez déjà prêché cet axe
récemment ») et **écrite par personne**. La phrase n'a donc jamais atteint quiconque. Deux
corrections avant d'ouvrir la première route d'écriture :

1. **`church_id` devient nullable.** `urim_preparation.church_id` l'est depuis le 11/08 —
   Urim est l'antichambre, et le pasteur sans église est le cas normal. `preached` ne l'avait
   pas suivi : on pouvait préparer sans église et **pas archiver**, ce qui refermait la porte
   exactement sur le premier utilisateur de l'application.

2. **`pericope_id` est ajoutée** (colonne nue, jamais de FK vers `urim_corpus` — §3.9). Le
   rangement par loci se lit depuis l'**unité**, qui porte les pesées ; sans elle il faudrait
   re-résoudre le passage à chaque affichage, et une curation qui bouge ferait changer un
   rangement passé sans que rien ne le dise.

Rien à migrer : la table est vide depuis toujours.

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
"""

from alembic import op
import sqlalchemy as sa

revision = "e3f4a5b6c7d8"
down_revision = "d2e3f4a5b6c7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("urim_preached", "church_id", existing_type=sa.Uuid(), nullable=True)
    op.add_column("urim_preached", sa.Column("pericope_id", sa.Uuid(), nullable=True))


def downgrade() -> None:
    op.drop_column("urim_preached", "pericope_id")
    # Comme pour la préparation : redescendre exige qu'aucune archive personnelle n'existe.
    # La contrainte échouera d'elle-même s'il en reste — on n'invente pas une église à
    # quelqu'un pour faire passer un `downgrade`.
    op.alter_column("urim_preached", "church_id", existing_type=sa.Uuid(), nullable=False)
