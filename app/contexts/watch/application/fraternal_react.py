"""Le **react fraternel** — *« tu es passé voir Anna il y a un mois. Un mot ? »*

Une veille n'est pas silencieuse. Mais la question n'a jamais été *si* elle parle : c'est **vers
qui**.

> Le moteur se tait vers Anna, et parle vers Jean.

Son silence et sa parole n'ont pas le même destinataire, et c'est ce qui lui permet de ne pas être
muet sans devenir bavard sur les gens.

---

## Ce que ce module a failli être, et pourquoi il ne l'est pas

La façon évidente de proposer à Jean d'écrire à Anna serait de chercher **de qui Jean est un
proche** — le sens inverse du lien déclaré. Deux règles tombent d'un coup :

- le graphe devient énumérable, et son complément est une carte d'isolement ;
- **Jean apprend qu'Anna l'a nommé**, alors que le lien déclaré ne prévient jamais celui qu'il
  désigne. On aurait fabriqué la déclaration d'affinité semi-publique qu'on refuse depuis le début.

Et un second piège juste derrière : filtrer sur le silence d'Anna. La présence d'Anna dans la liste
de Jean **serait** alors l'information — un cas de veille fuité à un membre par la porte de
derrière, avec les meilleures intentions du monde.

D'où la forme retenue : **le react ne se calcule que sur les propres actes de Jean.** Il y était,
il le sait, on ne lui apprend rien. Le seul compte à rebours est celui de **son** geste.

## Ce qu'il ne fait pas

**Il n'écrit rien.** Proposer n'est pas un événement de veille, et la proposition ignorée ne laisse
aucune trace — sinon on noterait les gens sur leur réactivité, ce qui est un fait tiré d'un silence.
Ce qui entre au journal, c'est ce que Jean fera ensuite : un geste s'il y retourne, et surtout la
parole d'Anna si elle répond. **Seule la réponse écrit.**

Effet de bord heureux : le react est **ininstrumentable**. Personne ne peut faire bouger le moteur
en le consultant.

**Il ne fournit aucun texte.** Ni ici, ni ailleurs. Le moteur donne un nom et une raison d'écrire,
jamais les mots — si deux personnes reçoivent la même phrase, la phrase ne vaut plus rien, et on
aura enseigné à l'église que saluer est un bouton.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from app.contexts.watch.application.ports import (
    GestureReader,
    NeutralizationStore,
    SignalStore,
)
from app.contexts.watch.application.referent_ports import (
    PeopleDirectory,
    WatchParameterRepository,
)
from app.contexts.watch.domain.parameters import WatchParam


@dataclass(frozen=True)
class FraternalReact:
    """Une invitation. **Un identifiant et une date — la sienne.**

    `last_gesture_at` est la date du geste de Jean, pas une mesure du silence d'Anna. C'est la
    seule date qu'on ait le droit de lui rendre, et elle lui appartient.

    Aucun nom : comme partout dans ce contexte, le client résout. Aucun motif non plus — il n'y en
    a pas à donner, et en donner un reviendrait à dire quelque chose d'Anna."""

    account_id: UUID
    last_gesture_at: datetime


class SuggestFraternalReacts:
    """Ce que le compagnon demande à l'ouverture, pour la personne connectée et pour elle seule."""

    def __init__(
        self,
        gestures: GestureReader,
        signals: SignalStore,
        exclusions: NeutralizationStore,
        people: PeopleDirectory,
        params: WatchParameterRepository,
        *,
        clock,
    ) -> None:
        self._gestures = gestures
        self._signals = signals
        self._exclusions = exclusions
        self._people = people
        self._params = params
        self._clock = clock

    async def execute(
        self, *, actor_account_id: UUID, tenant_id: UUID
    ) -> list[FraternalReact]:
        now = self._clock()
        after = await self._params.get_int(tenant_id, WatchParam.REACT_AFTER_DAYS)
        cap = await self._params.get_int(tenant_id, WatchParam.REACT_SUGGESTIONS_CAP)

        mine = await self._gestures.gestures_by(
            actor_account_id=actor_account_id,
            tenant_id=tenant_id,
            before=now - timedelta(days=after),
            # De quoi remplir le plafond après le filtrage des sorties — un décès, un départ, une
            # demande qu'on cesse. Sans marge, une seule sortie viderait la proposition.
            limit=cap * 3,
        )
        if not mine:
            return []

        silenced = await self._signals.do_not_contact_ids(tenant_id)
        excluded = await self._exclusions.excluded_subject_ids(tenant_id)

        suggestions: list[FraternalReact] = []
        for gesture in mine:
            if len(suggestions) >= cap:
                break
            # **Les trois sorties, et aucune n'a besoin d'être expliquée à Jean.** Quelqu'un qui a
            # demandé qu'on cesse, quelqu'un qui est mort, quelqu'un qui a quitté l'église : la
            # proposition disparaît, et rien ne dit laquelle des trois — sinon la disparition
            # elle-même deviendrait une information.
            if gesture.subject_id in silenced or gesture.subject_id in excluded:
                continue
            if not await self._people.is_eligible(gesture.subject_id, tenant_id):
                continue
            suggestions.append(
                FraternalReact(
                    account_id=gesture.subject_id,
                    last_gesture_at=gesture.occurred_at,
                )
            )
        return suggestions
