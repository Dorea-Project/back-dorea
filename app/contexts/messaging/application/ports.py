"""Ports de la messagerie — ce qui entre, et ce qui sort.

`MessageChannel` est le port **sortant** : un transport sait envoyer, et rien
d'autre. Il ne connaît ni le motif, ni le destinataire en tant que personne, ni
la fenêtre de service — ces règles vivent au-dessus de lui.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.contexts.messaging.domain.enums import Channel, DeliveryOutcome, TemplateCategory


@dataclass(frozen=True)
class TemplateRef:
    """Un modèle approuvé chez l'opérateur, et ce qu'on y injecte.

    Le nom et la langue ne sont pas des constantes du code : un modèle se fait
    approuver, se refuse, se renomme. Ils viennent de la configuration.
    """

    name: str
    language: str
    category: TemplateCategory
    placeholders: tuple[str, ...] = ()

    #: Paramètres des **boutons** du modèle, dans l'ordre.
    #:
    #: Les modèles d'authentification de WhatsApp portent presque toujours un
    #: bouton « Copier le code », dont l'URL contient une variable. Elle se
    #: renseigne à part du corps, et l'oublier fait refuser l'envoi — le code
    #: apparaîtrait dans le texte mais le bouton serait vide.
    button_placeholders: tuple[str, ...] = ()


@dataclass(frozen=True)
class OutboundMessage:
    """Une intention d'envoi, indépendante du transport qui la portera.

    Elle porte **les deux formes** du même message : le modèle, pour WhatsApp
    qui l'exige hors fenêtre de 24 h, et le texte, pour le SMS qui ne connaît
    pas les modèles. Ainsi un repli d'un canal à l'autre ne demande pas de
    reconstruire le message — donc pas de risque qu'il dise autre chose.
    """

    #: Numéro au format E.164 **sans le `+`** : c'est ce qu'attend Infobip.
    to: str

    template: TemplateRef

    #: Ce que dit le message pour un canal sans modèles.
    text: str

    #: Notre identifiant, transmis au fournisseur. Il rend l'envoi idempotent et
    #: permet de rapprocher un accusé de réception de son message.
    message_id: str

    #: Ne sert qu'aux journaux : jamais le numéro, jamais le contenu.
    purpose: str = "unspecified"

    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderReceipt:
    """Ce que le fournisseur a répondu, réduit à ce dont on a besoin."""

    channel: Channel
    outcome: DeliveryOutcome

    #: Identifiant côté fournisseur, à rapprocher des accusés de réception.
    provider_message_id: str | None = None

    #: Statut brut, conservé pour le diagnostic (jamais interprété ailleurs).
    provider_status: str | None = None


class MessageChannel(ABC):
    """Un transport."""

    @property
    @abstractmethod
    def channel(self) -> Channel: ...

    @abstractmethod
    async def send(self, message: OutboundMessage) -> ProviderReceipt:
        """Envoie, ou lève.

        `ChannelUnavailableError` si le transport a flanché — l'appelant peut
        réessayer ou se replier ; `MessageRejectedError` si le message lui-même
        a été refusé — réessayer ne servira à rien.
        """
