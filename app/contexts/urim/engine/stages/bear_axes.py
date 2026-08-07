"""Étage 5 — **les axes portés**, et surtout ceux qui résistent.

C'est l'étage qui porte l'argument du produit. Retirez-lui une seule ligne — celle qui fait
remonter les pesées `resiste` **au même rang** que les portantes — et Urim devient un moteur de
proof-texting avec de meilleures manières.

## Quatre forces, et deux d'entre elles sont opposées

| valeur | ce que le texte fait de cet axe |
| :-- | :-- |
| `dominant` | il en est le sujet |
| `porte` | il le soutient |
| **`resiste`** | il le **complique ou le contredit** |
| `absent` | il n'en dit rien |

`absent` et `resiste` ne sont pas voisins : **ne rien dire n'est pas résister**. C'est la valeur
qui manquait au schéma d'origine, et sans elle le mode conviction était inconstructible.

Un axe `absent` n'affiche **rien**, et aucun plan ne se construit dessus. Un axe `resiste`
s'affiche — c'est même ce qu'il faut lire en premier quand on est sûr de soi.

## Ce que cet étage ne fait pas

**Il ne pondère pas.** Les pesées viennent curées, sourcées et relues (`reviewed_by NOT NULL`).
L'étage les range ; il ne les juge pas, et il n'en fabrique aucune.

**Il ne choisit pas à la place du pasteur.** Plusieurs axes dominants ⇒ il rend la main avec
chacun **motivé**, au même rang. Ordonner reviendrait à interpréter ce qu'il a en tête (S10).

**Il ne devine rien hors du corpus curé.** Sans unité retenue — le pasteur a forcé ses bornes —
il n'y a aucune pesée relue à lire. `DEGRADE`, et le motif dit ce qui manque : *on ne devine pas
une doctrine que personne n'a relue.*

## Les mises en garde s'affichent toujours

D-F : y compris quand la tradition de l'église est inconnue. La formulation le rend possible —
« ici les traditions divergent », jamais « votre tradition dit X ». Une unité sans caveat
n'affiche rien ; le vide est un état normal, jamais une improvisation.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.contexts.urim.engine.deps import AxisBearing, EngineDeps
from app.contexts.urim.engine.errors import StagePrerequisiteError
from app.contexts.urim.engine.outcomes import Option, Outcome, StageResult
from app.contexts.urim.engine.state import StudyState

DOMINANT = "dominant"
PORTE = "porte"
RESISTE = "resiste"
ABSENT = "absent"


class BearAxes:
    """Le sixième étage. Il montre ce que le texte porte — **et ce à quoi il résiste**."""

    code = "bear_axes"

    def applies(self, state: StudyState) -> bool:
        return state.bounds is not None and state.axis is None

    def execute(self, state: StudyState, deps: EngineDeps) -> StageResult:
        if state.bounds is None:
            raise StagePrerequisiteError("les axes exigent un passage borné")

        if state.pericope_id is None:
            # S22 rendu mécanique : sans unité curée, il n'y a rien de relu à lire. On ne devine
            # pas une pesée doctrinale — c'est exactement ce que `reviewed_by NOT NULL` interdit.
            return StageResult(
                outcome=Outcome.DEGRADE,
                rationale=(
                    "Bornes hors unité curée — aucune pesée doctrinale relue sur ce passage, "
                    "et aucune mise en garde. La préparation continue."
                ),
                state=state,
            )

        pesees = list(deps.doctrine.bearings(state.pericope_id))
        if not pesees:
            # **Aucune ligne n'est pas la même chose qu'une ligne `absent`.**
            #
            #     absente  →  personne n'a encore regardé
            #     absent   →  quelqu'un a regardé, et le texte n'en dit rien
            #
            # Ce sont des choses opposées, et le moteur mentirait en les confondant : il
            # affirmerait avec assurance qu'un texte ne porte pas un axe que personne n'a
            # examiné. C'est le seul endroit du produit où le silence porte une information —
            # partout ailleurs il n'est rien — et c'est pour ça qu'il faut le saisir.
            return StageResult(
                outcome=Outcome.DEGRADE,
                rationale=(
                    "Aucune pesée doctrinale n'a encore été relue sur cette unité. "
                    "La préparation continue, sans axe proposé."
                ),
                state=state,
            )

        resistants = [pesee for pesee in pesees if pesee.strength == RESISTE]
        mises_en_garde = list(deps.doctrine.caveats(state.pericope_id))

        dominants = [pesee for pesee in pesees if pesee.strength == DOMINANT]
        if len(dominants) == 1:
            (seul,) = dominants
            return StageResult(
                outcome=Outcome.CONTINUE,
                rationale=_motif(f"Axe dominant : {seul.label}. {seul.rationale}",
                                 resistants, mises_en_garde),
                state=state.with_(axis=seul.axis_code),
            )

        if dominants:
            # Plusieurs axes dominants : on les rend **au même rang**, chacun motivé. Les ordonner
            # serait décider ce que le pasteur veut prêcher.
            return StageResult(
                outcome=Outcome.AWAIT,
                rationale=_motif(
                    f"{len(dominants)} axes dominent ce texte, au même rang.",
                    resistants, mises_en_garde,
                ),
                state=state,
                options=tuple(_option(pesee) for pesee in dominants),
            )

        portants = [pesee for pesee in pesees if pesee.strength == PORTE]
        if portants:
            return StageResult(
                outcome=Outcome.AWAIT,
                rationale=_motif(
                    "Aucun axe ne domine ce texte ; voici ceux qu'il porte.",
                    resistants, mises_en_garde,
                ),
                state=state,
                options=tuple(_option(pesee) for pesee in portants),
            )

        # Ni dominant, ni porté, **mais des lignes relues** : le texte a été examiné et ne porte
        # aucun des dix loci. C'est une information — et elle n'a de valeur que parce qu'on la
        # distingue du cas précédent. Les résistants, eux, s'affichent quand même.
        return StageResult(
            outcome=Outcome.DEGRADE,
            rationale=_motif(
                "Cette unité a été relue et ne porte aucun des dix axes doctrinaux.",
                resistants, mises_en_garde,
            ),
            state=state,
        )


# --- Le motif, et ce qu'il transporte toujours --------------------------------------------------


def _motif(
    tete: str, resistants: Sequence[AxisBearing], mises_en_garde: Sequence[str]
) -> str:
    """La phrase de l'étage — **avec les résistants et les mises en garde, quoi qu'il arrive**.

    Ils voyagent dans *tous* les cas : quand un axe domine, quand plusieurs se disputent, et même
    quand le texte ne porte rien. C'est le seul endroit du moteur où une information s'ajoute sans
    condition, et c'est délibéré — un pasteur sûr de son axe est précisément celui qui a le plus
    besoin de lire ce qui lui résiste."""
    morceaux = [tete]
    if resistants:
        resiste = " · ".join(f"{p.label} ({p.rationale})" for p in resistants)
        morceaux.append(f"**Ce texte résiste à** : {resiste}.")
    if mises_en_garde:
        morceaux.append(f"Mises en garde : {' · '.join(mises_en_garde)}.")
    return " ".join(morceaux)


def _option(pesee: AxisBearing) -> Option:
    return Option(code=pesee.axis_code, label=pesee.label, rationale=pesee.rationale)
