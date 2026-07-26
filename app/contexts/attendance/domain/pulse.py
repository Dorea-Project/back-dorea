"""État de marche d'un membre — le cœur de M7-0 (règles lisibles, pas de boîte noire).

À partir de la suite chronologique de ses présences dans une cellule, on déduit un **état** :
`new` (pas assez d'historique) / `engaged` / `at_risk` (silence >= 3x son rythme) / `dormant`
(>= 6x). L'état `shared` (« actif ailleurs ») est **appliqué par la requête** (signal réseau du
compte global) — l'algorithme pur ne s'en occupe pas.

Le **rythme est personnel** : l'écart *médian* entre deux venues. Awa (chaque semaine) → 1 ;
Yao (une fois par mois) → ~4. « 3x son rythme » = 3 rencontres pour Awa, ~12 pour Yao.
"""

from __future__ import annotations

from enum import StrEnum
from statistics import median

AT_RISK_FACTOR = 3  # silence au-dela de 3x son rythme → à interpeller
DORMANT_FACTOR = 6  # silence au-dela de 6x son rythme → dormant
_MIN_GATHERINGS = 3  # en-deçà de 3 rencontres depuis son arrivée → « nouveau » (pas de vide)
_DEFAULT_RHYTHM = 1.0  # rythme par défaut si on ne peut pas l'estimer (< 2 venues)


class Outcome(StrEnum):
    PRESENT = "present"
    EXCUSED = "excused"  # a prévenu (M6-2) — ne compte pas comme un silence
    ABSENT = "absent"


class WalkState(StrEnum):
    NEW = "new"
    ENGAGED = "engaged"
    AT_RISK = "at_risk"  # « à interpeller »
    SHARED = "shared"  # actif ailleurs (appliqué par la requête)
    DORMANT = "dormant"


CARE_STATES = frozenset({WalkState.AT_RISK, WalkState.DORMANT})  # « à interpeller »


def compute_walk_state(outcomes: list[Outcome]) -> tuple[WalkState, int]:
    """Renvoie (état de base, silence concerné). `SHARED` est décidé en amont par la requête.

    `outcomes` : les résultats du membre sur les rencontres passées **depuis son arrivée**
    (l'appelant filtre par date d'adhésion → un nouveau membre a peu de rencontres → `new`)."""
    if len(outcomes) < _MIN_GATHERINGS:
        return WalkState.NEW, 0  # cellule/membre trop récent : on ne juge pas sur du vide

    present_idx = [i for i, o in enumerate(outcomes) if o is Outcome.PRESENT]
    if len(present_idx) >= 2:
        gaps = [present_idx[k + 1] - present_idx[k] for k in range(len(present_idx) - 1)]
        rhythm = max(1.0, median(gaps))
    else:
        rhythm = _DEFAULT_RHYTHM

    # Silence concerné = rencontres ABSENTES depuis la dernière venue (l'excusé ne compte pas).
    if present_idx:
        after_last = outcomes[present_idx[-1] + 1 :]
        concerning = sum(1 for o in after_last if o is Outcome.ABSENT)
    else:
        concerning = sum(1 for o in outcomes if o is Outcome.ABSENT)  # jamais venu depuis l'arrivée

    if concerning == 0:
        return WalkState.ENGAGED, 0
    if concerning >= DORMANT_FACTOR * rhythm:
        return WalkState.DORMANT, concerning
    if concerning >= AT_RISK_FACTOR * rhythm:
        return WalkState.AT_RISK, concerning
    return WalkState.ENGAGED, concerning
