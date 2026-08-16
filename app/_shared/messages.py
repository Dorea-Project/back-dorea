"""Le catalogue — **tout** ce que Dorea dit de sa propre voix, dans les deux langues.

C'est le pendant de la frontière du §0 du chantier bilingue : ce fichier ne contient que des
phrases dont Dorea est l'auteur. Le titre d'une annonce, le nom d'un chercheur, le mot du
pasteur qui décline un rendez-vous n'y entrent jamais — ils **passent en paramètres** et
ressortent tels quels.

D'où la règle qui gouverne la table : *aucune phrase de Dorea ne vit hors d'ici*. Un point
d'appel qui écrit `f"« {event.title} » a été annulé."` a beau n'avoir que quatre mots à lui,
ces quatre mots sont introuvables le jour où l'on ajoute une langue. Même la ponctuation qui
sépare un titre d'un lieu (« — ») est de Dorea : c'est pourquoi `EVENT_TOMORROW` et
`EVENT_TOMORROW_AT` sont deux entrées et non une entrée plus un bout de f-string.

**Rendu tardif.** Rien ici n'est appelé au moment où un contexte décide de prévenir quelqu'un.
Un `PushNotification` porte une clé et des paramètres ; le texte naît au dispatch, quand on sait
enfin **qui** lit. C'est ce qui permet à deux membres de la même église de recevoir la même
notification chacun dans sa langue — et à un rappel de rendez-vous planifié trois semaines à
l'avance de ne pas se figer dans la langue du jour où il a été posé.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from app._shared.domain.locale import DEFAULT_LOCALE, Locale


class MessageKey(StrEnum):
    """L'identité d'une chose que Dorea dit. **Les valeurs vont en base** (`scheduled_
    notifications.message_key`) : on peut en ajouter, jamais les renommer après coup — un
    rappel déjà planifié porte l'ancienne."""

    ANNOUNCEMENT_TARGETED = "announcement.targeted"
    ANNOUNCEMENT_BROADCAST = "announcement.broadcast"
    ANNOUNCEMENT_CONSENT = "announcement.consent"

    APPOINTMENT_CONFIRMED = "appointment.confirmed"
    APPOINTMENT_REMINDER = "appointment.reminder"
    APPOINTMENT_DECLINED = "appointment.declined"
    APPOINTMENT_DECLINED_WITH_NOTE = "appointment.declined_with_note"
    APPOINTMENT_RELAY = "appointment.relay"
    APPOINTMENT_RECALL = "appointment.recall"

    EVENT_PUBLISHED = "event.published"
    EVENT_TOMORROW = "event.tomorrow"
    EVENT_TOMORROW_AT = "event.tomorrow_at"
    EVENT_PARTICIPANT_CONFIRMED = "event.participant_confirmed"
    EVENT_CANCELLED = "event.cancelled"
    EVENT_REMOVED = "event.removed"

    MISSION_CARD_ACCEPTED = "mission.card_accepted"

    WATCH_CONTACT_RETURN = "watch.contact_return"
    WATCH_SHADOW_DIGEST = "watch.shadow_digest"

    SERMON_FALLBACK_QUESTION = "sermon.fallback_question"


@dataclass(frozen=True, slots=True)
class Message:
    """Un couple titre/corps — rendu, prêt à partir vers un appareil."""

    title: str
    body: str


#: Le catalogue. Chaque clé porte **toutes** les langues : une entrée incomplète est une
#: notification muette pour la moitié des lecteurs, et le test de structure la refuse.
CATALOG: dict[MessageKey, dict[Locale, Message]] = {
    # --- Annonces ---------------------------------------------------------------------
    # Le titre est celui de l'annonce : humain, jamais traduit. Il traverse le gabarit.
    MessageKey.ANNOUNCEMENT_TARGETED: {
        Locale.FR: Message("{announcement}", "Une annonce vous concerne."),
        Locale.EN: Message("{announcement}", "An announcement concerns you."),
    },
    MessageKey.ANNOUNCEMENT_BROADCAST: {
        Locale.FR: Message("Nouvelle annonce", "{announcement}"),
        Locale.EN: Message("New announcement", "{announcement}"),
    },
    MessageKey.ANNOUNCEMENT_CONSENT: {
        Locale.FR: Message("Une annonce vous concerne", "Acceptez-vous qu'elle soit publiée ?"),
        Locale.EN: Message("An announcement concerns you", "Do you agree to it being published?"),
    },
    # --- Rendez-vous ------------------------------------------------------------------
    MessageKey.APPOINTMENT_CONFIRMED: {
        Locale.FR: Message("Rendez-vous confirmé", "Votre rendez-vous a été confirmé."),
        Locale.EN: Message("Appointment confirmed", "Your appointment has been confirmed."),
    },
    MessageKey.APPOINTMENT_REMINDER: {
        Locale.FR: Message("Rappel de rendez-vous", "Votre rendez-vous approche."),
        Locale.EN: Message("Appointment reminder", "Your appointment is coming up."),
    },
    # Deux entrées, parce que deux voix : le pasteur a écrit un mot, ou il n'en a pas écrit.
    # Le sien passe en paramètre et sort intact ; seul le défaut appartient à Dorea.
    MessageKey.APPOINTMENT_DECLINED: {
        Locale.FR: Message("Rendez-vous", "Votre demande n'a pas été retenue."),
        Locale.EN: Message("Appointment", "Your request was not taken up."),
    },
    MessageKey.APPOINTMENT_DECLINED_WITH_NOTE: {
        Locale.FR: Message("Rendez-vous", "{note}"),
        Locale.EN: Message("Appointment", "{note}"),
    },
    MessageKey.APPOINTMENT_RELAY: {
        Locale.FR: Message("Rendez-vous", "C'est un autre pasteur qui te recevra."),
        Locale.EN: Message("Appointment", "Another pastor will see you."),
    },
    MessageKey.APPOINTMENT_RECALL: {
        Locale.FR: Message("Rendez-vous", "Quelqu'un vous rappelle très vite."),
        Locale.EN: Message("Appointment", "Someone will call you back very soon."),
    },
    # --- Événements -------------------------------------------------------------------
    MessageKey.EVENT_PUBLISHED: {
        Locale.FR: Message("Nouvel événement", "« {title} »"),
        Locale.EN: Message("New event", "“{title}”"),
    },
    MessageKey.EVENT_TOMORROW: {
        Locale.FR: Message("C'est demain", "« {title} »."),
        Locale.EN: Message("It's tomorrow", "“{title}”."),
    },
    MessageKey.EVENT_TOMORROW_AT: {
        Locale.FR: Message("C'est demain", "« {title} » — {place}."),
        Locale.EN: Message("It's tomorrow", "“{title}” — {place}."),
    },
    MessageKey.EVENT_PARTICIPANT_CONFIRMED: {
        Locale.FR: Message("Nouvelle présence confirmée", "Quelqu'un sera présent à « {title} »."),
        Locale.EN: Message("New confirmed attendance", "Someone will be at “{title}”."),
    },
    MessageKey.EVENT_CANCELLED: {
        Locale.FR: Message("Événement annulé", "« {title} » a été annulé."),
        Locale.EN: Message("Event cancelled", "“{title}” has been cancelled."),
    },
    MessageKey.EVENT_REMOVED: {
        Locale.FR: Message("Événement retiré", "Votre événement a été retiré par la modération."),
        Locale.EN: Message("Event removed", "Your event was removed by moderation."),
    },
    # --- Mission ----------------------------------------------------------------------
    MessageKey.MISSION_CARD_ACCEPTED: {
        Locale.FR: Message("Une invitation acceptée", "{name} a répondu à ton invitation."),
        Locale.EN: Message("An invitation accepted", "{name} answered your invitation."),
    },
    # --- Veille -----------------------------------------------------------------------
    MessageKey.WATCH_CONTACT_RETURN: {
        Locale.FR: Message("Un retour ?", "As-tu pu joindre {label} ?"),
        Locale.EN: Message("Any news?", "Were you able to reach {label}?"),
    },
    MessageKey.WATCH_SHADOW_DIGEST: {
        Locale.FR: Message(
            "Dorea observe",
            "{count} situation(s) auraient été signalées cette semaine. "
            "Ouvrez le rapport pour les voir.",
        ),
        Locale.EN: Message(
            "Dorea is watching",
            "{count} situation(s) would have been flagged this week. "
            "Open the report to see them.",
        ),
    },
    # --- Sermon -----------------------------------------------------------------------
    # ⚠️ La seule entrée qui ne part pas vers un appareil : c'est la question du compagnon
    # quand le digesteur tourne **sans IA** (repli déterministe). `title` porte la question,
    # `body` le mot qui aide — le couple `prompt`/`guidance` de `CompanionQuestion`.
    #
    # Elle est ici et pas dans le digesteur pour que la règle reste vraie sans exception :
    # *aucune phrase de Dorea ne vit hors du catalogue*. Une phrase rangée ailleurs « parce
    # qu'elle n'est pas une notification » est exactement celle qu'on ne retrouve pas.
    MessageKey.SERMON_FALLBACK_QUESTION: {
        Locale.FR: Message("Qu'est-ce qui t'a le plus parlé dans ce message ?", "{summary}"),
        Locale.EN: Message("What spoke to you most in this message?", "{summary}"),
    },
}


def render(key: MessageKey, locale: Locale, params: Mapping[str, object] | None = None) -> Message:
    """Le texte, dans cette langue, avec le contenu humain glissé dedans.

    ⚠️ Le `.format` s'applique au **gabarit**, pas aux valeurs : un titre d'annonce contenant
    des accolades ressort intact au lieu d'être réinterprété. C'est ce qui rend sûr le passage
    de texte écrit par des gens.

    Une langue absente du catalogue retombe sur `DEFAULT_LOCALE` — le cas ne devrait pas
    exister (le test de structure l'interdit), mais une clé muette vaut mieux qu'une exception
    sur le chemin d'une notification.
    """
    by_locale = CATALOG[key]
    template = by_locale.get(locale) or by_locale[DEFAULT_LOCALE]
    values = dict(params or {})
    return Message(
        title=template.title.format(**values),
        body=template.body.format(**values),
    )
