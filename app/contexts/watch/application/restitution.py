"""La restitution — **ce que le responsable relit avant d'appeler**.

Avant de composer le numéro, Jean lit six mois de lien en quatre lignes, au lieu de faire défiler
onze entrées dans le bus. Quatre propriétés, et la quatrième est la plus importante :

- **que du déjà-écrit.** Chaque segment *est* un champ de la base — l'épisode, l'issue précédente,
  la date du dernier contact, l'engagement qu'il avait pris. Rien n'est reformulé, rien n'est
  déduit ;
- **servi à qui a déjà le droit de tout lire.** Le même contrôle que le reste de l'écran du cas :
  son propriétaire, personne d'autre. Il n'y a rien de nouveau à sécuriser ;
- **aucune conclusion.** Pas de « semble fragile », pas de conseil de posture, pas de score. Le
  bloc rend des faits datés et se tait ;
- **zéro IA.** C'est la découverte en spécifiant : tout ce que le résumé contenait était **déjà
  structuré** en base. Des gabarits fermés suffisent, et le coût reste nul. L'IA ne deviendra
  nécessaire que le jour où il y aura beaucoup de texte libre à condenser — c'est-à-dire quand les
  engagements des responsables seront longs et nombreux, pas avant.

**Un cas sans histoire n'affiche rien.** Pas de bloc vide, pas de « aucune information » : un
encart qui ne dit rien apprend au lecteur à ne plus le lire.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.contexts.watch.application.my_cases import _OwnedCase
from app.contexts.watch.application.ports import ContactAttemptStore
from app.contexts.watch.domain.contact import ContactResult
from app.contexts.watch.domain.signal import MONTHS, Signal, spoken_date

# Ce que chaque issue de contact **dit**, en clair. Même principe que les issues de cas : une
# phrase que le responsable lit, pas un code d'état.
_RESULT_LABELS: dict[ContactResult, str] = {
    ContactResult.REACHED: "vous l'avez eue",
    ContactResult.NOT_REACHED: "sans réponse",
    ContactResult.POSTPONED: "à rappeler",
    ContactResult.PENDING: "tentative en cours",
}

_CHANNEL_LABELS: dict[str, str] = {
    "call": "par téléphone",
    "whatsapp": "sur WhatsApp",
    "visit": "en visite",
    "other": "",
}


@dataclass(frozen=True)
class ContextSegment:
    """Une ligne du bloc, et **la source d'où elle vient**.

    `source` est ce que l'écran déplie : la traçabilité est gratuite ici, puisque chaque phrase
    *est* un champ. C'est ce qui permet au responsable de vérifier au lieu de croire."""

    kind: str  # episode | link | present | last_contact | commitment
    text: str
    at: datetime | None = None
    source: str | None = None


@dataclass(frozen=True)
class CaseContextDTO:
    case_id: UUID
    segments: tuple[ContextSegment, ...] = ()

    @property
    def is_empty(self) -> bool:
        return not self.segments


class GetCaseContext(_OwnedCase):
    """Le bloc de contexte, assemblé par gabarits. Aucune décision, aucune interprétation."""

    def __init__(self, signals, attempts: ContactAttemptStore, *, clock) -> None:
        super().__init__(signals, None, clock=clock)
        self._attempts = attempts

    async def execute(
        self, *, signal_id: UUID, tenant_id: UUID, actor_account_id: UUID
    ) -> CaseContextDTO:
        case = await self._load(
            signal_id=signal_id, tenant_id=tenant_id, actor_account_id=actor_account_id
        )
        segments: list[ContextSegment] = []
        segments += self._link(case, await self._signals.accompanied_since(
            subject_id=case.subject_id, tenant_id=tenant_id
        ))
        segments += self._episode(case)
        segments += self._present(case)
        segments += await self._contacts(case)
        return CaseContextDTO(case_id=case.id, segments=tuple(segments))

    def _link(self, case: Signal, since: datetime | None) -> list[ContextSegment]:
        """« Vous l'accompagnez depuis février. »

        La phrase que le responsable ne peut pas reconstruire de tête, et qui change la façon
        d'ouvrir un appel : on ne parle pas de la même manière à quelqu'un qu'on suit depuis six
        mois qu'à quelqu'un dont le cas vient de s'ouvrir."""
        if since is None:
            return []
        return [
            ContextSegment(
                kind="link",
                text=f"Vous l'accompagnez depuis {MONTHS[since.month - 1]}.",
                at=since,
                source="watch_care_memory",
            )
        ]

    def _episode(self, case: Signal) -> list[ContextSegment]:
        """Ce que l'issue précédente dit — la phrase existe déjà sur l'agrégat, on la place ici."""
        note = case.previous_case_note
        if note is None:
            return []
        return [
            ContextSegment(
                kind="episode",
                text=f"{note} C'est la {case.occurrence_number}ᵉ fois.",
                at=case.previous_closed_at,
                source="watch_signals.previous_outcome",
            )
        ]

    def _present(self, case: Signal) -> list[ContextSegment]:
        """La raison d'aujourd'hui, et ce qu'on a appris depuis. Citées, jamais réécrites."""
        segments = [
            ContextSegment(
                kind="present",
                text=case.reason,
                at=case.opened_at,
                source="watch_signals.reason",
            )
        ]
        segments += [
            ContextSegment(
                kind="present",
                text=annotation,
                source="watch_signals.annotations",
            )
            for annotation in case.annotations
        ]
        return segments

    async def _contacts(self, case: Signal) -> list[ContextSegment]:
        """Le dernier contact, et **l'engagement qu'on avait pris**.

        C'est le segment que le responsable oublie le plus vite et regrette le plus : « vous aviez
        noté vouloir la rappeler aujourd'hui » n'a pas d'équivalent dans un cahier."""
        attempts = await self._attempts.recent_for(signal_id=case.id, limit=3)
        segments: list[ContextSegment] = []
        for attempt in attempts:
            channel = _CHANNEL_LABELS.get(
                getattr(attempt.channel, "value", str(attempt.channel)), ""
            )
            issue = _RESULT_LABELS[attempt.result]
            when = spoken_date(attempt.attempted_at)
            segments.append(
                ContextSegment(
                    kind="last_contact",
                    text=f"Contact le {when} {channel} — {issue}.".replace("  ", " "),
                    at=attempt.attempted_at,
                    source="watch_contact_attempts",
                )
            )
            if attempt.commitment:
                segments.append(
                    ContextSegment(
                        kind="commitment",
                        # **Cité tel quel.** Citer n'est pas résumer : aucun risque de déformer ce
                        # que quelqu'un s'était engagé à faire.
                        text=f"Vous aviez noté : « {attempt.commitment} »",
                        at=attempt.answered_at or attempt.attempted_at,
                        source="watch_contact_attempts.commitment",
                    )
                )
        return segments
