"""Interpreter `LIFE_EVENT_ANNOUNCED` — une annonce nommant quelqu'un devient un effet de veille.

Applique la table de décision (`role_rules`) au rôle porté par le fait. Le type d'annonce
n'apparaît nulle part ici : il a déjà fait son travail en amont, en proposant les rôles
plausibles au publicateur.

Trois règles portées à cet étage :
- **`EXIT` absorbe.** Dès qu'il est retenu, c'est le seul effet évalué — on ne neutralise pas
  quelqu'un qu'on vient de retirer de la veille, et on éteint ce qui courait sur lui.
- **Tout est daté de l'événement**, jamais de l'ingestion : une saisie tardive ne décale pas
  l'histoire de la personne.
- **Rien n'est décidé ici.** L'épisode est proposé même si le moteur ne sait pas encore le
  matérialiser : le fait est au ledger, la proposition sera honorée à la reprojection.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from app.contexts.watch.application.interpretation import WatchStateView
from app.contexts.watch.domain.effects import (
    CasePriority,
    ExcludeForever,
    ExclusionCause,
    Extinguish,
    ExtinguishCause,
    Neutralise,
    OpenCase,
    ProposedEffect,
)
from app.contexts.watch.domain.facts import Fact, FactKind
from app.contexts.watch.domain.role_rules import (
    SubjectRole,
    WatchEffect,
    episode_window,
    neutralization_window,
    resolve_effects,
)

_GENESIS = datetime(2026, 1, 1, tzinfo=UTC)


def _reason(role: SubjectRole, event_date: datetime) -> str:
    """La raison **en clair**, écrite une fois — jamais reconstruite à l'affichage."""
    return f"{role.value} annoncé le {event_date.date().isoformat()}"


class LifeEventAnnouncedV1:
    kind = FactKind.LIFE_EVENT_ANNOUNCED
    version = 1
    effective_from = _GENESIS

    def interpret(self, fact: Fact, state: WatchStateView) -> Sequence[ProposedEffect]:
        role = SubjectRole(fact.payload["role"])
        override = fact.payload.get("effects")
        effects = resolve_effects(
            role, tuple(WatchEffect(e) for e in override) if override else None
        )
        event_date = fact.occurred_at
        reason = _reason(role, event_date)
        proposed: list[ProposedEffect] = []

        if WatchEffect.EXIT in effects:
            # Terminal et prioritaire. On éteint d'abord tout ce qui courait sur la personne :
            # sans cela, une échéance continuerait de tourner sur un défunt.
            proposed.append(
                Extinguish(
                    subject_id=fact.subject_id,
                    reason=reason,
                    cause=ExtinguishCause.DECEASED,
                    at=fact.recorded_at,
                )
            )
            proposed.append(
                ExcludeForever(
                    subject_id=fact.subject_id,
                    reason=reason,
                    cause=ExclusionCause.DECEASED,
                    at=fact.recorded_at,
                )
            )
            return proposed  # aucun autre effet n'est évalué

        if WatchEffect.NEUTRALIZATION in effects:
            window = neutralization_window(
                role, event_date, declared_days=fact.payload.get("declared_duration_days")
            )
            if window is not None:
                starts_at, expected_return_at = window
                proposed.append(
                    Neutralise(
                        subject_id=fact.subject_id,
                        reason=reason,
                        starts_at=starts_at,
                        expected_return_at=expected_return_at,
                        role=role.value,
                    )
                )

        if WatchEffect.EPISODE in effects:
            window = episode_window(role, event_date)
            proposed.append(
                OpenCase(
                    subject_id=fact.subject_id,
                    reason=reason,
                    origin=CasePriority.ANNOUNCEMENT,
                    opened_at=event_date,
                    expires_at=window[1] if window is not None else None,
                    role=role.value,
                )
            )

        return proposed
