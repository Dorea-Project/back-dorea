"""Interpreter des **gestes du responsable** — ce qu'un humain a fait sur un cas.

Le journal ne contenait que ce que les sources disent du monde. Ce qu'un responsable *faisait* —
ouvrir un cas, le fermer avec une issue — vivait uniquement sur la projection, donc une
reprojection l'effaçait sans pouvoir le reconstruire. On perdait les issues qu'il avait conclues,
le premier regard, la chaîne d'épisode qui évite de rappeler quelqu'un en repartant de zéro : très
exactement la trace du soin apporté, au nom de la réparation.

**Le geste vise la personne, pas un identifiant de cas.** Un rejeu recrée les cas avec de nouveaux
identifiants ; un effet qui pointerait vers l'ancien ne retrouverait rien. Il y a au plus un cas
vivant par personne — c'est un invariant de l'arbitrage — et c'est celui-là qu'on vise. Le
`signal_id` voyage quand même dans le payload : il ne sert pas à retrouver le cas, il sert à
raconter lequel a été fermé, ce jour-là.

**L'interpreter ne rejoue aucune règle.** Il ne vérifie ni l'autorité (faite à l'émission, par
`_OwnedCase`), ni la légitimité de la transition : c'est l'agrégat `Signal` qui refuse tout seul
une clôture sans humain, une issue absorbante déjà posée, une transition qui n'existe pas.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

from app.contexts.watch.application.interpretation import WatchStateView
from app.contexts.watch.domain.contact import HARD_EXPIRY_ATTEMPTS, ContactResult
from app.contexts.watch.domain.effects import (
    CasePriority,
    Extinguish,
    ExtinguishCause,
    MarkCaseSeen,
    ProposedEffect,
    RecordContactAttempt,
    ResolveCase,
    ResolveContactAttempt,
)
from app.contexts.watch.domain.facts import Fact, FactKind

_GENESIS = datetime(2026, 1, 1, tzinfo=UTC)


def _actor(fact: Fact) -> UUID:
    return UUID(str(fact.payload["actor_account_id"]))


class CaseSeenV1:
    kind = FactKind.CASE_SEEN
    version = 1
    effective_from = _GENESIS

    def interpret(self, fact: Fact, state: WatchStateView) -> Sequence[ProposedEffect]:
        return [
            MarkCaseSeen(
                subject_id=fact.subject_id,
                reason="Le cas a été ouvert par son destinataire.",
                at=fact.occurred_at,
                by_account_id=_actor(fact),
            )
        ]


class CaseClosedV1:
    kind = FactKind.CASE_CLOSED
    version = 1
    effective_from = _GENESIS

    def interpret(self, fact: Fact, state: WatchStateView) -> Sequence[ProposedEffect]:
        return [
            ResolveCase(
                subject_id=fact.subject_id,
                reason="Le cas a été fermé, avec une issue choisie.",
                at=fact.occurred_at,
                by_account_id=_actor(fact),
                outcome=str(fact.payload["outcome"]),
            )
        ]


class ContactAttemptedV1:
    """L'effort, écrit **avant** que l'application perde la main.

    On sort vers WhatsApp ou le téléphone, et on ne revient pas toujours. Sans cette trace posée au
    départ, le produit conclurait à un échec de veille là où il y a eu un appel de vingt minutes —
    le pire des faux négatifs, celui qui invalide un succès réel."""

    kind = FactKind.CONTACT_ATTEMPTED
    version = 1
    effective_from = _GENESIS

    def interpret(self, fact: Fact, state: WatchStateView) -> Sequence[ProposedEffect]:
        return [
            RecordContactAttempt(
                subject_id=fact.subject_id,
                reason="Un contact a été tenté.",
                attempt_id=UUID(str(fact.payload["attempt_id"])),
                channel=str(fact.payload["channel"]),
                at=fact.occurred_at,
                by_account_id=_actor(fact),
            )
        ]


class ContactAnsweredV1:
    """Ce que le responsable rapporte de son appel — et, le cas échéant, la **péremption dure**.

    Trois tentatives sans réponse sur un régime d'échéance : le cas sort de la file. Ce n'est pas
    un renoncement, c'est une question de volume — sans elle, un module d'évangélisation qui
    fonctionne noie son propre inviteur en trois semaines. La personne reste en base ; elle sort de
    la file, pas du fichier.

    Le décompte et l'origine du cas voyagent dans le payload, écrits au moment où on les connaît :
    l'interpreter reste pur, et un rejeu conclut la même chose qu'au premier jour."""

    kind = FactKind.CONTACT_ANSWERED
    version = 1
    effective_from = _GENESIS

    def interpret(self, fact: Fact, state: WatchStateView) -> Sequence[ProposedEffect]:
        result = str(fact.payload["result"])
        effects: list[ProposedEffect] = [
            ResolveContactAttempt(
                subject_id=fact.subject_id,
                reason="Le responsable a dit ce qui s'est passé.",
                attempt_id=UUID(str(fact.payload["attempt_id"])),
                result=result,
                at=fact.occurred_at,
                commitment=fact.payload.get("commitment"),
            )
        ]
        if self._expires(fact, result):
            effects.append(
                Extinguish(
                    subject_id=fact.subject_id,
                    reason="Resté sans réponse après trois tentatives.",
                    cause=ExtinguishCause.UNREACHABLE,
                    at=fact.occurred_at,
                )
            )
        return effects

    def _expires(self, fact: Fact, result: str) -> bool:
        if result != ContactResult.NOT_REACHED.value:
            return False
        if fact.payload.get("origin") != CasePriority.DEADLINE.value:
            return False
        return int(fact.payload.get("failed_attempts") or 0) >= HARD_EXPIRY_ATTEMPTS
