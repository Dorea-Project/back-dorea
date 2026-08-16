"""le culte n'a plus de titre français : « Culte » était son type, pas son nom (L-6 du bilingue)

Le compagnon de sermon ouvre la rencontre du culte au premier déclarant, et il y écrivait
`title = 'Culte'`. Ce n'était pas un nom donné par quelqu'un : c'était le mot français pour le
type `service`, gravé en base au moment de l'écriture. Une église anglophone lisait donc
« Culte » dans son historique de présence, et **aucun rendu ne pouvait le rattraper** — la ligne
existait déjà. C'était la seule voix de Dorea qui n'était pas rendue à l'envoi.

`title` redevient ce qu'il est : le nom qu'un humain donne lui-même à sa rencontre (« Culte de
Pâques », « Cellule Bethel »). Les rencontres qui n'ont d'autre nom que leur type portent `NULL`,
et le client les nomme dans la langue de son lecteur — même règle que les erreurs de l'API.

**Ce que le UPDATE vise, et pourquoi il ne peut pas déborder.** Les trois conditions ensemble
décrivent exactement la ligne écrite par le compagnon : église-entière (`group_id IS NULL`), de
type `service`, intitulée `Culte`. Un responsable qui aurait nommé « Culte » une rencontre de
**groupe** n'est pas touché. Reste le cas d'un humain ayant créé une rencontre église-entière de
type service et l'ayant nommée « Culte » : elle est remise à `NULL` et s'affichera « Culte » en
français, « Service » en anglais — c'est-à-dire ce qu'il voulait dire.

Revision ID: c4e9a72b18f3
Revises: b3d8f21a6c47
Create Date: 2026-08-16 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c4e9a72b18f3'
down_revision: Union[str, Sequence[str], None] = 'b3d8f21a6c47'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "UPDATE gatherings SET title = NULL "
        "WHERE title = 'Culte' AND group_id IS NULL AND type = 'service'"
    )


def downgrade() -> None:
    # On rend le titre aux seules lignes qui l'auraient reçu du compagnon. Redescendre remet le
    # français partout, ce qui est précisément le défaut corrigé — mais la migration doit savoir
    # se défaire, et aucune ligne n'est perdue.
    op.execute(
        "UPDATE gatherings SET title = 'Culte' "
        "WHERE title IS NULL AND group_id IS NULL AND type = 'service'"
    )
