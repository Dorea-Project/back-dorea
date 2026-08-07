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
from datetime import datetime, timedelta
from uuid import UUID

from app.contexts.watch.application.my_cases import _OwnedCase
from app.contexts.watch.application.ports import (
    ContactAttemptStore,
    DeclaredLinkReader,
    GestureReader,
)
from app.contexts.watch.application.referent_ports import PeopleDirectory
from app.contexts.watch.domain.contact import ContactResult
from app.contexts.watch.domain.gesture import GESTURE_LABELS, GestureKind
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

# Combien de temps une visite explique encore un silence. Au-delà, elle ne dit plus rien de la
# situation d'aujourd'hui — et un bloc qui remonte à six mois est un bloc qu'on arrête de lire.
GESTURE_LOOKBACK = timedelta(days=30)

# Un geste dont le libellé a disparu du produit ne s'affiche pas plutôt que de faire tomber
# l'écran : le journal est immuable, le vocabulaire ne l'est pas.
_KNOWN_GESTURES: frozenset[str] = frozenset(k.value for k in GestureKind)


@dataclass(frozen=True)
class ContextSegment:
    """Une ligne du bloc, et **la source d'où elle vient**.

    `source` est ce que l'écran déplie : la traçabilité est gratuite ici, puisque chaque phrase
    *est* un champ. C'est ce qui permet au responsable de vérifier au lieu de croire."""

    kind: str  # episode | link | gesture | present | last_contact | commitment
    text: str
    at: datetime | None = None
    source: str | None = None
    # **Le lien fraternel, et il ne porte qu'un identifiant.** Aucune vue de la veille ne rend un
    # nom : c'est le client qui résout, comme partout ailleurs dans ce contexte. Ce champ n'est
    # donc pas une commodité d'affichage — c'est ce qui empêche le serveur de fabriquer des
    # phrases nominatives sur les gens, et ce qui garde le lien à un seul saut : il n'apparaît que
    # sur un cas ouvert, servi à son propriétaire, jamais dans une liste.
    account_id: UUID | None = None


@dataclass(frozen=True)
class CaseContextDTO:
    case_id: UUID
    segments: tuple[ContextSegment, ...] = ()

    @property
    def is_empty(self) -> bool:
        return not self.segments


class GetCaseContext(_OwnedCase):
    """Le bloc de contexte, assemblé par gabarits. Aucune décision, aucune interprétation."""

    def __init__(
        self,
        signals,
        attempts: ContactAttemptStore,
        gestures: GestureReader | None = None,
        people: PeopleDirectory | None = None,
        links: DeclaredLinkReader | None = None,
        *,
        clock,
    ) -> None:
        super().__init__(signals, None, clock=clock)
        self._attempts = attempts
        self._gestures = gestures
        self._people = people
        self._links = links

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
        segments += await self._declared_links(case, tenant_id)
        segments += await self._gestures_before(case, tenant_id)
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

    async def _declared_links(
        self, case: Signal, tenant_id: UUID
    ) -> list[ContextSegment]:
        """**Ce qu'elle a dit elle-même** — et c'est le lien le plus fort du bloc.

        Il passe avant le geste dans l'ordre de lecture, et l'ordre est la spécification : ce que
        la personne a consenti d'avance vaut mieux que ce qu'on a déduit d'un acte. En nommant
        quelqu'un, elle a dit *« vous pouvez passer par lui »* ; personne n'a rien demandé à Jean.

        Aucune fenêtre : un lien déclaré ne périme pas au bout de trente jours. Il se retire, et
        c'est elle qui le retire."""
        if self._links is None:
            return []
        segments: list[ContextSegment] = []
        for link in await self._links.declared_links(
            subject_id=case.subject_id, tenant_id=tenant_id
        ):
            if not await self._is_reachable(link.linked_account_id, tenant_id):
                continue
            segments.append(
                ContextSegment(
                    kind="declared_link",
                    # Aucun accord de genre, ici comme ailleurs : ces phrases s'affichent pour
                    # n'importe qui, et une formulation qui oblige à choisir se trompe un jour.
                    text=(
                        "Fait partie des proches que cette personne a indiqués. "
                        "Vous pouvez lui demander de ses nouvelles."
                    ),
                    at=link.declared_at,
                    source="watch_facts.self_declaration",
                    account_id=link.linked_account_id,
                )
            )
        return segments

    async def _gestures_before(
        self, case: Signal, tenant_id: UUID
    ) -> list[ContextSegment]:
        """**Le point aveugle du lot précédent, comblé par une lecture.**

        Jean est passé voir Sondet pendant l'absence — donc *avant* que l'échéance ne tombe. À cet
        instant il n'y avait aucun cas à enrichir, et l'interpreter n'a rien écrit : c'est la règle,
        déclarer une visite ne peut pas faire entrer quelqu'un en veille. Le cas s'ouvre donc trois
        semaines plus tard sans rien savoir de la visite, et le responsable décroche pour rien.

        La réparation ne touche pas la décision — elle n'a pas le droit d'y toucher. Elle se lit
        ici, sur l'écran qu'il regarde juste avant d'appeler. Le cas s'ouvre toujours ; il ne
        s'ouvre plus **muet**.

        **Strictement avant l'ouverture.** Ce qui est venu après est déjà sur la fiche, écrit par
        l'interpreter en annotation — l'afficher deux fois apprendrait à ne plus lire le bloc.
        """
        if self._gestures is None:
            return []
        seen = await self._gestures.gestures_between(
            subject_id=case.subject_id,
            tenant_id=tenant_id,
            since=case.opened_at - GESTURE_LOOKBACK,
            until=case.opened_at,
        )
        segments: list[ContextSegment] = []
        for g in seen:
            if g.kind not in _KNOWN_GESTURES:
                continue
            known = await self._is_reachable(g.by_account_id, tenant_id)
            text = f"{GESTURE_LABELS[GestureKind(g.kind)]} le {spoken_date(g.occurred_at)}."
            if known:
                # **La question, jamais l'information.** On ne dit pas au responsable ce que Jean
                # sait de Sondet — on lui dit qu'il peut le lui demander. La différence est tout le
                # module : l'information remonte *par* l'humain, jamais autour de lui.
                text = f"{text} Vous pouvez lui demander de ses nouvelles."
            segments.append(
                ContextSegment(
                    kind="gesture",
                    text=text,
                    at=g.occurred_at,
                    source="watch_facts.gesture_done",
                    account_id=g.by_account_id if known else None,
                )
            )
        return segments

    async def _is_reachable(self, account_id: UUID | None, tenant_id: UUID) -> bool:
        """Proposer d'appeler quelqu'un qui a quitté l'église — ou qui est mort — est pire que
        ne rien proposer. Le geste reste affiché ; c'est le lien qui disparaît."""
        if account_id is None or self._people is None:
            return False
        return await self._people.is_eligible(account_id, tenant_id)

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
