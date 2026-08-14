"""Le sens d'un mot d'origine — **acquis, traduit, et vérifiable**

`urim_corpus_lemma.gloss` existait, vide. La remplir demande trois colonnes de plus, et
chacune est une condition de la décision L1 : *traduire une source publiée n'est pas inventer
une définition — à condition qu'on puisse le vérifier.*

| Colonne | Pourquoi elle est **obligatoire** et non confortable |
| :-- | :-- |
| `gloss_source` | **L'entrée d'origine, mot pour mot.** Une glose française contestée se vérifie contre sa source en un coup d'œil. Sans elle, la traduction devient à son tour une source — exactement ce que la règle refuse |
| `gloss_source_ref` | D'où elle vient (`TBESG`, CC BY 4.0). La licence l'exige, et le pasteur a le droit de savoir qui définit le mot qu'il va prêcher |
| `gloss_model` | **Qui a traduit.** L'équivalent de `corpus_snapshot` : `mistral-small-latest` est un alias mouvant, et une glose d'aujourd'hui n'a pas été écrite par le modèle d'hier |

⚠️ **Aucune contrainte n'oblige `gloss` à être non nulle, et c'est voulu** : un lemme sans
entrée dans le lexique reste sans glose. *Rien plutôt qu'une vraisemblance* — c'est la règle du
dépôt, et elle vaut ici plus qu'ailleurs : personne ne relit une définition grecque avant de la
redire en chaire.

Revision ID: c7d8e9f0a1b2
Revises: b6c7d8e9f0a1
"""

from alembic import op
import sqlalchemy as sa

revision = "c7d8e9f0a1b2"
down_revision = "b6c7d8e9f0a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("urim_corpus_lemma", sa.Column("gloss_source", sa.Text(), nullable=True))
    op.add_column(
        "urim_corpus_lemma", sa.Column("gloss_source_ref", sa.String(64), nullable=True)
    )
    op.add_column("urim_corpus_lemma", sa.Column("gloss_model", sa.String(), nullable=True))


def downgrade() -> None:
    for colonne in ("gloss_model", "gloss_source_ref", "gloss_source"):
        op.drop_column("urim_corpus_lemma", colonne)
