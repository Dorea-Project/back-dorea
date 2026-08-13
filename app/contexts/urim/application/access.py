"""La garde d'accès à une préparation — **une seule définition, deux appelants**.

Elle vivait en méthode privée de `UrimStudyService`. L'archive en a besoin mot pour mot :
qui peut relire une préparation peut l'archiver, et peut en tirer un livrable. La recopier
aurait créé une **seconde définition de « mes préparations »**, qui diverge au premier
changement — c'est exactement ce que le dépôt refuse ailleurs (`GET /iam/me` réutilise
`GetMyMemberships` plutôt que de relire les appartenances).

⚠️ **Deux règles, et laquelle s'applique dépend d'une colonne nulle** :

- **avec église** : la garde est le **droit de prêcher dans cette église**, pas la propriété.
  Deux pasteurs d'une même assemblée se relisent — un travail d'église est un objet d'église ;
- **sans église** (l'antichambre) : il n'y a personne à qui demander, et la seule règle qui
  reste est la **propriété**. Un tiers reçoit *« cette préparation n'existe pas »* plutôt
  qu'un refus : sur un objet privé, confirmer l'existence dirait déjà que cette personne
  prépare, sur quoi, et quand.
"""

from __future__ import annotations

from uuid import UUID

from app.contexts.urim.application.ports import PreacherAuthorization, PreparationRecord
from app.contexts.urim.domain.errors import PreparationIntrouvableError


async def ensure_may_prepare(
    access: PreacherAuthorization, actor_account_id: UUID, church_id: UUID | None
) -> None:
    """Préparer n'exige rien hors d'une église ; dans une église, c'est l'église qui dit."""
    if church_id is None:
        return
    # **Quelle** permission cela recouvre est décidé par l'adaptateur, pas ici. On pose une
    # question de droit ; on n'a pas à connaître le vocabulaire des rôles d'un autre contexte.
    await access.ensure_may_prepare(account_id=actor_account_id, church_id=church_id)


async def ensure_may_read(
    access: PreacherAuthorization, actor_account_id: UUID, record: PreparationRecord
) -> None:
    """Rouvrir une préparation : **son auteur**, ou l'église quand il y en a une."""
    if record.church_id is None:
        if record.author_id != actor_account_id:
            raise PreparationIntrouvableError("Cette préparation n'existe pas.")
        return
    await ensure_may_prepare(access, actor_account_id, record.church_id)
