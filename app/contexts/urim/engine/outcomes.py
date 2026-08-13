"""Ce qu'un étage a le droit de dire — et le motif qui l'accompagne **toujours**.

Quatre issues, pas plus. La décision humaine (`AWAIT`) est une issue **normale** du moteur,
pas une exception : le moteur s'arrête et rend la main. Le repli (`DEGRADE`) ne coupe jamais
le pipeline — aucun mur un vendredi soir.

`rationale` n'est pas facultatif. C'est la traduction, dans le code, de `reviewed_by NOT NULL`
dans la base : aucun étage ne produit un résultat sans énoncer pourquoi.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from app.contexts.urim.engine.errors import EngineInvariantError
from app.contexts.urim.engine.state import StudyState


class Outcome(StrEnum):
    CONTINUE = "continue"  # l'étage suivant s'exécute
    AWAIT = "await_decision"  # le pasteur doit trancher
    REFUSE = "refuse"  # motivé, définitif pour ce couple
    DEGRADE = "degrade"  # repli, la préparation continue


@dataclass(frozen=True, slots=True)
class Option:
    """Une proposition soumise au pasteur quand le moteur rend la main (`AWAIT`)."""

    code: str
    label: str
    rationale: str  # pourquoi cette option est proposée

    #: ⚠️ **D'où vient cette proposition** — parce que deux options côte à côte ne valent pas
    #: la même chose.
    #:
    #: « Jean 5:42 partage 1 des mots rares de la saisie » et « Parabole du bon Samaritain,
    #: illustrant qui est notre prochain » arrivaient dans la même liste, avec la même
    #: apparence. La première est trouvée sur des mots, la seconde sur le sens ; les présenter
    #: identiques laisse le pasteur croire qu'elles ont été trouvées de la même façon.
    #:
    #: Le client peut ainsi les grouper — *trouvés dans vos mots* / *traitent votre sujet* —
    #: sans avoir à deviner la provenance depuis la forme du motif.
    origin: str = "moteur"

    #: ⚠️ **Ce que le texte fait de l'axe** — `dominant`, `porte`, `resiste`, ou `None`.
    #:
    #: 🔴 L'information existait et voyageait **collée dans le libellé** : « La charité sans
    #: hypocrisie — en fait son sujet ». Le client qui veut séparer *en fait son sujet* de *le
    #: soutient* devait donc lire le texte du libellé, ce qui marche jusqu'au jour où la
    #: formulation change. C'est le trou 1 de `docs/Urim_Conversation.md`.
    #:
    #: `None` n'est pas un défaut : une option de bornage ou une correction d'entrée ne pèse
    #: aucun axe, et le vocabulaire reste celui du corpus — le même mot que `BearingView`,
    #: jamais un synonyme.
    strength: str | None = None


@dataclass(frozen=True, slots=True)
class StageResult:
    outcome: Outcome
    rationale: str  # JAMAIS vide — invariant vérifié
    state: StudyState
    options: tuple[Option, ...] = field(default=())

    def __post_init__(self) -> None:
        if not self.rationale.strip():
            raise EngineInvariantError("un étage ne rend rien sans motif")
        if self.outcome is Outcome.AWAIT and not self.options:
            raise EngineInvariantError("AWAIT sans options à proposer")

    @property
    def halts(self) -> bool:
        """Le moteur rend la main au pasteur (décision attendue, ou refus motivé)."""
        return self.outcome in (Outcome.AWAIT, Outcome.REFUSE)
