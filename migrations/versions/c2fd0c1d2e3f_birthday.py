"""l'anniversaire : une date declaree, affichee au bon moment

> *Dorea rappelle aux humains d'aimer ; il n'aime jamais a leur place.*

Un champ de profil, et rien d'autre : pas de fait au ledger, pas de cas, pas de notification
poussee, pas de message automatique. Un encart qui attend qu'on ouvre l'application.

Quatre decisions dans ces quatre colonnes :

- **jour et mois suffisent.** `birth_year` est optionnelle et n'est **jamais affichee nulle part** :
  l'age de quelqu'un n'est pas une donnee d'eglise. Elle n'existe que si le membre la donne, pour
  d'eventuels usages pastoraux futurs explicitement consentis -- aucun aujourd'hui ;
- **la visibilite est choisie par le membre**, dans une liste fermee. `hidden` eteint tout :
  l'encart, la reponse de l'assistant, la vue du pasteur. Meme mecanique que `DO_NOT_CONTACT` --
  le reglage du membre absorbe, et aucune bonne intention ne le leve ;
- **le defaut est `groups`**, parce que l'anniversaire est un rituel communautaire dans les eglises
  cibles -- mais le champ lui-meme reste optionnel, et ne pas renseigner sa date equivaut a
  `hidden` ;
- **la saisie appartient au membre.** Un responsable ne renseigne pas la date d'un autre.

Revision ID: c2fd0c1d2e3f
Revises: b1fd0c1d2e3f
Create Date: 2026-07-31 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c2fd0c1d2e3f'
down_revision: Union[str, Sequence[str], None] = 'b1fd0c1d2e3f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("accounts", sa.Column("birth_day", sa.Integer(), nullable=True))
    op.add_column("accounts", sa.Column("birth_month", sa.Integer(), nullable=True))
    op.add_column("accounts", sa.Column("birth_year", sa.Integer(), nullable=True))
    op.add_column(
        "accounts",
        sa.Column(
            "birthday_scope", sa.String(), nullable=False, server_default=sa.text("'groups'")
        ),
    )


def downgrade() -> None:
    op.drop_column("accounts", "birthday_scope")
    op.drop_column("accounts", "birth_year")
    op.drop_column("accounts", "birth_month")
    op.drop_column("accounts", "birth_day")
