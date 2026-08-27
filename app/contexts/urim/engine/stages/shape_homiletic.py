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
                ) + _clause_de_charge(state.risk_flags),
                state=state,
                # ⚠️ **Le risque relevé se lit ICI, à l'écran où le pasteur choisit.**
                #
                # 🔴 Il ne se lisait nulle part. La branche `CONTINUE` ci-dessous est la seule
                # qui appelait `_releve()`, et elle est **injoignable depuis l'API** : la
                # décision écrit `plan_source` *et* `subject_matter` d'un coup, si bien que
                # `applies()` — qui exige `subject_matter is None` — ne laisse plus jamais cet
                # étage s'exécuter. La promesse faite à l'écran des axes (« le risque sera
                # relevé sur la mise en forme ») n'était donc jamais tenue.
                options=tuple(_option(couple, state.risk_flags) for couple in faisables),
            )

        # ⚠️ **Ces deux branches sont la garde de l'étage, pas celle du produit.**
        #
        # Elles n'ont jamais été atteintes depuis l'API — voir plus haut — et c'est la bordure
        # qui valide désormais le couple reçu (`UrimStudyService._appliquer`). On les garde :
        # un étage qui reçoit un état incohérent doit le dire, et trois tests les tiennent.
        # Mais elles ne sont **pas** la protection du pasteur ; ne pas les confondre.
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
    """Les impossibles s'affichent **avec** les possibles — signalés, jamais fabriqués.

    🔴 **Illisible sur un téléphone, le 22/08/2026.** Quinze couples collés bout à bout, chacun
    traînant son motif entier, dans un seul paragraphe gris qui remplissait deux écrans. Et
    répétitif, ce qui est pire : *« ce passage ne porte aucun personnage nommé… »* revenait
    **trois fois**, une par forme de plan.

    La cause n'était pas la longueur, c'était la structure. **Le refus porte sur la matière,
    pas sur la forme du plan** : « biographique » est écarté pour la même raison qu'on
    l'aborde en textuel, en expositif ou en thématique. On groupe donc par motif, et on le dit
    une fois.

    ⚠️ **On ne touche pas au motif lui-même.** Il vient du relu — c'est la phrase d'un homme
    qui a lu ce passage. L'abréger serait réécrire son travail ; le regrouper ne fait que
    cesser de le répéter.

    Les retours à la ligne sont voulus : une liste se lit, un paragraphe de quinze parenthèses
    se saute."""
    if not refuses:
        return tete

    par_motif: dict[str, list[Feasibility]] = {}
    for couple in refuses:
        par_motif.setdefault(couple.refusal_reason, []).append(couple)

    lignes = []
    for motif in sorted(par_motif):
        groupe = par_motif[motif]
        matieres = sorted({c.subject_matter for c in groupe})
        plans = sorted({c.plan_source for c in groupe})

        # Une matière refusée sur **toutes** les formes ne se nomme qu'une fois : c'est la
        # matière qui ne tient pas, et le pasteur a besoin de le savoir comme ça.
        if len(matieres) == 1 and len(plans) > 1:
            cle = f"{matieres[0]} — quelle que soit la forme du plan"
        else:
            cle = " · ".join(f"{c.plan_source} x {c.subject_matter}" for c in groupe)
        lignes.append(f"• {cle} : {motif}")

    return tete + "\n\nÉcartées :\n" + "\n".join(lignes)


def _clause_de_charge(drapeaux: Sequence[str]) -> str:
    """Nomme **l'effet** du drapeau, jamais l'état de celui qui écrit (S10, S37).

    La même phrase qu'à l'écran des axes, et c'est voulu : elle y annonçait le relèvement, elle
    le constate ici. Deux formulations auraient laissé croire à deux mécanismes."""
    if not drapeaux:
        return ""
    return (
        " Formulation à forte charge : le risque de proof-texting est relevé d'un cran sur "
        "les mises en forme ci-dessous."
    )


def _option(couple: Feasibility, drapeaux: Sequence[str] = ()) -> Option:
    """⚠️ **Le risque porté par l'option est le risque relevé.**

    Le bloc `feasibility` continue d'afficher la curation telle quelle — c'est le panorama, et
    il ne doit pas bouger sous les pieds du relecteur. L'option, elle, est ce que le pasteur
    **choisit** : c'est là que la vigilance doit être lisible, au moment du geste."""
    risque = _releve(couple.proof_text_risk, drapeaux)
    releve = " (relevé d'un cran)" if risque != couple.proof_text_risk else ""
    return Option(
        code=f"{couple.plan_source}:{couple.subject_matter}",
        label=f"{couple.plan_source} x {couple.subject_matter}",
        rationale=f"Risque de proof-texting : {risque}{releve}.",
        origin="curation",
    )
