"""Le port **`Notifier`** — ce que les autres contextes appellent pour prévenir des personnes.

Transverse : Event, Annonces, RDV importent ce port et reçoivent un adaptateur. La notification est
**best-effort** : elle ne casse jamais l'action qui la déclenche (voir `PushNotifier`).

⚠️ **Ce qui voyage ici n'est pas un texte, c'est une intention.** Une `PushNotification` porte une
clé du catalogue et les morceaux de contenu humain à y glisser. Elle ne sait pas dans quelle
langue elle sera lue, et c'est délibéré : au moment où un contexte décide de prévenir, il ne
connaît pas encore ses destinataires — il en a parfois plusieurs centaines, dont certains lisent
l'anglais. Le texte naît au dispatch, une fois par langue présente parmi eux.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from app._shared.messages import Message, MessageKey


@dataclass(frozen=True)
class PushNotification:
    key: MessageKey | None = None
    #: Le contenu **humain** à glisser dans le gabarit — titre d'événement, nom, mot du pasteur.
    #: Il ressort tel quel : Dorea ne traduit jamais ce qu'un humain a écrit. Les valeurs doivent
    #: rester sérialisables en JSON, l'outbox les écrit en base telles quelles.
    params: Mapping[str, object] = field(default_factory=dict)
    # Charge utile (deep-link : type + id, actions). **Des codes, jamais du texte** — c'est le
    # client qui les traduit, comme pour les erreurs de l'API.
    data: dict | None = None

    #: ⚠️ **Transitoire — la porte de sortie des lignes d'avant le bilingue.** Une notification
    #: déjà planifiée en base porte son texte rendu et aucune clé : elle part telle quelle, dans
    #: la langue du jour où elle a été posée. C'est ce qui rend le déploiement sans perte — un
    #: rappel de rendez-vous déjà en file n'a pas à être deviné depuis sa phrase. Aucun code neuf
    #: ne remplit ce champ ; il disparaît avec les colonnes `title`/`body` de
    #: `scheduled_notifications`, une fois l'outbox drainée (quelques jours : le plus long
    #: différé du produit est le rappel d'événement, à 24 h).
    rendered: Message | None = None

    def __post_init__(self) -> None:
        # `key` est optionnelle *pour la seule* porte de sortie ci-dessus. L'invariant empêche
        # qu'elle le devienne pour de bon : une notification sans clé ni texte est muette, et
        # une notification avec les deux ne dit pas laquelle fait foi.
        if (self.key is None) == (self.rendered is None):
            raise ValueError(
                "une notification porte une clé du catalogue, ou un texte déjà rendu (legacy)"
            )


class Notifier(ABC):
    @abstractmethod
    async def notify(
        self, account_ids: list[UUID], notification: PushNotification
    ) -> None: ...


class NotificationScheduler(ABC):
    """Planifie un envoi **différé** (outbox) : cible déjà résolue + quand. Dispatché plus tard,
    hors du chemin de la requête (rappels de RDV, broadcasts asynchrones)."""

    @abstractmethod
    async def schedule(
        self, account_ids: list[UUID], notification: PushNotification, *, at: datetime
    ) -> None: ...
