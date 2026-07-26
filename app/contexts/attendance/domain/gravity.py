"""Poids (gravité) d'un tag d'absence — crochet pour l'effectif & le « point de non-retour » (M7).

Idée (utilisateur, 2026-07-16) : tous les tags ne pèsent pas pareil sur la **rétention**.
Un voyage → la personne **revient** (reste dans l'effectif) ; un déménagement → elle est
**partie** (M7 pourra la sortir de l'effectif et signaler qu'elle ne reviendra plus).

On **plante la gravité ici** ; la logique d'effectif et l'alerte de non-retour vivent en M7.
"""

from enum import StrEnum

from app.contexts.attendance.domain.enums import AbsenceReason


class AbsenceGravity(StrEnum):
    TRANSIENT = "transient"  # revient — reste dans l'effectif
    WATCH = "watch"  # à surveiller — l'accumulation compte
    STRUCTURAL = "structural"  # parti — candidat à sortir de l'effectif (M7)


ABSENCE_GRAVITY: dict[AbsenceReason, AbsenceGravity] = {
    AbsenceReason.SICK: AbsenceGravity.TRANSIENT,
    AbsenceReason.TRAVEL: AbsenceGravity.TRANSIENT,
    AbsenceReason.WORK: AbsenceGravity.TRANSIENT,
    AbsenceReason.FAMILY: AbsenceGravity.TRANSIENT,
    AbsenceReason.STUDIES: AbsenceGravity.TRANSIENT,
    AbsenceReason.UNAVAILABLE: AbsenceGravity.WATCH,
    AbsenceReason.OTHER: AbsenceGravity.WATCH,
    AbsenceReason.MOVED: AbsenceGravity.STRUCTURAL,
}


def gravity_of(reason: AbsenceReason) -> AbsenceGravity:
    return ABSENCE_GRAVITY.get(reason, AbsenceGravity.WATCH)
