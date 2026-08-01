"""Déposer un sujet de reconnaissance — **le seul geste du membre qui parle de lui en bien**.

Tout le reste de ce que le moteur écoute décrit une situation : une absence, une inquiétude, une
demande. Il manquait la parole inverse, et son absence coûtait cher — un cas restait à sa priorité
d'origine alors que la personne venait de donner de ses nouvelles, et le responsable ouvrait son
appel par « je vois que tu n'es pas venue » à quelqu'un qui allait bien.

**Où le texte va, et où il ne va pas.** Il entre au journal, dans le payload du fait. Il ne
ressort ni sur l'écran du responsable — l'annotation dit qu'un sujet a été déposé et quand, jamais
ce qu'il contient — ni nulle part ailleurs : il n'existe aucun mur, aucun fil, aucun compteur de
reconnaissances. Une reconnaissance est adressée à Dieu, pas à une audience.

Ce dernier point n'est pas une pudeur, c'est l'invariant anti-compteur d'engagement : un mur de
reconnaissances serait une production rafraîchissable dont le destinataire est son propre auteur —
exactement la boucle d'habitude que le produit refuse de fabriquer.

**Best-effort, jamais bloquant.** Si le moteur n'est pas monté, le dépôt réussit quand même : ce
que la personne a voulu dire ne dépend pas de l'état d'un greffon.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from app.contexts.watch.application.intake import Intake, warn_if_disconnected
from app.contexts.watch.domain.facts import Fact, FactKind, SubjectKind
from app.contexts.watch.domain.registry import COMPANION

# Ce qu'on accepte de garder. Au-delà, ce n'est plus un sujet de reconnaissance, c'est un journal
# intime — et le produit n'a aucune raison d'en être le dépositaire.
MAX_LENGTH = 500


class DepositGratitude:
    """Le membre, pour lui-même. Le service ne prend **aucun identifiant de sujet**.

    Même règle que l'anniversaire, et pour la même raison : un responsable qui pourrait déposer
    « elle va bien » à la place de quelqu'un ferait taire un cas avec sa propre impression."""

    def __init__(self, intake: Intake | None, *, clock, id_factory=uuid4) -> None:
        warn_if_disconnected("companion", intake)
        self._intake = intake
        self._clock = clock
        self._new_id = id_factory

    async def execute(
        self, *, actor_account_id: UUID, tenant_id: UUID, subject: str
    ) -> bool:
        """Renvoie True si le moteur a retenu le signe de vie. False n'est pas un échec du geste."""
        if self._intake is None:
            return False
        now: datetime = self._clock()
        result = await self._intake.submit(
            Fact(
                # Identité neuve à chaque dépôt : rendre grâce deux fois est deux gestes, et le
                # second est un signe de vie aussi valable que le premier.
                fact_id=self._new_id(),
                tenant_id=tenant_id,
                occurred_at=now,
                recorded_at=now,
                source=COMPANION,
                kind=FactKind.GRATITUDE_DEPOSITED,
                subject_kind=SubjectKind.PERSON,
                subject_id=actor_account_id,
                payload={"subject": subject.strip()[:MAX_LENGTH]},
            )
        )
        return result.accepted
