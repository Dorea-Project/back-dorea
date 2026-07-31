"""« N'insistez plus. » — l'arrêt d'urgence du membre, **inconditionnel et absorbant**.

C'est la contrepartie de la frontière de transparence, et elle n'est pas facultative : le membre ne
peut pas lister ce qu'un tiers a ressenti à son sujet, mais il n'a pas besoin de voir le dossier
pour être protégé — il a un bouton qui arrête tout, sans avoir à savoir ce qui existait.

Trois propriétés, et chacune est un refus de quelque chose d'ordinaire :

- **Sans motif.** Aucun champ, aucune liste de raisons, aucune confirmation qui demande pourquoi.
  Exiger une justification pour qu'on cesse de vous contacter, c'est faire de la sortie une
  négociation. « Non » suffit, et c'est même la seule réponse qui n'a jamais à s'expliquer.
- **Absorbant.** `DO_NOT_CONTACT` est une issue dont aucune transition ne sort. Une veille dont on
  ne peut pas sortir est un fichage ; celle-ci se quitte définitivement, et aucune bonne intention
  ne la rouvre.
- **Immédiat, échéances comprises.** Les rappels programmés sont annulés dans le même geste. Sans
  ça, la personne qui vient de demander qu'on cesse recevrait un rappel posé trois semaines plus
  tôt — et la parole qu'on s'était engagé à respecter serait démentie par une notification
  automatique.

Ce que ce service **n'est pas** : une suppression. Rien n'est effacé du journal, et ce n'est pas de
la mauvaise foi — le ledger est append-only par construction, et l'histoire d'une personne n'a pas
à disparaître pour qu'on cesse de la déranger. Ce qui s'arrête, c'est le contact.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.contexts.watch.application.ports import ScheduledCheckStore, SignalStore
from app.contexts.watch.domain.signal import SignalOutcome


@dataclass(frozen=True)
class ContactStopped:
    """« C'est noté. » — une seule phrase, et rien à ajouter."""

    message: str = "C'est noté. Nous ne vous contacterons plus."
    had_open_case: bool = False


class StopContactingMe:
    def __init__(
        self,
        signals: SignalStore,
        checks: ScheduledCheckStore | None = None,
        *,
        clock,
    ) -> None:
        self._signals = signals
        self._checks = checks
        self._clock = clock

    async def execute(self, *, tenant_id: UUID, actor_account_id: UUID) -> ContactStopped:
        """L'acteur **est** le sujet : personne ne pose ce retrait pour quelqu'un d'autre.

        Un responsable qui « retirerait » un membre de la veille prendrait une décision qui
        n'appartient qu'à lui — et le jour où ça arriverait, ce serait pour se débarrasser d'un cas
        gênant. La route ne prend donc aucun identifiant de sujet."""
        now = self._clock()
        case = await self._signals.live_case_of(
            subject_id=actor_account_id, tenant_id=tenant_id
        )
        if case is not None:
            await self._signals.resolve_case(
                subject_id=actor_account_id,
                tenant_id=tenant_id,
                outcome=SignalOutcome.DO_NOT_CONTACT.value,
                at=now,
                # C'est **elle** qui ferme : la clôture est humaine, et l'humain est la personne.
                by_account_id=actor_account_id,
            )
        if self._checks is not None:
            # Toutes, sans distinction de régime : « n'insistez plus » ne souffre pas d'exception.
            await self._checks.cancel_for(
                subject_id=actor_account_id, tenant_id=tenant_id, kind=None, at=now
            )
        return ContactStopped(had_open_case=case is not None)
