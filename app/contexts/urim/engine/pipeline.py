"""La boucle — un état, des étages purs, et la main qui revient au pasteur.

`run` est **pure** : aucune écriture en base, aucun appel réseau, aucune horloge (elle est
dans `deps`). Le moteur enchaîne les étages dans l'ordre, accumule les motifs dans la trace,
et s'arrête dès qu'un étage rend la main (`AWAIT` : le pasteur tranche · `REFUSE` : motivé,
définitif pour ce couple). `DEGRADE` ne coupe jamais.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from app.contexts.urim.engine.deps import Decision, EngineDeps
from app.contexts.urim.engine.outcomes import StageResult
from app.contexts.urim.engine.stage import Stage
from app.contexts.urim.engine.stages.bear_axes import BearAxes
from app.contexts.urim.engine.stages.bound_pericope import BoundPericope
from app.contexts.urim.engine.stages.load_context import LoadContext
from app.contexts.urim.engine.stages.propose_theme import ProposeTheme
from app.contexts.urim.engine.stages.resolve_passage import ResolvePassage
from app.contexts.urim.engine.stages.route_entry import RouteEntry
from app.contexts.urim.engine.stages.serve_corpus import ServeCorpus
from app.contexts.urim.engine.stages.shape_homiletic import ShapeHomiletic
from app.contexts.urim.engine.stages.weigh_conviction import WeighConviction
from app.contexts.urim.engine.state import StudyState, TraceEntry

#: **Les huit étages de la spec (§2), plus le chemin inversé.**
#:
#:     RouteEntry()        0     — détecteur d'entrée : la saisie ne fait pas foi
#:     WeighConviction()   1-bis — d'une intention vers un texte (§7) ; conviction seulement
#:     ResolvePassage()    1     — identifier le passage, pas la version
#:     BoundPericope()     2     — unité littéraire + motif
#:     ServeCorpus()       3     — la version servie, et le seul repli du moteur
#:     LoadContext()       4     — sourcé, ou absent
#:     BearAxes()          5     — porté / résistant / absent + mises en garde
#:     ShapeHomiletic()    6     — couple plan x matière, refus motivé
#:     ProposeTheme()      7     — une proposition, jamais un titre
#:
#: ⚠️ **Neuf entrées, huit étages.** `WeighConviction` n'est pas un neuvième palier : c'est
#: l'**alternative** à l'étage 1, pas sa suite. L'un part d'un passage et cherche ce qu'il
#: porte ; l'autre part d'une intention et cherche quel texte la porte. Les deux se rejoignent
#: au bornage, et **aucun étage aval ne sait par où c'est entré** — c'est ce qui permet au
#: chemin inversé de n'ajouter aucune condition ailleurs.
#:
#: **Les tests d'architecture ne sont plus vrais par vacuité.** Ils itèrent des étages réels :
#: le déterminisme, le motif obligatoire et l'interdit `deps.context` portent désormais sur tout
#: le pipeline, plus seulement sur l'étage-témoin fautif qui les accompagne.
PIPELINE: Final[tuple[Stage, ...]] = (
    RouteEntry(),
    # Le **chemin inversé** (§7) : il ne s'applique qu'à la conviction, et il s'efface dès
    # qu'un texte est retenu. Placé avant l'étage 1 parce qu'il en est l'alternative, pas la
    # suite : l'un part d'un passage, l'autre y arrive.
    WeighConviction(),
    ResolvePassage(),
    BoundPericope(),
    ServeCorpus(),
    LoadContext(),
    BearAxes(),
    ShapeHomiletic(),
    ProposeTheme(),
)


@dataclass(frozen=True, slots=True)
class EngineRun:
    state: StudyState
    results: tuple[StageResult, ...]

    @property
    def halted(self) -> bool:
        """Le moteur a rendu la main (dernier étage `AWAIT` ou `REFUSE`)."""
        return bool(self.results) and self.results[-1].halts


class UrimEngine:
    def __init__(self, deps: EngineDeps, pipeline: tuple[Stage, ...] = PIPELINE) -> None:
        self._deps, self._pipeline = deps, pipeline

    def run(self, state: StudyState) -> EngineRun:
        results: list[StageResult] = []
        for stage in self._pipeline:
            if not stage.applies(state):
                continue
            result = stage.execute(state, self._deps)
            results.append(result)
            state = result.state.with_(
                trace=(*state.trace, TraceEntry(stage.code, result.rationale))
            )
            if result.halts:
                break  # la main revient au pasteur
        return EngineRun(state=state, results=tuple(results))

    def resume(self, state: StudyState, decision: Decision) -> EngineRun:
        """Reprise après `AWAIT` : la décision entre dans l'état, le pipeline repart."""
        return self.run(decision.apply_to(state))
