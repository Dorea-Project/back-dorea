"""Interpreter `GRATITUDE_DEPOSITED` — **le signe de vie**, enfin branché.

Tout le mécanisme existait : `EnrichCase(life_sign=True)`, la rétractation d'un cas encore retenu,
la baisse de priorité. Il n'avait aucun émetteur. Ce fichier est le chaînon, et il est court —
c'est le signe que le moteur avait été bien découpé.

**Ce qu'un signe de vie fait, et surtout ce qu'il ne fait pas.**

Il n'ouvre rien. Déposer une reconnaissance n'est pas un motif de soin : c'est le contraire.

Il n'éteint rien non plus, et il n'existe **aucune** cause de clôture « signe de vie » — un
invariant balaie l'enum pour que ça le reste. Déposer une reconnaissance prouve qu'on est vivant,
pas qu'on est revenu en cellule. Éteindre le cas là-dessus serait la même erreur que fermer un
deuil parce que la personne est venue au culte : confondre une présence avec un état.

Ce qu'il fait, donc : il **enrichit** le cas et en abaisse la priorité, pour que le responsable
lise *« absente depuis 4 semaines, a déposé un sujet de reconnaissance le 12 avril »* et comprenne
immédiatement de quoi il s'agit — au lieu d'ouvrir son appel par « je vois que tu n'es pas venue »
à quelqu'un qui vient précisément de donner de ses nouvelles.

**Une seule exception, et elle n'efface rien de ce qui a été vu.** Sur un cas encore `HELD` — que
personne n'avait lu, sur lequel aucune promesse n'avait été faite — l'arbitrage le rétracte. C'est
lui qui en décide, pas cet interpreter : la règle vaut pour tout signe de vie présent et futur, et
la tenir à un seul endroit est ce qui l'empêche de diverger.

**Le texte déposé ne remonte pas.** L'annotation dit qu'un sujet a été déposé et quand ; elle ne
cite pas ce qu'il contient. Une reconnaissance est adressée à Dieu, pas au responsable de cellule
— et un contenu intime qui réapparaît sur l'écran de quelqu'un d'autre est exactement la fuite que
le produit passe son temps à fermer.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from app.contexts.watch.application.interpretation import WatchStateView
from app.contexts.watch.domain.effects import (
    CasePriority,
    EnrichCase,
    ProposedEffect,
)
from app.contexts.watch.domain.facts import Fact, FactKind
from app.contexts.watch.domain.signal import spoken_date

_GENESIS = datetime(2026, 1, 1, tzinfo=UTC)


class GratitudeDepositedV1:
    kind = FactKind.GRATITUDE_DEPOSITED
    version = 1
    effective_from = _GENESIS

    def interpret(self, fact: Fact, state: WatchStateView) -> Sequence[ProposedEffect]:
        # Sans cas vivant, il n'y a rien à enrichir — et surtout rien à ouvrir. L'arbitrage
        # écarterait un `EnrichCase` orphelin, mais le dire ici évite d'écrire un effet qui ne
        # veut rien dire : quelqu'un qui va bien et rend grâce n'a produit aucun événement de
        # veille, et c'est très bien ainsi.
        if not state.has_open_case(fact.subject_id):
            return []
        return [
            EnrichCase(
                subject_id=fact.subject_id,
                reason="A déposé un sujet de reconnaissance.",
                origin=CasePriority.DECLARED,
                annotation=(
                    f"A déposé un sujet de reconnaissance le {spoken_date(fact.occurred_at)}."
                ),
                # **Abaisser, pas éteindre.** Le cas reste, le responsable rappellera — mais
                # après ceux dont personne n'a de nouvelles.
                priority=CasePriority.ABSENCE,
                downgrade=True,
                life_sign=True,
                at=fact.occurred_at,
            )
        ]
