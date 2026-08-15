"""La citation d'ailleurs rejoint les trois — une seconde révision qui ne migre rien

`88cf00a17967` venait de réunir trois chaînes parties de la table d'examen. Le temps de
l'écrire, une worktree encore active en avait produit une quatrième — `d8e9f0a1b2c3`, la
citation qui vit dans une autre Bible — chaînée elle aussi sur un point antérieur.

⚠️ **Ce n'est pas la même chose que la première fusion, et c'est instructif.** La première
payait un parallélisme *passé* : trois branches parties le même jour du même point. Celle-ci
paie un parallélisme *en cours* — les sessions n'avaient pas fini d'écrire pendant qu'on
fusionnait, et la base de développement partagée pointait déjà cette révision-là.

Elle ne fait rien non plus. Et la leçon qu'elle porte tient en une ligne : **on ne réunit pas
des têtes tant que les branches écrivent encore.**
"""

revision = "647ed6d8ca53"
down_revision = ("88cf00a17967", "d8e9f0a1b2c3")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Rien à faire : les deux chaînes ont déjà tout créé, chacune de son côté."""


def downgrade() -> None:
    """Redescendre rouvrirait les deux têtes — c'est ce qu'on vient de fermer."""
