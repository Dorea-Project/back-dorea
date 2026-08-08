"""Étage 4 — **le contexte : sourcé, ou absent**.

Le plus court étage du moteur, et sa règle tient en trois mots. Il n'y a pas de troisième
possibilité : ni contexte reconstitué, ni contexte plausible, ni « on suppose que ». Une unité
sans note relue n'affiche **rien**.

C'est la même discipline que partout ailleurs — `reviewed_by NOT NULL`, `rationale` jamais vide,
`segment_refs` non vide. **Rien plutôt qu'une vraisemblance.** Un contexte historique inventé est
exactement le genre d'erreur qu'un pasteur répète en chaire avec assurance, parce qu'elle avait
l'air documentée.

Il ne rend jamais la main : le contexte informe, il n'arbitre rien.

Deux natures, dites avant la note : l'**historique** situe, le **littéraire** explique la
construction. Table `urim_corpus_context_note` — définie le 2026-08-06 (S40), après que cet étage
eut été écrit contre un port dont rien ne fixait la forme.
"""

from __future__ import annotations

from app.contexts.urim.engine.deps import EngineDeps
from app.contexts.urim.engine.errors import StagePrerequisiteError
from app.contexts.urim.engine.outcomes import Outcome, StageResult
from app.contexts.urim.engine.state import StudyState


class LoadContext:
    """Le cinquième étage. Il apporte ce qui a été relu, et se tait sur le reste."""

    code = "load_context"

    def applies(self, state: StudyState) -> bool:
        return state.bounds is not None

    def execute(self, state: StudyState, deps: EngineDeps) -> StageResult:
        if state.bounds is None:
            raise StagePrerequisiteError("le contexte exige un passage borné")

        if state.pericope_id is None:
            # Pas d'unité curée : rien de relu à lire. On le dit, et on avance. « Bornes
            # forcées » serait faux une fois sur deux — le pasteur n'a le plus souvent rien
            # forcé du tout, c'est le corpus qui n'avait rien à cet endroit.
            return StageResult(
                outcome=Outcome.CONTINUE,
                rationale="Bornes hors unité curée — aucun contexte relu sur ce passage.",
                state=state,
            )

        notes = list(deps.corpus.context_for(state.pericope_id))
        if not notes:
            return StageResult(
                outcome=Outcome.CONTINUE,
                rationale="Aucun contexte relu sur cette unité.",
                state=state,
            )

        # La nature est dite avant la note : l'historique situe, le littéraire explique la
        # construction — et le pasteur ne les lit pas au même moment.
        dit = " · ".join(
            f"{note.kind} — {note.body} ({note.source_ref})" for note in notes
        )
        return StageResult(
            outcome=Outcome.CONTINUE,
            rationale=f"Contexte : {dit}",
            state=state,
        )
