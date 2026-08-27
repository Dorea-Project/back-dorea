"""urim : le fil ne disparait plus, et ce qu'on y ecrit peut devenir un point

🔴 **Deux defauts, une table.**

Le premier, vu sur telephone le 22/08 : on quitte l'ecran, on revient, **la
conversation a disparu**. Le client n'y est pour rien — il affiche tout ce qu'il
a. C'est le serveur qui ne gardait rien : *« ce que le pasteur a ecrit en
ouvrant est la seule chose qu'il ait dite que le serveur garde vraiment »*. Le
reste vivait en memoire, et mourait avec l'ecran.

Le second est une demande du fondateur : ce qu'il ecrit dans le fil doit pouvoir
**preparer le document**. Or un element de plan ne pouvait naitre que d'un
endroit — l'ecran « Mes points ». Le fil ne produisait rien qui atteigne le
`.docx`.

## Pourquoi une seule table pour les deux

Parce que c'est le meme objet. Une note attachee a un point n'est rien d'autre
qu'une phrase du fil qui porte une adresse : `element_code` + `element_ordinal`.

    speaker='pasteur', element_code=null        une parole du fil
    speaker='pasteur', element_code='divisions' une note posee sous le point 2
    speaker='urim'                              ce que l'atelier a repondu

## Ce que cette table ne fait pas

⚠️ **Elle ne decide jamais qu'une phrase est un point.** Le fondateur l'a dit
mieux que moi : *« ça peut etre point ou pas, il peut mettre une pause et
revenir changer »*. Si lui ne sait pas encore, la machine ne peut pas savoir.
On garde donc, on attache, et **un geste explicite** promeut — `promoted_at`
dit quand, et empeche de promouvoir deux fois.

Tant que la promotion n'a pas eu lieu, la phrase n'atteint aucun document : le
livrable n'imprime que `urim_preparation_element`. Le verrou tient.

⚠️ **Le modele ne lit jamais ces lignes.** Elles sont les hesitations d'un
homme ; les lui donner en ferait une matiere. Ce qui remonte au modele est ce
qui remonte deja : la saisie du tour, et rien d'autre.

Revision ID: f4d9b0e36c12
Revises: e3c8a9d25b01
Create Date: 2026-08-23 22:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f4d9b0e36c12'
down_revision: Union[str, Sequence[str], None] = 'e3c8a9d25b01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "urim_thread_entry",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("preparation_id", sa.Uuid(), nullable=False, index=True),
        # Qui parle. Deux valeurs, fermees en base : un troisieme locuteur
        # devrait etre decide, pas ecrit par accident.
        sa.Column("speaker", sa.String(length=16), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        # Ou le pasteur l'a posee. Nul = une parole du fil, sans adresse.
        sa.Column("element_code", sa.String(length=64), nullable=True),
        sa.Column("element_ordinal", sa.Integer(), nullable=True),
        # Quand elle est devenue un point de son plan. Nul = elle attend.
        sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("written_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "speaker in ('pasteur','urim')", name="ck_urim_thread_entry_speaker"
        ),
        sa.CheckConstraint(
            "length(btrim(body)) > 0", name="ck_urim_thread_entry_body"
        ),
    )
    # Le fil se lit **dans l'ordre**, toujours, et jamais autrement.
    op.create_index(
        "ix_urim_thread_entry_fil",
        "urim_thread_entry",
        ["preparation_id", "written_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_urim_thread_entry_fil", table_name="urim_thread_entry")
    op.drop_table("urim_thread_entry")
