"""Étage 7 — **le thème proposé**, et ce qu'il refuse de regarder.

Le dernier étage. Il croise deux choses, et **deux seulement** :

- l'**axe retenu** — le locus dominant, curé et relu ;
- l'**historique de l'auteur** — `urim.preached`, une donnée d'Urim clée sur lui.

## Ce qu'il ne croise pas, et c'est une correction de la spec elle-même

La spec d'origine faisait croiser au thème « l'axe retenu, **le calendrier ecclésial**,
l'historique ». E1 l'a corrigée : le calendrier ne rentre pas. Il s'**affiche à côté**, et le
pasteur en tient compte lui-même.

Le motif du refus vaut d'être gardé tel quel :

> *« Un baptême dimanche, c'est légitime »* vaudrait demain pour *« douze malades ce mois-ci »*.

Une exception étroite pour l'étage 7 aurait rendu le mur négociable. Et le test qui inspecte le
bytecode refuserait de toute façon tout étage lisant `deps.context`.

## Ce qu'il évite

Le thème se dérive du locus **dominant**, soutenu par les axes **portés**, en évitant ce qui
**résiste**. Un locus `absent` n'affiche rien et aucun plan ne se construit dessus.

## Une proposition, pas un titre

L'étage **propose** et continue : il ne bloque pas le pasteur à la dernière marche. La formulation
est un gabarit fermé — déterministe, sans modèle. Le jour où une étape modèle reformulera plus
joliment, elle restera un accélérateur, jamais une dépendance (S12).

## Pourquoi cet étage redemande au corpus ce que le bornage savait déjà

`bounds_overridden` est vrai pour **deux raisons opposées** : le pasteur a choisi « gardez mes
bornes », ou bien aucune unité curée ne couvrait le passage. La conséquence mécanique est la
même — rien de relu n'est lisible — et c'est pourquoi un seul booléen suffit à la porter (S22).
Mais la *phrase* n'est pas la même, et disait jusqu'ici « Bornes forcées » dans les deux cas.

À 0,23 % de couverture curée, le second cas est l'ordinaire : presque chaque préparation
s'entendait reprocher un forçage qui n'avait pas eu lieu. C'est la règle des refus, appliquée à
un motif — *on dit ce qui manque au moteur, jamais ce qui manque au pasteur.*

Le bornage, lui, connaissait la raison au moment de poser le drapeau. Elle ne peut pas voyager
dans l'état : au rejeu, `bound_pericope` ne s'applique plus (les bornes sont déjà là) et un champ
supplémentaire ne serait jamais recalculé. On repose donc la question au corpus, qui est le seul
à pouvoir y répondre à tout instant : *une unité curée couvrait-elle ce passage ?*

Un nouveau semis peut faire basculer la réponse pour une préparation ancienne. C'est précisément
ce que `corpus_drifted` signale, et c'est le prix assumé de ne pas ajouter une colonne qui dirait
la même chose et pourrait la contredire.

⚠️ **Et cette phrase n'atteint aujourd'hui aucun pasteur.** La chaîne se referme d'elle-même :
`bounds_overridden` n'est vrai que lorsque `pericope_id` est `None` — les trois écrivains le
posent ainsi —, sans unité curée `bear_axes` dégrade sans retenir d'axe, et sans axe cet étage ne
s'applique pas. La branche est un garde-fou, pas un comportement observable ; le corriger valait
quand même mieux que laisser une phrase fausse attendre son jour.

Ce que la découverte dit vraiment est plus grave que la formulation : **hors unité curée, le
pipeline s'arrête à la pesée doctrinale.** Le pasteur reçoit son texte et rien après.

⚠️ **Mise à jour du 2026-08-13 — ce n'est plus la curation qui manque, c'est un bouton.** La
phrase disait « soit 99,77 % de l'Écriture aujourd'hui » : le corpus l'a rattrapée, 4 561 unités
couvrent désormais les 66 livres et toutes portent leurs pesées. Le chemin qui menait là est
donc passé du cas ordinaire au cas de **« Mes bornes »** — `pericope_id` retombe à `None`, et
S22 se propage. Le tour rendu à cet endroit est réparé et gardé
(`docs/Urim_Arbre_Conversationnel.md`, mur n°2) ; la branche, elle, reste vivante.
"""

from __future__ import annotations

from app.contexts.urim.engine.deps import EngineDeps
from app.contexts.urim.engine.errors import StagePrerequisiteError
from app.contexts.urim.engine.outcomes import Outcome, StageResult
from app.contexts.urim.engine.state import StudyState


class ProposeTheme:
    """Le huitième et dernier étage. Il propose, il n'intitule pas."""

    code = "propose_theme"

    def applies(self, state: StudyState) -> bool:
        return state.axis is not None and state.theme is None

    def execute(self, state: StudyState, deps: EngineDeps) -> StageResult:
        if state.axis is None:
            raise StagePrerequisiteError("le thème exige un axe retenu")

        deja = list(deps.homiletics.recently_preached_axes(state.author_id))
        redite = state.axis in deja

        theme = _gabarit(state)
        return StageResult(
            outcome=Outcome.CONTINUE,
            rationale=_motif(state, redite, _une_unite_existait(state, deps)),
            state=state.with_(theme=theme),
        )


def _gabarit(state: StudyState) -> str:
    """Un gabarit **fermé** : même état, même phrase. Aucun modèle, aucune surprise."""
    forme = (
        f", en {state.plan_source} {state.subject_matter}"
        if state.plan_source and state.subject_matter
        else ""
    )
    return f"{state.axis}{forme}"


def _une_unite_existait(state: StudyState, deps: EngineDeps) -> bool:
    """Le corpus avait-il **quelque chose à proposer** sur ce passage ?

    C'est toute la différence entre un choix du pasteur et un trou du moteur, et elle se relit
    ici plutôt qu'elle ne se transporte — voir l'en-tête du module."""
    if state.resolved is None:
        return False
    return bool(list(deps.corpus.pericopes_for(state.resolved)))


def _motif(state: StudyState, redite: bool, unite_existait: bool) -> str:
    dit = f"Thème proposé à partir de l'axe retenu : {state.axis}."
    if redite:
        # L'archive informe, elle n'interdit rien : prêcher deux fois le même axe est un choix
        # légitime, et le pasteur est le seul à savoir pourquoi.
        dit += " Vous avez déjà prêché cet axe récemment."
    if state.bounds_overridden:
        # ⚠️ Deux phrases, parce qu'il y a deux situations — et une seule des deux relève d'une
        # décision du pasteur. Lui parler de « bornes forcées » quand le corpus n'avait rien à
        # lui opposer, c'est lui imputer le vide du moteur.
        dit += (
            " Bornes que vous avez conservées — le thème ne s'appuie sur aucune faisabilité relue."
            if unite_existait
            else " Hors unité curée — le thème ne s'appuie sur aucune faisabilité relue."
        )
    return dit
