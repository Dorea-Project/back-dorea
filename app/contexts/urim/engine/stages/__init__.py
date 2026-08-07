"""Les huit étages du moteur, un fichier par étage, dans l'ordre de la spec §2.

Un étage est **pur** : il lit un état, consulte la bordure (`deps`), rend un `StageResult`
motivé. Il ne mute rien, n'écrit nulle part, et n'a pas le droit de lire `deps.context`.
"""

from app.contexts.urim.engine.stages.bear_axes import BearAxes
from app.contexts.urim.engine.stages.bound_pericope import BoundPericope
from app.contexts.urim.engine.stages.load_context import LoadContext
from app.contexts.urim.engine.stages.propose_theme import ProposeTheme
from app.contexts.urim.engine.stages.resolve_passage import ResolvePassage
from app.contexts.urim.engine.stages.route_entry import RouteEntry
from app.contexts.urim.engine.stages.serve_corpus import ServeCorpus
from app.contexts.urim.engine.stages.shape_homiletic import ShapeHomiletic

__all__ = [
    "BearAxes",
    "BoundPericope",
    "LoadContext",
    "ProposeTheme",
    "ResolvePassage",
    "RouteEntry",
    "ServeCorpus",
    "ShapeHomiletic",
]
