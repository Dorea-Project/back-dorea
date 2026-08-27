"""urim : le vestibule — une preparation ne s'ouvre plus toute seule

Trois colonnes pour une seule regle : **rien n'entre en preparation sans un
« oui » explicite**.

Jusqu'ici, ecrire une phrase ET ouvrir une preparation etaient le meme geste :
le `POST /studies` creait la ligne, et le moteur descendait. Un pasteur qui
disait bonjour repartait avec une preparation ouverte sur rien — 150 de ces
lignes viennent d'etre purgees, et elles n'etaient pas une negligence : c'etait
le comportement.

`maturity` porte les quatre ages d'un sujet.

    absent      rien           on converse
    pressenti   un theme       on relance — on ne propose pas
    nomme       un sujet       on propose une preparation
    confirme    un oui         le moteur descend

🔴 **`confirme` ne peut naitre que d'un tour du pasteur.** Le modele ne le rend
jamais — la validation le refuse a la source — et c'est ce qui rend l'ouverture
inatteignable par une saisie qui souffle une intention.

`carried_subject` est la charge **nettoyee de son emballage** : « je voudrais
travailler un peu sur le pardon aujourd'hui » donne « le pardon ». C'est elle
qui descend dans le moteur au consentement, pas la phrase brute — le
deterministe ne sait pas faire cette extraction, et c'est la raison d'etre de
l'appel au modele a cet endroit precis.

`declined_subjects` tient la retenue : **un sujet decline ne revient pas**. Sans
elle, la pente d'un modele est de re-servir le meme sujet trois tours plus loin,
et la conversation devient un harcelement poli.

⚠️ **Les preparations existantes naissent `confirme`.** Elles ont ete ouvertes
sous l'ancien regime, ou ouvrir valait consentement ; les faire retomber en
`absent` redemanderait leur accord sur un travail deja fait, parfois deja
preche. La regle nouvelle vaut pour ce qui vient.

Revision ID: e3c8a9d25b01
Revises: d2b7f8c14a90
Create Date: 2026-08-22 12:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e3c8a9d25b01'
down_revision: Union[str, Sequence[str], None] = 'd2b7f8c14a90'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "urim_preparation",
        sa.Column(
            "maturity",
            sa.String(length=16),
            nullable=False,
            # Le defaut du serveur vaut pour l'existant ; le code, lui, pose
            # toujours la valeur explicitement.
            server_default="confirme",
        ),
    )
    op.add_column(
        "urim_preparation",
        sa.Column("carried_subject", sa.Text(), nullable=True),
    )
    op.add_column(
        "urim_preparation",
        sa.Column(
            "declined_subjects",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
    )

    # ⚠️ **Le defaut change apres coup, et c'est le coeur de la migration.**
    # L'existant est ne `confirme` (voir l'en-tete) ; tout ce qui naitra ensuite
    # part de `absent`, et devra passer par le consentement.
    op.alter_column("urim_preparation", "maturity", server_default="absent")

    # La liste est fermee en base : une valeur inventee par un client ou par un
    # correctif presse ne s'ecrit pas.
    op.create_check_constraint(
        "ck_urim_preparation_maturity",
        "urim_preparation",
        "maturity in ('absent','pressenti','nomme','confirme')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_urim_preparation_maturity", "urim_preparation", type_="check"
    )
    op.drop_column("urim_preparation", "declined_subjects")
    op.drop_column("urim_preparation", "carried_subject")
    op.drop_column("urim_preparation", "maturity")
