"""Étage 0-bis — **le vestibule** : on n'entre pas en préparation sans avoir dit oui.

🔴 **Le défaut qu'il ferme a été vu sur un téléphone, le 22/08/2026.** Un pasteur écrit
« bonjour Urim », et une préparation s'ouvre ; le moteur descend, pèse, et rend 1 Corinthiens.
Ce n'était pas un accident : **écrire une phrase et ouvrir une préparation étaient le même
geste**, et 150 lignes vides en base le disaient depuis des semaines sans que personne les lise.

> **Envoyer un texte n'est pas demander à le préparer.**

## Ce que cet étage fait, et ce qu'il ne fait pas

Il **n'appelle aucun modèle** — aucun étage ne le fait, c'est la règle de séparation. La lecture
du vestibule est faite par la bordure (`study_service`), écrite dans l'état, et **relue** ici.
Cet étage ne fait qu'une chose : décider si le pipeline a le droit de continuer.

    absent · pressenti   →  REFUSE, et le motif est la parole de l'agent — on converse
    nomme                →  AWAIT, deux options : préparer, ou seulement lire
    confirme             →  l'étage ne s'applique pas, le moteur descend

⚠️ **Pourquoi `REFUSE` pour une conversation qui va bien.** Le vocabulaire des issues n'a pas de
« rends la main sans rien proposer » : `AWAIT` exige des options, et il n'y en a pas — le pasteur
doit parler, pas choisir. `REFUSE` porte un motif et rend la main, ce qui est exactement le geste
voulu ; la barre de saisie, elle, ne se ferme jamais. C'est déjà la forme qu'a prise l'accueil de
la civilité le matin même.

## La borne haute, et elle compte autant que la règle

Un vestibule trop bavard est pire que pas de vestibule : le pasteur qui sait ce qu'il veut se
retrouve à demander la permission de travailler. D'où `nomme` → **une** proposition, une seule,
et un sujet décliné qui ne revient jamais (RT1).
"""

from __future__ import annotations

from app.contexts.urim.engine.deps import EngineDeps
from app.contexts.urim.engine.normalizer import normalize
from app.contexts.urim.engine.outcomes import Option, Outcome, StageResult
from app.contexts.urim.engine.state import Maturite, StudyState

#: Le code de l'option qui **ouvre**. C'est le seul geste au monde qui pose `confirme`.
CONSENTIR = "vestibule:preparer"

#: Le code de l'option qui lit sans engager. Elle mène au même moteur, sans le travail de
#: préparation — *envoyer un texte, c'est `recherche` par défaut*.
LIRE_SEULEMENT = "vestibule:lire"

#: Les deux issues d'une **suspension** — un autre sujet arrive sur un travail commencé.
#:
#: Elles ne sont pas les mêmes que celles de l'ouverture, et c'est tout le sujet de §4 : la
#: question n'est plus « voulez-vous préparer ? » mais « lequel des deux préparez-vous ? ».
CHANGER = "vestibule:changer"
RATTACHER = "vestibule:rattacher"

_SANS_SUJET = (
    "Je vous écoute. Dites-moi ce qui vous occupe, ou donnez-moi un passage — "
    "je ne prépare rien tant que vous ne me l'avez pas demandé."
)


class Vestibule:
    """Le premier étage, et le seul qui puisse refuser d'entrer."""

    code = "vestibule"

    def applies(self, state: StudyState) -> bool:
        """Tant que le sujet n'est pas **confirmé par le pasteur**, rien ne descend.

        ⚠️ **Et il ne se ré-applique jamais après.** `confirme` est un état persisté : une fois
        posé, cet étage disparaît du chemin pour toujours. Sans quoi chaque rejeu redemanderait
        son accord à quelqu'un qui l'a déjà donné — le défaut que `route_entry` a connu avec
        `entry_mode`, et qui reposait éternellement la même question."""
        return state.maturity != Maturite.CONFIRME

    def execute(self, state: StudyState, deps: EngineDeps) -> StageResult:
        if (
            state.maturity == Maturite.NOMME
            and state.carried_subject
            and not self._decline(state)
        ):
            # **Deux questions différentes, et la différence est l'état du travail.** Sur une
            # page blanche : « voulez-vous en faire une préparation ? ». Sur un travail
            # commencé : « lequel des deux ? ». Les confondre ferait perdre l'un ou l'autre.
            return (
                self._suspendre(state) if self._travail_commence(state)
                else self._proposer(state)
            )

        # `absent` et `pressenti` se traitent pareil **ici**, et différemment ailleurs : la
        # nuance entre « il n'a rien » et « quelque chose affleure » vit dans la phrase de
        # l'agent, écrite par le vestibule de la bordure. Le moteur, lui, ne connaît qu'une
        # question : a-t-on le droit de descendre ?
        return StageResult(
            outcome=Outcome.REFUSE,
            rationale=state.vestibule_reply or _SANS_SUJET,
            state=state,
        )

    def _travail_commence(self, state: StudyState) -> bool:
        """Y a-t-il quelque chose à perdre ? Un texte résolu, une unité bornée, un axe, un
        thème — n'importe lequel suffit, et aucun ne se devine."""
        return any((
            state.resolved is not None,
            state.pericope_id is not None,
            state.axis is not None,
            state.theme is not None,
        ))

    def _decline(self, state: StudyState) -> bool:
        """Ce sujet a-t-il **déjà été refusé** ? (RT1)

        La pente naturelle d'un modèle est d'être serviable tout de suite : s'il peut proposer,
        il proposera à chaque tour, et la conversation devient un harcèlement poli. Un sujet
        décliné ne revient donc pas — **un autre candidat peut mûrir**, celui-là non.

        ⚠️ **La comparaison est normalisée**, sinon « Le Pardon » reviendrait après « le
        pardon » et la retenue serait contournée par une majuscule."""
        if not state.declined_subjects:
            return False
        vise = normalize(state.carried_subject or "")
        return any(vise == normalize(sujet) for sujet in state.declined_subjects)

    def _suspendre(self, state: StudyState) -> StageResult:
        """Un **autre** sujet arrive sur un travail commencé — on ne le fond pas dedans.

        🔴 **Le défaut que ça ferme est le plus sournois du fil.** Une fois un sujet en
        mémoire, tout ce qui arrive est lu *à travers lui* : le pasteur envoie Luc 15 alors
        qu'il travaillait sur le pardon, et l'agent lui répond sur le pardon. Il répond avec ce
        qu'il a gardé, **pas à la préoccupation du tour**.

        > **Un système qui se souvient trop enferme.** L'état doit servir la reprise, jamais
        > l'interprétation forcée.

        D'où la symétrie avec la règle du consentement : ce qui arrive **suspend** l'état, il
        ne s'y fond pas — et il ne l'écrase pas non plus. C'est le pasteur qui tranche, en un
        tour."""
        nouveau = state.carried_subject or ""
        # Le thème s'il existe, sinon le livre du passage retenu, sinon rien de précis :
        # nommer faux serait pire que ne pas nommer.
        en_cours = (
            state.theme
            or (state.resolved.book if state.resolved else None)
            or "ce que vous prépariez"
        )

        return StageResult(
            outcome=Outcome.AWAIT,
            rationale=(
                f"Vous travailliez sur {en_cours}. « {nouveau} », c'est un autre chemin — "
                "vous changez de sujet, ou vous voulez le rattacher à ce qui est en cours ?"
            ),
            state=state,
            options=(
                Option(
                    code=CHANGER,
                    label=f"Changer pour « {nouveau} »",
                    rationale=(
                        "Le travail en cours reste dans votre fil ; celui-ci repart de zéro."
                    ),
                    origin="vestibule",
                ),
                Option(
                    code=RATTACHER,
                    label="Rester sur ce qui est en cours",
                    rationale=(
                        "On garde le texte et les décisions déjà prises. Votre phrase ne se "
                        "perd pas : elle reste dans le fil."
                    ),
                    origin="vestibule",
                ),
            ),
        )

    def _proposer(self, state: StudyState) -> StageResult:
        """Un sujet est là. **On demande — on n'ouvre pas.**

        Les deux options ne sont pas symétriques et ne doivent pas l'être : préparer engage un
        travail, lire n'engage rien. C'est pourquoi lire est **le défaut du produit** et
        préparer, le geste qui se demande."""
        sujet = state.carried_subject or ""

        return StageResult(
            outcome=Outcome.AWAIT,
            rationale=(
                state.vestibule_reply
                or f"J'ai compris : {sujet}. Que voulez-vous en faire ?"
            ),
            state=state,
            options=(
                Option(
                    code=CONSENTIR,
                    label="En faire une préparation",
                    rationale=(
                        "Le moteur descend : il cherche le texte, borne l'unité, pèse les axes."
                    ),
                    origin="vestibule",
                ),
                Option(
                    code=LIRE_SEULEMENT,
                    label="Seulement l'ouvrir et lire",
                    rationale=(
                        "On regarde le texte, sans rien engager. Vous pourrez préparer ensuite."
                    ),
                    origin="vestibule",
                ),
            ),
        )
