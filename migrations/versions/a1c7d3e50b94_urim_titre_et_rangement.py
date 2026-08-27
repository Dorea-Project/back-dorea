"""Urim — un titre écrit à la main, et le rangement d'une préparation.

Deux manques que l'application ne pouvait pas combler seule.

**Le titre.** `urim_preparation` n'en portait pas : l'écran affichait `raw_input` tant que rien
n'était résolu, puis l'étiquette de la péricope. Les deux sont justes, et aucun des deux n'est
choisi — un pasteur qui ouvre trois préparations sur Romains les voit se ressembler dans son
historique. La colonne est **nullable et le reste** : elle ne remplace pas la règle d'affichage,
elle passe devant quand elle est renseignée.

**Le rangement.** Une préparation qu'on ne veut plus voir n'avait qu'une sortie : `abandonnee`,
posée par « reformuler » — *« la préparation est abandonnée, pas corrigée »*. Le mot dit un
renoncement, et l'employer pour ranger mêlerait deux intentions dans une seule colonne. D'où un
quatrième état, `rangee` : elle quitte le fil, elle ne quitte pas la base, et rien ne l'efface.

⚠️ **On n'ajoute pas `archivee`, et c'est délibéré.** `urim_preached` est déjà « l'archive du
prédicateur » — le geste qui dit *« j'ai prêché ceci »*. Deux sens sur un même mot dans le même
produit, c'est la confusion garantie le jour où les deux écrans coexistent.

Revision ID: a1c7d3e50b94
Revises: f4d9b0e36c12
Create Date: 2026-08-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "a1c7d3e50b94"
down_revision: str | None = "f4d9b0e36c12"
branch_labels: str | None = None
depends_on: str | None = None

#: Le nom porté par la contrainte dans `models.py`. Le renommer ici la dédoublerait.
_CHECK = "prep_status"


def upgrade() -> None:
    op.add_column(
        "urim_preparation",
        sa.Column("title", sa.Text(), nullable=True),
    )

    # Une contrainte CHECK ne s'étend pas : on la remplace. L'ordre compte — la nouvelle
    # est posée après la suppression, jamais l'inverse, sinon les deux se contredisent le
    # temps d'une transaction.
    op.drop_constraint(_CHECK, "urim_preparation", type_="check")
    op.create_check_constraint(
        _CHECK,
        "urim_preparation",
        "status IN ('ouverte','close','abandonnee','rangee')",
    )


def downgrade() -> None:
    # Redescendre efface un état que des lignes portent peut-être. On les ramène à
    # `ouverte` plutôt que de laisser la contrainte échouer : une préparation rangée
    # réapparaît dans le fil, ce qui est visible et réparable — une migration qui refuse
    # de descendre ne l'est pas.
    op.execute("UPDATE urim_preparation SET status = 'ouverte' WHERE status = 'rangee'")

    op.drop_constraint(_CHECK, "urim_preparation", type_="check")
    op.create_check_constraint(
        _CHECK,
        "urim_preparation",
        "status IN ('ouverte','close','abandonnee')",
    )

    op.drop_column("urim_preparation", "title")
