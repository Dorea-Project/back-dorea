"""mission : la personne existe dès l'acceptation, pas à l'intégration

> *La capsule va partout. La veille s'engage là où un référent existe.*

Le chercheur vivait dans sa propre table et ne devenait une personne qu'à l'intégration. Trois
conséquences, toutes bloquantes :

- **pas de référent** — la cascade ne travaille que sur des personnes, donc l'inviteur ne
  devenait le référent qu'après l'intégration : au moment exact où l'invité en avait le moins
  besoin ;
- **hors du dénominateur de couverture** — l'indicateur le plus vendable du produit ignorait
  précisément les plus fragiles ;
- **passage à membre = migration**, donc perte de l'histoire de celui dont l'histoire compte le
  plus : quelqu'un l'a amené.

Désormais, dès qu'un contact existe, c'est une **personne en base avec un statut**. Le statut
change (`INVITED → VISITOR → SYMPATHIZER → CONFIRMED_MEMBER`) ; l'identité, jamais.

`seekers.person_account_id` relie la capsule à cette personne. `integrated_account_id` reste pour
les lignes déjà écrites — mais ces deux colonnes ne disent pas la même chose : l'une dit *qui
c'est*, l'autre disait *quand elle a fini par compter*.

Aucune reprise de données : la table est vide, et elle ne le sera plus jamais autant.

Revision ID: e1fb0c1d2e3f
Revises: d0fb0c1d2e3f
Create Date: 2026-07-27 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1fb0c1d2e3f'
down_revision: Union[str, Sequence[str], None] = 'd0fb0c1d2e3f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("seekers", sa.Column("person_account_id", sa.Uuid(), nullable=True))
    op.create_index("ix_seekers_person", "seekers", ["person_account_id"])
    # Les lignes existantes : celle qui a été intégrée EST la personne. Sur une base vide c'est
    # un no-op ; sur une base pilote, ça évite de perdre le lien déjà établi.
    op.execute(
        "UPDATE seekers SET person_account_id = integrated_account_id "
        "WHERE integrated_account_id IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_index("ix_seekers_person", table_name="seekers")
    op.drop_column("seekers", "person_account_id")
