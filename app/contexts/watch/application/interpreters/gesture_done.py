"""Interpreter `GESTURE_DONE` — **le soin qui a eu lieu**, enfin branché.

Comme pour le signe de vie, tout le mécanisme existait et n'avait aucun émetteur :
`Signal.record_gesture()` sans appelant, `gestures_count` figé à zéro, et un garde de reprojection
qui protégeait des gestes que rien n'écrivait. Ce fichier est le chaînon.

**Ce qu'un geste fait.** Il **enrichit** le cas et le fait descendre sous ceux dont personne n'a de
nouvelles. Le responsable lit alors *« Sans nouvelles — 3 rencontres de la cellule Bethel. Quelqu'un
de l'église lui a rendu visite le 3 août. »* et il sait deux choses avant de décrocher : que la
personne n'est pas seule, et qu'il peut fermer sur *« on sait, quelqu'un s'en occupe déjà »* — une
issue qui existe depuis le début et que rien ne lui permettait de choisir en connaissance de cause.

C'est **là** que la calibration bascule. La même situation se rangeait jusqu'ici en
« j'ai pris contact, tout allait bien », c'est-à-dire la seule issue du vocabulaire qui dise *la
détection s'est trompée* — et la boucle froide proposait donc de regarder moins, d'autant plus fort
que l'église se soignait bien elle-même.

**Ce qu'un geste ne fait pas, et c'est plus important.**

Il n'ouvre rien : sans cas vivant, il ne se passe rien du tout. Déclarer qu'on est passé voir
quelqu'un ne doit jamais le faire entrer en veille — sinon prendre des nouvelles fiche la personne,
et le canal se retournerait contre ce pour quoi il existe. Le fait reste au ledger, il n'en sort
aucun effet.

Il n'éteint rien, il ne rétracte rien. C'est pourquoi il pose `gesture=True` et **pas**
`life_sign=True` : un signe de vie est la personne qui parle d'elle-même et peut faire disparaître
un cas que personne n'avait lu ; un geste est quelqu'un d'autre qui rapporte ce qu'il a fait. Ce
que Jean a constaté chez Sondet n'est pas ce que Sondet dit de lui-même, et un tiers qui pourrait
éteindre un cas le ferait taire avec sa propre impression.

**Il ne descend pas plus bas que le plancher.** Sur un cas d'absence — déjà la priorité la moins
urgente — la descente est un non-événement, et c'est voulu : ce qui libère la place du responsable
n'est pas un rang recalculé, c'est lui qui referme le cas en sachant. Sur une inquiétude ou une
annonce, en revanche, elle veut dire quelque chose : quelqu'un y est allé, ça passe après ceux vers
qui personne n'est allé.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from app.contexts.watch.application.interpretation import WatchStateView
from app.contexts.watch.domain.effects import CasePriority, EnrichCase, ProposedEffect
from app.contexts.watch.domain.facts import Fact, FactKind
from app.contexts.watch.domain.gesture import GESTURE_LABELS, GestureKind
from app.contexts.watch.domain.signal import spoken_date

_GENESIS = datetime(2026, 1, 1, tzinfo=UTC)


class GestureDoneV1:
    kind = FactKind.GESTURE_DONE
    version = 1
    effective_from = _GENESIS

    def interpret(self, fact: Fact, state: WatchStateView) -> Sequence[ProposedEffect]:
        case = state.case_of(fact.subject_id)
        if case is None:
            # Rien à enrichir, et surtout rien à ouvrir. Quelqu'un a pris soin de quelqu'un qui
            # n'était pas en veille : c'est une bonne nouvelle, pas un événement de veille.
            return []

        gesture = GestureKind(fact.payload["kind"])
        annotation = f"{GESTURE_LABELS[gesture]} le {spoken_date(fact.occurred_at)}."

        # **Ce qu'elle a demandé passe avant ce qu'on a fait pour elle.** Même garde que pour la
        # reconnaissance déposée : un cas né de sa propre parole ne redescend pas parce qu'un tiers
        # est passé. Quelqu'un qui demande un appel *et* reçoit une visite a toujours demandé un
        # appel — et le produit existe pour l'entendre.
        asked_for_it = CasePriority(case.origin) is CasePriority.DECLARED
        return [
            EnrichCase(
                subject_id=fact.subject_id,
                reason="Quelqu'un de l'église a pris de ses nouvelles.",
                origin=CasePriority.ABSENCE,
                annotation=annotation,
                priority=None if asked_for_it else CasePriority.ABSENCE,
                downgrade=not asked_for_it,
                # Compté sur le cas, jamais sur celui qui l'a posé : un compteur par personne
                # deviendrait un classement des bons et des mauvais frères.
                gesture=True,
                at=fact.occurred_at,
            )
        ]
