"""Étage 03 — l'arbitrage : le seul endroit qui décide de ce qui **devient visible**.

Fixe, non extensible. Un greffon ajoute des sources et des interpreters ; il ne touche jamais à
cet étage, parce que c'est ici que tiennent les promesses qu'on ne veut pas voir contournées.

Quatre décisions, dans cet ordre :

1. **L'exclusion absorbe.** Une personne retirée de la veille ne reçoit plus rien, quelle que
   soit la source — sauf l'exclusion elle-même, qui est ce qui l'y a mise.
2. **Fusion par personne.** Un second cas sur quelqu'un qui en a déjà un ouvert devient un
   enrichissement. Une personne n'a jamais deux cas : sinon deux responsables l'appellent le
   même soir, chacun croyant être le seul.
3. **Priorité par origine du dire**, jamais par gravité supposée. Personne ici ne note la
   gravité d'une vie.
4. **Plafond de débit.** Au-delà de N cas ouverts, un responsable ne reçoit plus rien de
   nouveau : le surplus est **retenu**, pas perdu, et réévalué. Un responsable noyé ne traite
   pas plus de cas — il les ignore tous. Le déclaré n'y entre jamais : on ne fait pas attendre
   quelqu'un qui a levé la main pour lui-même.

Écrit **avec** la machine à états, jamais après. Un `Signal` sans plafond, c'est une file qui
déborde chez le premier responsable et un produit qu'on abandonne au bout de trois semaines.
Les nombres, eux, attendent le terrain — ils vivent dans `ArbitrationPolicy`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace

from app.contexts.watch.application.interpretation import WatchStateView
from app.contexts.watch.domain.effects import (
    CasePriority,
    EffectKind,
    EnrichCase,
    ExcludeForever,
    MarkCaseSeen,
    OpenCase,
    ProposedEffect,
    RecordContactAttempt,
    ResolveCase,
    ResolveContactAttempt,
)
from app.contexts.watch.domain.regime import HeldReason

# Ce qui **traverse** l'exclusion : l'exclusion elle-même — c'est elle qui l'a posée — et les
# gestes du responsable sur un cas. Fermer le cas d'un défunt, dire qu'on a tenté de le joindre,
# sont justement les actes qu'on attend de lui ; les refuser laisserait le cas ouvert pour
# toujours sur son écran.
_CROSSES_EXCLUSION = (
    ExcludeForever,
    MarkCaseSeen,
    ResolveCase,
    RecordContactAttempt,
    ResolveContactAttempt,
)

# Ordre de priorité — par **origine du dire**. Le déclaré d'abord : c'est la personne elle-même.
_PRIORITY_ORDER: dict[CasePriority, int] = {
    CasePriority.DECLARED: 0,
    CasePriority.DEADLINE: 1,
    CasePriority.ANNOUNCEMENT: 2,
    CasePriority.CONCERN: 3,
    CasePriority.ABSENCE: 4,
}


@dataclass(frozen=True)
class ArbitrationPolicy:
    """Les nombres — par église, jamais en dur. Valeurs de départ à calibrer (étape 0 terrain)."""

    open_cases_cap: int = 5  # cas ouverts par responsable ; le déclaré n'y entre jamais


@dataclass(frozen=True)
class Arbitration:
    """Ce qui passe, ce qui est retenu, ce qui tombe. **Retenu ≠ perdu.**"""

    admitted: tuple[ProposedEffect, ...] = ()
    held: tuple[ProposedEffect, ...] = ()
    dropped: tuple[tuple[ProposedEffect, str], ...] = ()
    # **Pourquoi** ce qui est retenu l'est. Le plafond se relâche quand la place se libère ; le
    # rodage ne se relâche que le jour où l'église décide de laisser Dorea parler.
    held_reason: HeldReason = HeldReason.CAP


def _origin_of(effect: ProposedEffect) -> CasePriority | None:
    return getattr(effect, "origin", None)


def _rank(effect: ProposedEffect) -> int:
    origin = _origin_of(effect)
    return _PRIORITY_ORDER.get(origin, len(_PRIORITY_ORDER)) if origin else -1


def arbitrate(
    effects: Sequence[ProposedEffect],
    state: WatchStateView,
    *,
    policy: ArbitrationPolicy | None = None,
) -> Arbitration:
    policy = policy or ArbitrationPolicy()

    kept: list[ProposedEffect] = []
    dropped: list[tuple[ProposedEffect, str]] = []
    held: list[ProposedEffect] = []

    # 1 — l'exclusion absorbe. Ce garde est ici, pas dans les interpreters : un seul endroit à
    # tenir, valable pour tout greffon présent et futur.
    for effect in effects:
        # Les gestes du responsable traversent l'exclusion : fermer le cas d'un défunt est
        # justement l'acte qu'on attend de lui, et le refuser laisserait le cas ouvert pour
        # toujours sur son écran.
        if state.is_excluded(effect.subject_id) and not isinstance(effect, _CROSSES_EXCLUSION):
            dropped.append((effect, "subject_excluded"))
            continue
        kept.append(effect)

    # 2 — fusion par personne : un seul cas ouvert, jamais deux.
    fused: list[ProposedEffect] = []
    for effect in kept:
        if isinstance(effect, OpenCase) and state.has_open_case(effect.subject_id):
            fused.append(
                EnrichCase(
                    subject_id=effect.subject_id,
                    reason=effect.reason,  # conservée pour la trace, jamais réécrite sur le cas
                    origin=effect.origin,
                    extend_to=effect.expires_at,
                    # Ce qu'on vient d'apprendre s'ajoute à la fiche, **quelle que soit
                    # l'origine**. Sans cette annotation, un événement qui aurait ouvert un cas
                    # se dissout en une source de plus dès que la personne en a déjà un : le
                    # responsable ne verrait jamais que quelqu'un a pensé à elle, ni qu'elle a
                    # annulé le rendez-vous qu'elle avait demandé.
                    annotation=effect.reason,
                    # Et l'urgence de ce qui arrive est portée. `Signal.enrich` ne la retient que
                    # si elle est **plus** urgente que celle du cas : un événement anodin ne peut
                    # pas faire redescendre un cas grave, mais une main qui se retire remonte.
                    priority=effect.origin,
                )
            )
        else:
            fused.append(effect)

    # 3 — priorité par origine, puis ordre d'arrivée (tri stable) : à origine égale, le plus
    # ancien d'abord — c'est le décrochage le plus frais qui se traite en premier.
    fused.sort(key=_rank)

    # 4 — plafond de débit, appliqué aux seules **ouvertures** de cas.
    #
    # En **rodage**, aucun cas ne sort — pas même le déclaré. Tout est détecté, journalisé, écrit,
    # et retenu avec sa raison : l'église observe ce que Dorea aurait dit avant de le laisser dire.
    # Retenir le déclaré peut surprendre, et c'est pourtant le point : une église qui n'a pas encore
    # annoncé Dorea à ses responsables ne doit pas leur envoyer un cas, quelle qu'en soit l'origine.
    held_reason = HeldReason.CAP
    if not state.regime.emits:
        return Arbitration(
            admitted=tuple(e for e in fused if not isinstance(e, OpenCase)),
            held=tuple(e for e in fused if isinstance(e, OpenCase)),
            dropped=tuple(dropped),
            held_reason=HeldReason.SHADOW,
        )

    admitted: list[ProposedEffect] = []
    budget: dict[object, int] = {}
    for effect in fused:
        if not isinstance(effect, OpenCase) or effect.origin is CasePriority.DECLARED:
            admitted.append(effect)  # le déclaré ne passe jamais au plafond
            continue
        # Le propriétaire **résolu à l'émission** l'emporte sur celui qu'on déduirait des cas
        # déjà ouverts : sur une personne qui n'en a aucun, la déduction rend `None`, et tout le
        # monde partagerait alors le même budget. Le plafond ne pèserait sur personne — et un
        # responsable pourrait signaler dix fois en trente secondes sans jamais être retenu.
        owner = getattr(effect, "owner_account_id", None) or state.owner_of(effect.subject_id)
        already = budget.get(owner, state.open_cases_of_owner(owner))
        if already >= policy.open_cases_cap:
            held.append(effect)  # détecté, non émis, réévalué
            continue
        budget[owner] = already + 1
        admitted.append(effect)

    return Arbitration(
        admitted=tuple(admitted),
        held=tuple(held),
        dropped=tuple(dropped),
        held_reason=held_reason,
    )


def as_held(effect: ProposedEffect) -> ProposedEffect:
    """Un cas retenu reste le même cas — seule sa visibilité change."""
    return replace(effect)


# Les effets que l'étage 04 sait écrire. Les autres sont proposés et journalisés, pas perdus :
# ils vivent dans le ledger, et une reprojection les honorera quand l'objet existera.
MATERIALIZABLE: frozenset[EffectKind] = frozenset(
    {
        EffectKind.NEUTRALISE,
        EffectKind.EXTINGUISH,
        EffectKind.EXCLUDE_FOREVER,
        EffectKind.OPEN_CASE,
        EffectKind.ENRICH_CASE,
        EffectKind.RECORD_MEMORY,
        EffectKind.SCHEDULE_CHECK,
        EffectKind.CANCEL_SCHEDULED_CHECKS,
        EffectKind.COVERAGE_SIGNAL,
        EffectKind.MARK_CASE_SEEN,
        EffectKind.RESOLVE_CASE,
        EffectKind.RECORD_CONTACT_ATTEMPT,
        EffectKind.RESOLVE_CONTACT_ATTEMPT,
    }
)
