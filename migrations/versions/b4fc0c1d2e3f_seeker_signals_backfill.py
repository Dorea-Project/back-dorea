"""backfill : les chercheurs en cours deviennent des cas de veille

**Pourquoi.** `SeekerStatus` était une seconde machine à états suivant les mêmes personnes que le
`Signal`. Les commandes écrivent désormais sur le cas, et l'état du chercheur se **lit**. Sans ce
backfill, tout chercheur `accepted` ou `accompanied` d'avant la bascule n'aurait plus de cas
vivant — et se lirait donc « clos ». Il disparaîtrait de la file de son inviteur sans que
personne ne l'ait décidé : exactement le silence que le module existe pour empêcher.

**Ce que le backfill ne peut pas faire.** Un chercheur sans `person_account_id` (créé avant le
seuil de Mission) n'a aucun compte à qui rattacher un cas — un `Signal` porte sur une personne.
Ceux-là sont laissés tels quels et **comptés** : les taire les ferait passer pour traités.

**Le propriétaire.** L'accompagnateur s'il existe, sinon l'inviteur. Pour une capsule de groupe,
l'inviteur est nul et le cas reste sans propriétaire — c'est la vérité, et elle remonte comme un
défaut de couverture au lieu d'être maquillée par un destinataire inventé.

Revision ID: b4fc0c1d2e3f
Revises: a3fc0c1d2e3f
Create Date: 2026-07-27 23:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b4fc0c1d2e3f'
down_revision: Union[str, Sequence[str], None] = 'a3fc0c1d2e3f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# `origin = declared` : accepter une capsule est un geste de la personne elle-même — c'est ce que
# produit déjà `CrossTheThreshold` aujourd'hui, et le rejeu du ledger doit rendre la même chose.
_BACKFILL = sa.text(
    """
    INSERT INTO watch_signals (
        id, tenant_id, subject_id, origin, status, reason, opened_at, expires_at,
        owner_account_id, source_refs, priority, annotations,
        first_seen_at, first_contact_at,
        episode_id, occurrence_number, gestures_count
    )
    SELECT
        gen_random_uuid(), s.tenant_id, s.person_account_id, 'declared',
        CASE
            WHEN s.status = 'accompanied' THEN 'in_contact'
            WHEN COALESCE(s.accompanied_by_account_id, s.inviter_account_id) IS NOT NULL
                THEN 'assigned'
            ELSE 'open'
        END,
        'A répondu à une invitation et laissé son contact.',
        s.created_at, NULL,
        COALESCE(s.accompanied_by_account_id, s.inviter_account_id),
        '[]'::json, 'declared', '[]'::json,
        s.accompanied_at, s.accompanied_at,
        gen_random_uuid(), 1, 0
    FROM seekers s
    WHERE s.person_account_id IS NOT NULL
      AND s.status IN ('accepted', 'accompanied')
      AND NOT EXISTS (
          SELECT 1 FROM watch_signals w
          WHERE w.tenant_id = s.tenant_id
            AND w.subject_id = s.person_account_id
            AND w.status IN ('held', 'open', 'assigned', 'in_contact')
      )
    """
)

# Chaque cas ouvre son propre épisode : aucun de ces chercheurs n'a d'antériorité connue.
_FIX_EPISODE = sa.text("UPDATE watch_signals SET episode_id = id WHERE episode_id <> id")

_ORPHANS = sa.text(
    """
    SELECT count(*) FROM seekers
    WHERE person_account_id IS NULL AND status IN ('accepted', 'accompanied')
    """
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return  # `gen_random_uuid` est du Postgres ; rien à reprendre ailleurs

    result = bind.execute(_BACKFILL)
    bind.execute(_FIX_EPISODE)
    orphans = bind.execute(_ORPHANS).scalar_one()
    print(
        f"[backfill] {result.rowcount} chercheur(s) repris en cas de veille ; "
        f"{orphans} sans compte, laissé(s) hors veille (créé(s) avant le seuil)."
    )


def downgrade() -> None:
    """Irréversible, et c'est assumé.

    Rien ne distingue en base un cas repris par ce backfill d'un cas ouvert normalement depuis.
    Les supprimer par leur motif effacerait aussi les cas légitimes — on préfère laisser des
    lignes en trop plutôt que perdre le suivi de quelqu'un."""
