"""`PushNotifier` — l'implémentation du port `Notifier` par la push.

C'est **ici et nulle part ailleurs** que le texte naît. Trois gestes, dans cet ordre : résoudre la
langue de chaque destinataire, rendre le catalogue **une fois par langue présente**, puis envoyer.
Une église francophone n'appelle donc le catalogue qu'une seule fois, quel que soit le nombre de
membres ; une église mixte, deux.

**Best-effort** : un échec d'envoi (jeton périmé, fournisseur indisponible) est journalisé, jamais
propagé — une notification ne casse pas l'action qui l'a déclenchée. Le rendu lui-même est sous la
même garde : une clé mal paramétrée fait taire *un groupe de langue*, pas la publication.
"""

from __future__ import annotations

from uuid import UUID

from app._shared.domain.locale import DEFAULT_LOCALE, Locale
from app._shared.messages import Message, render
from app.contexts.iam.application.ports import LocaleResolver
from app.contexts.notifications.application.notifier import Notifier, PushNotification
from app.contexts.notifications.application.ports import PushSender
from app.contexts.notifications.domain.repositories import DeviceRepository
from app.core.logging import get_logger

_logger = get_logger("notifications.push")


class PushNotifier(Notifier):
    def __init__(
        self, devices: DeviceRepository, sender: PushSender, locales: LocaleResolver
    ) -> None:
        self._devices = devices
        self._sender = sender
        self._locales = locales

    async def notify(
        self, account_ids: list[UUID], notification: PushNotification
    ) -> None:
        if not account_ids:
            return
        tokens = await self._devices.tokens_by_account(account_ids)
        if not tokens:
            return  # personne n'a d'appareil : ni langue à résoudre, ni catalogue à ouvrir

        for locale, targets in (await self._group_by_locale(tokens)).items():
            text = self._render(notification, locale)
            if text is None:
                continue
            for token in targets:
                try:
                    await self._sender.send(
                        token=token, title=text.title, body=text.body, data=notification.data
                    )
                except Exception as exc:  # best-effort : une push ne casse jamais l'appelant
                    _logger.warning("push_send_failed", error=str(exc))

    async def _group_by_locale(
        self, tokens: dict[UUID, list[str]]
    ) -> dict[Locale, list[str]]:
        """Les jetons rangés par langue de leur propriétaire — l'unité d'un rendu."""
        spoken = await self._locales.resolve_many(list(tokens))
        grouped: dict[Locale, list[str]] = {}
        for account_id, account_tokens in tokens.items():
            grouped.setdefault(spoken.get(account_id, DEFAULT_LOCALE), []).extend(account_tokens)
        return grouped

    def _render(self, notification: PushNotification, locale: Locale) -> Message | None:
        # La sortie de secours des lignes d'avant le bilingue : le texte était déjà rendu, il
        # part tel quel. Disparaît avec les colonnes `title`/`body` de l'outbox.
        if notification.rendered is not None:
            return notification.rendered
        try:
            return render(notification.key, locale, notification.params)
        except (KeyError, IndexError) as exc:
            # Un paramètre manquant est un défaut de programmation, et le test de structure du
            # catalogue le rattrape. En production il ne doit pas emporter la publication.
            _logger.warning(
                "push_render_failed", key=str(notification.key), locale=str(locale), error=str(exc)
            )
            return None
