"""La Présence comme **source** du moteur de veille — elle émet, elle ne décide pas.

Une présence réellement enregistrée produit un `PRESENCE_RECORDED`. Ce qu'il advient — fermer une
neutralisation, dater un retour, garder la mémoire du lien — est l'affaire de l'engine.

**Ce qui compte comme retour se décide par le type de fait, pas par une règle.** Seules les deux
voix de la présence émettent ce fait : le pointage du responsable et l'auto-pointage du membre.
Réagir à une annonce n'en émet pas — c'est un signe de vie, pas un retour, et le fil d'actualité
n'est pas une source de présence. L'asymétrie est dans le câblage, pas dans une condition qu'on
pourrait oublier d'écrire.

**Daté de la rencontre, pas de la saisie.** Un responsable qui saisit le dimanche mercredi date
le retour de dimanche — sinon l'histoire du membre décale à chaque saisie différée.
"""

from __future__ import annotations

from datetime import datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from app.contexts.watch.application.intake import Intake
from app.contexts.watch.domain.facts import Fact, FactKind, SubjectKind
from app.contexts.watch.domain.registry import ATTENDANCE

_FACT_NAMESPACE = uuid5(NAMESPACE_URL, "dorea:watch:presence_recorded")


def fact_id_for(gathering_id: UUID, account_id: UUID) -> UUID:
    """Identité **dérivée** : repointer la même personne à la même rencontre ne rejoue rien."""
    return uuid5(_FACT_NAMESPACE, f"{gathering_id}:{account_id}")


class DetectReturn:
    """Signale au moteur qu'une personne était là. Best-effort : jamais bloquant pour M6."""

    def __init__(self, intake: Intake | None) -> None:
        self._intake = intake

    async def on_positive_presence(
        self,
        *,
        account_id: UUID,
        tenant_id: UUID,
        occurred_at: datetime,
        gathering_id: UUID,
        recorded_at: datetime,
    ) -> None:
        if self._intake is None:
            return
        await self._intake.submit(
            Fact(
                fact_id=fact_id_for(gathering_id, account_id),
                tenant_id=tenant_id,
                occurred_at=occurred_at,  # la date de la rencontre
                recorded_at=recorded_at,  # celle de la saisie
                source=ATTENDANCE,
                kind=FactKind.PRESENCE_RECORDED,
                subject_kind=SubjectKind.PERSON,
                subject_id=account_id,
                payload={"gathering_id": str(gathering_id)},
            )
        )
