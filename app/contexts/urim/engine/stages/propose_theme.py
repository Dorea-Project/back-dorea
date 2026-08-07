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
            rationale=_motif(state, redite),
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


def _motif(state: StudyState, redite: bool) -> str:
    dit = f"Thème proposé à partir de l'axe retenu : {state.axis}."
    if redite:
        # L'archive informe, elle n'interdit rien : prêcher deux fois le même axe est un choix
        # légitime, et le pasteur est le seul à savoir pourquoi.
        dit += " Vous avez déjà prêché cet axe récemment."
    if state.bounds_overridden:
        dit += " Bornes forcées — le thème ne s'appuie sur aucune faisabilité relue."
    return dit
