"""Les trois chaînes qui partaient de l'examen — une révision qui ne migre rien

Trois worktrees ont travaillé le même jour, sur la même base de développement partagée, et
toutes trois ont chaîné leur migration sur `d2e3f4a5b6c7` — la table d'examen, la dernière
révision que `main` portait quand elles sont parties :

    c7d8e9f0a1b2   le livrable — l'archive du prédicateur et ses suivantes
    e4f5a6b7c8d9   les collisions entre traductions
    e6f708192a3b   le relecteur et sa file

Trois têtes, donc, et `alembic upgrade head` refusait de choisir. ⚠️ **Ce n'est pas un défaut
de leur travail** : chacune était juste, chacune ignorait les deux autres. C'est la
contrepartie du parallélisme, et elle se paie ici, une fois.

Cette révision ne fait **rien** — elle ne crée ni colonne ni table. Elle dit seulement que les
trois branches se rejoignent et que la suite chaînera sur un seul point.
"""

revision = "88cf00a17967"
down_revision = ("c7d8e9f0a1b2", "e4f5a6b7c8d9", "e6f708192a3b")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Rien à faire : les trois chaînes ont déjà tout créé, chacune de son côté."""


def downgrade() -> None:
    """Redescendre rouvrirait les trois têtes — c'est exactement ce qu'on vient de fermer."""
