"""La liste des sections de plan se ferme — quinze codes, pas dix

`preparation_element.element_code` était un texte libre. Le verrou du livrable s'adosse au code
`divisions` : un client qui envoie `Divisions` ou `Point` **refuserait son document à un pasteur
qui a pourtant écrit son plan**.

Fermer seul aurait déplacé le problème — au lieu d'un verrou contourné par une majuscule, un
plan refusé pour la même majuscule. Le service **canonise donc avant** (`Divisions`, `POINT`,
`sous point`, `Intro` retombent sur leur code), et la base refuse ce qui reste.

**Quinze et non dix.** Braga en nomme dix ; les prédications réelles (`docs/temoins/`) en
portent cinq de plus — objectif, contexte, définitions, NB, témoignage. Fermer aux dix aurait
refusé à trois pasteurs sur trois des sections qu'ils tiennent depuis toujours.

La contrainte est **en base** et pas seulement au service : une garde applicative tombe au
premier second chemin d'écriture — un import, un script de reprise, un correctif de nuit.

Rien à migrer : la table est vide (vérifié le 2026-08-14).

Revision ID: b6c7d8e9f0a1
Revises: a5b6c7d8e9f0
"""

from alembic import op

revision = "b6c7d8e9f0a1"
down_revision = "a5b6c7d8e9f0"
branch_labels = None
depends_on = None

_CODES = (
    "'titre','introduction','proposition','phrase_interrogative','phrase_de_transition',"
    "'divisions','subdivisions','illustrations','application','conclusion',"
    "'objectif','contexte','definitions','nb','temoignage'"
)


def upgrade() -> None:
    op.create_check_constraint(
        "element_code_connu",
        "urim_preparation_element",
        f"element_code IN ({_CODES})",
    )


def downgrade() -> None:
    op.drop_constraint(
        "element_code_connu", "urim_preparation_element", type_="check"
    )
