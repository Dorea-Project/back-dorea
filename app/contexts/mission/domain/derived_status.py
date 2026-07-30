"""`SeekerStatus` **dérivé** — il ne se remplace pas, il se scinde.

Il confondait deux choses qui ont chacune déjà un propriétaire :

| Ce qu'il exprimait | Vrai propriétaire |
|---|---|
| `ACCEPTED → INTEGRATED` — **où en est la personne** | `MembershipStatus` (IAM) |
| `ACCOMPANIED → CLOSED` — **où en est le cas** | `Signal` (watch) |

Rien à construire pour le remplacer : les deux existent. `Seeker` garde ce qu'il est **seul** à
savoir — la provenance : quel lien, quel inviteur, quand accepté. Un enregistrement de
provenance, pas un cycle de vie.

Cette fonction est **pure** et n'écrit rien. C'est ce qui garantit qu'il n'y a plus qu'une seule
machine à états : la valeur exposée par l'API est calculée à la lecture, jamais stockée en
parallèle. Deux machines écrites « le temps de migrer » divergent pendant la fenêtre — c'est-à-dire
qu'on aggrave temporairement le problème qu'on corrige, et une fenêtre de migration s'étire
toujours.
"""

from __future__ import annotations

from app.contexts.mission.domain.enums import SeekerStatus
from app.contexts.watch.domain.signal import SignalStatus


def derive_seeker_status(seeker, case) -> SeekerStatus:
    """L'état d'un chercheur, lu depuis ses deux vrais propriétaires.

    `case` est le cas **vivant** de la personne, ou None. L'ordre des tests compte :

    - devenu membre → `INTEGRATED`, quoi qu'il arrive au cas ensuite ;
    - plus de cas vivant → le parcours est clos, **sans jugement** ;
    - contact engagé → quelqu'un a pris le relais ;
    - sinon → il a accepté, personne ne s'en occupe encore. C'est l'état à ne pas laisser durer.
    """
    if seeker.integrated_account_id is not None:
        return SeekerStatus.INTEGRATED
    if case is None or not case.is_live:
        return SeekerStatus.CLOSED
    if case.status is SignalStatus.IN_CONTACT:
        return SeekerStatus.ACCOMPANIED
    return SeekerStatus.ACCEPTED
