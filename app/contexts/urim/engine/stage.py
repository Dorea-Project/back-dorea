"""Le contrat d'un étage — pur, ordonné, motivé.

Un étage lit un état, consulte la bordure (`deps`), et rend un `StageResult`. Il ne mute rien,
n'écrit nulle part, et **n'a pas le droit de lire `deps.context`** (cf. `deps.py`).

L'ordre du pipeline est contraignant : un étage dont les prérequis manquent lève
`StagePrerequisiteError` plutôt que de travailler sur un état incomplet.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.contexts.urim.engine.deps import EngineDeps
from app.contexts.urim.engine.outcomes import StageResult
from app.contexts.urim.engine.state import StudyState


@runtime_checkable
class Stage(Protocol):
    code: str

    def applies(self, state: StudyState) -> bool:
        """Cet étage a-t-il quelque chose à faire sur cet état ?"""
        ...

    def execute(self, state: StudyState, deps: EngineDeps) -> StageResult:
        """Le travail de l'étage — pur. Rend **toujours** un motif."""
        ...
