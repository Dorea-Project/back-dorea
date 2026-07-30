"""Interpreter `JOINED_GROUP` — **regarder celui qui n'est pas encore venu**.

Jusqu'ici, seule une présence armait la détection d'absence. La conséquence était silencieuse et
mauvaise : le nouveau inscrit qu'on ne revoit jamais restait invisible. Il n'avait pas de première
présence, donc pas d'échéance, donc aucun regard — alors que c'est exactement la personne qu'il
fallait voir. Le silence de quelqu'un qui n'est jamais venu est le plus difficile à entendre, parce
qu'il ne succède à rien.

**Entrer dans un groupe est un acte, pas une omission.** Le fait décrit ce que quelqu'un a fait —
ou ce qu'un responsable a fait pour lui en l'inscrivant — et le contrat du moteur reste intact :
rien ici ne dit qu'une personne n'est pas venue.

Il n'ouvre **aucun cas**. Arriver dans un groupe n'est pas un motif de soin : c'est le moment où
l'on commence à attendre quelqu'un. Le premier regard tombera au rythme du groupe, et c'est lui,
éventuellement, qui ouvrira.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from app.contexts.watch.application.interpretation import WatchStateView
from app.contexts.watch.application.interpreters.absence_watch import arm_absence_watch
from app.contexts.watch.domain.effects import ProposedEffect
from app.contexts.watch.domain.facts import Fact, FactKind

_GENESIS = datetime(2026, 1, 1, tzinfo=UTC)


class JoinedGroupV1:
    kind = FactKind.JOINED_GROUP
    version = 1
    effective_from = _GENESIS

    def interpret(self, fact: Fact, state: WatchStateView) -> Sequence[ProposedEffect]:
        return arm_absence_watch(
            fact, reason="Vient d'entrer dans le groupe — regarder si elle y vient."
        )
