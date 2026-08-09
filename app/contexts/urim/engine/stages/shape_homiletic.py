"""Étage 6 — **la faisabilité homilétique** : un refus motivé, jamais un plan fabriqué.

E2 l'a établi contre la spec d'origine : la mise en forme homilétique **est un étage**, pas une
mise en page. Elle consomme les axes, elle rend un résultat motivé, et elle peut `REFUSE` —
`homiletic_feasibility.refusal_reason` existe en base précisément pour ça.

## La faisabilité est celle d'un triplet, pas d'un texte

`Romains 8:9-17` ne porte aucun personnage. Croisé avec **biographique**, il ne produit pas un
plan : il produit un refus, et le refus dit pourquoi.

> **Une combinaison impossible est signalée, jamais fabriquée.** Urim n'invente pas un personnage
> pour satisfaire une case.

Et les couples refusés voyagent avec les faisables — les cacher laisserait le pasteur croire qu'on
n'y a pas pensé.

## Le risque de proof-texting, et ce qui le relève

Il est **structurellement plus élevé en thématique** : les textes y sont convoqués pour confirmer.
Deux choses le relèvent encore, et elles ne choisissent jamais le texte (S26, S37) :

- une **intention déclarée** — « je veux motiver » n'ajoute aucun axe, ça change le risque ;
- la **charge d'une conviction** — même patron, même propriété de sûreté.

Un signal qui ne peut qu'**ajouter de la vigilance** ne peut pas nuire en se trompant. Et le motif
nomme l'effet, jamais l'état de celui qui écrit.

## Hors unité curée

`homiletic_feasibility` est clée sur la péricope : bornes forcées, aucune ligne. `DEGRADE`, jamais
`REFUSE` (S22) — *on ne punit pas une liberté qu'on a accordée, et on ne devine pas une
faisabilité que personne n'a relue.*
"""

from __future__ import annotations

from collections.abc import Sequence

from app.contexts.urim.engine.deps import EngineDeps, Feasibility
from app.contexts.urim.engine.errors import StagePrerequisiteError
from app.contexts.urim.engine.outcomes import Option, Outcome, StageResult
from app.contexts.urim.engine.state import StudyState

#: Du moins au plus risqué. L'ordre **est** l'échelle — il n'y a pas de score.
RISQUES: tuple[str, ...] = ("faible", "moyen", "eleve")


class ShapeHomiletic:
    """Le septième étage. Il refuse plutôt que de fabriquer."""

    code = "shape_homiletic"

    def applies(self, state: StudyState) -> bool:
        """Il faut un axe retenu — la forme se décide après le fond, jamais avant."""
        return state.axis is not None and state.subject_matter is None

    def execute(self, state: StudyState, deps: EngineDeps) -> StageResult:
        if state.axis is None:
            raise StagePrerequisiteError("la mise en forme exige un axe retenu")

        if state.pericope_id is None:
            return StageResult(
                outcome=Outcome.DEGRADE,
                rationale=(
                    "Bornes hors unité curée — aucune faisabilité relue, et donc aucune alerte "
                    "de risque de proof-texting. La préparation continue."
                ),
                state=state,
            )

        couples = list(deps.homiletics.couples_for(state.pericope_id))

        # ⚠️ **Aucune ligne n'est pas la même chose que « rien n'est faisable ».**
        #
        #     aucune ligne  →  personne n'a encore regardé
        #     que des refus →  quelqu'un a regardé, et rien ne tient sur ce texte
        #
        # `bear_axes` tient cette distinction depuis le début ; cet étage ne la tenait pas, et
        # le défaut n'apparaissait qu'une fois la curation *améliorée* : sans péricope il
        # dégradait et continuait, avec une péricope pesée mais sans faisabilité il refusait.
        # Ajouter du relu rendait la sortie pire, ce qui est le signe d'une confusion et non
        # d'une sévérité.
        if not couples:
            return StageResult(
                outcome=Outcome.DEGRADE,
                rationale=(
                    "Aucune faisabilité n'a encore été relue sur cette unité — ni mise en "
                    "forme proposée, ni alerte de proof-texting. La préparation continue."
                ),
                state=state,
            )

        faisables = [couple for couple in couples if couple.feasible]
        refuses = [couple for couple in couples if not couple.feasible]

        if state.plan_source is None:
            if not faisables:
                # Tous les couples relus sont refusés : c'est un fait curé, pas un échec du
                # moteur. Et chaque refus porte son motif.
                return StageResult(
                    outcome=Outcome.REFUSE,
                    rationale=_avec_refus(
                        "Aucune mise en forme n'est faisable sur cette unité.", refuses
                    ),
                    state=state,
                )
            return StageResult(
                outcome=Outcome.AWAIT,
                rationale=_avec_refus(
                    f"{len(faisables)} mises en forme sont possibles sur cette unité.", refuses
                ),
                state=state,
                options=tuple(_option(couple) for couple in faisables),
            )

        choisi = _trouver(couples, state.plan_source, state.subject_matter)
        if choisi is None or not choisi.feasible:
            motif = choisi.refusal_reason if choisi else "Ce couple n'a pas été relu."
            return StageResult(
                outcome=Outcome.REFUSE, rationale=motif, state=state
            )

        risque = _releve(choisi.proof_text_risk, state.risk_flags)
        return StageResult(
            outcome=Outcome.CONTINUE,
            rationale=_motif_du_risque(choisi, risque, state.risk_flags),
            state=state.with_(
                plan_source=choisi.plan_source, subject_matter=choisi.subject_matter
            ),
        )


# --- Le risque -----------------------------------------------------------------------------------


def _releve(risque: str, drapeaux: Sequence[str]) -> str:
    """Une intention ou une charge **relève** le risque d'un cran — elle ne choisit aucun texte.

    Faux positif : de la vigilance en plus, inoffensif. Faux négatif : le comportement
    d'aujourd'hui. Aucun modèle : rien ne casse. C'est ce qui rend ce signal acceptable là où
    « détecter pour router » ne l'était pas."""
    if not drapeaux or risque not in RISQUES:
        return risque
    return RISQUES[min(RISQUES.index(risque) + 1, len(RISQUES) - 1)]


def _motif_du_risque(couple: Feasibility, risque: str, drapeaux: Sequence[str]) -> str:
    dit = (
        f"Mise en forme retenue : {couple.plan_source} x {couple.subject_matter}. "
        f"Risque de proof-texting : {risque}."
    )
    if drapeaux:
        # ⚠️ Le motif nomme **l'effet**, jamais l'état de celui qui écrit (S10, S37).
        dit += " Relevé d'un cran — davantage de textes qui résistent sont affichés."
    return dit


# --- Les couples ---------------------------------------------------------------------------------


def _trouver(
    couples: Sequence[Feasibility], plan: str, matiere: str | None
) -> Feasibility | None:
    for couple in couples:
        if couple.plan_source == plan and (
            matiere is None or couple.subject_matter == matiere
        ):
            return couple
    return None


def _avec_refus(tete: str, refuses: Sequence[Feasibility]) -> str:
    """Les impossibles s'affichent **avec** les possibles — signalés, jamais fabriqués."""
    if not refuses:
        return tete
    dits = " · ".join(
        f"{couple.plan_source} x {couple.subject_matter} ({couple.refusal_reason})"
        for couple in refuses
    )
    return f"{tete} Écartées : {dits}."


def _option(couple: Feasibility) -> Option:
    return Option(
        code=f"{couple.plan_source}:{couple.subject_matter}",
        label=f"{couple.plan_source} x {couple.subject_matter}",
        rationale=f"Risque de proof-texting : {couple.proof_text_risk}.",
        origin="curation",
    )
