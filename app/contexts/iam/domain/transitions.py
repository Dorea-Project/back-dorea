"""Table de transition des statuts d'appartenance (§5.5) — logique de domaine pure.

Chaîne de progression : `invited → visitor → sympathizer → newcomer → confirmed_member`.
On n'avance que **d'un palier à la fois** (fast-track interdit en V1) :
- palier suivant exact → OK
- palier plus loin dans la chaîne → `StatusSkipForbiddenError` (saut interdit)
- reste (événement inconnu ici, statut hors chaîne, régression) → `InvalidTransitionError`

`bootstrap_owner` (genèse), `demote`, `close`, `create_external_participant` sont
gérés ailleurs (respectivement provisionnement/enrôlement et incrément « cascade »).
"""

from __future__ import annotations

from app.contexts.iam.domain.enums import MembershipStatus as S
from app.contexts.iam.domain.enums import MembershipTransitionEvent as E
from app.contexts.iam.domain.errors import InvalidTransitionError, StatusSkipForbiddenError

# Ordre de la chaîne progressive.
_CHAIN: tuple[S, ...] = (S.INVITED, S.VISITOR, S.SYMPATHIZER, S.NEWCOMER, S.CONFIRMED_MEMBER)

# Événement progressif → statut cible.
_FORWARD_TARGET: dict[E, S] = {
    E.FIRST_ATTENDANCE_RECORDED: S.VISITOR,
    E.QUALIFY_SYMPATHIZER: S.SYMPATHIZER,
    E.QUALIFY_NEWCOMER: S.NEWCOMER,
    E.CONFIRM_MEMBER: S.CONFIRMED_MEMBER,
}


def next_status(current: S, event: E) -> S:
    """Statut résultant d'un événement progressif appliqué à `current`, sinon lève."""
    target = _FORWARD_TARGET.get(event)
    if target is None or current not in _CHAIN:
        raise InvalidTransitionError(
            "Transition de statut non autorisée.",
            details={"from": current.value, "event": event.value},
        )

    current_idx = _CHAIN.index(current)
    required_source_idx = _CHAIN.index(target) - 1

    if current_idx == required_source_idx:
        return target
    if current_idx < required_source_idx:
        raise StatusSkipForbiddenError(
            "Saut de palier interdit (avancer un palier à la fois).",
            details={"from": current.value, "event": event.value, "to": target.value},
        )
    raise InvalidTransitionError(
        "Transition de statut non autorisée (régression ou palier déjà franchi).",
        details={"from": current.value, "event": event.value, "to": target.value},
    )
