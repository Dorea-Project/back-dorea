"""`UrimEngine` — pipeline déterministe à étages (spec §1).

Trois propriétés non négociables :

- **Déterminisme** — mêmes entrées + même `corpus_snapshot` ⇒ même sortie, bit pour bit.
- **Motif obligatoire** — aucun étage ne rend un résultat sans énoncer pourquoi.
- **La décision humaine est un état, pas une erreur** — `AWAIT` est une issue normale.

Ce paquet est **pur** : ni I/O, ni horloge, ni session. Toute la bordure passe par `EngineDeps`.
"""

from app.contexts.urim.engine.deps import (
    AxisBearing,
    CitationCandidate,
    ContextNote,
    Decision,
    EngineDeps,
    Feasibility,
    PericopeView,
    ReferenceCheck,
    ReferenceSpan,
)
from app.contexts.urim.engine.errors import (
    EngineError,
    EngineInvariantError,
    StagePrerequisiteError,
)
from app.contexts.urim.engine.normalizer import normalize, tokens
from app.contexts.urim.engine.outcomes import Option, Outcome, StageResult
from app.contexts.urim.engine.pipeline import PIPELINE, EngineRun, UrimEngine
from app.contexts.urim.engine.stage import Stage
from app.contexts.urim.engine.stages import (
    BearAxes,
    BoundPericope,
    LoadContext,
    ProposeTheme,
    ResolvePassage,
    RouteEntry,
    ServeCorpus,
    ShapeHomiletic,
)
from app.contexts.urim.engine.state import (
    Bounds,
    EntryMode,
    EntryOrigin,
    Reference,
    StudyState,
    TraceEntry,
)

__all__ = [
    "PIPELINE",
    "AxisBearing",
    "BearAxes",
    "BoundPericope",
    "Bounds",
    "CitationCandidate",
    "ContextNote",
    "Decision",
    "EngineDeps",
    "EngineError",
    "EngineInvariantError",
    "EngineRun",
    "EntryMode",
    "EntryOrigin",
    "Feasibility",
    "LoadContext",
    "Option",
    "Outcome",
    "PericopeView",
    "ProposeTheme",
    "Reference",
    "ReferenceCheck",
    "ReferenceSpan",
    "ResolvePassage",
    "RouteEntry",
    "ServeCorpus",
    "ShapeHomiletic",
    "Stage",
    "StagePrerequisiteError",
    "StageResult",
    "StudyState",
    "TraceEntry",
    "UrimEngine",
    "normalize",
    "tokens",
]
