"""Erreurs du contexte Présence — codes préfixés `ATT_`."""

from app._shared.domain.errors import DomainError, NotFoundError


class AttendanceError(DomainError):
    code = "ATT_ERROR"


class GatheringNotFoundError(NotFoundError):
    code = "ATT_GATHERING_NOT_FOUND"


class GatheringClosedError(AttendanceError):
    """La rencontre est clôturée : plus de saisie (M6-0)."""

    code = "ATT_GATHERING_CLOSED"
    http_status = 409


class NotAGroupMemberError(AttendanceError):
    """On ne pointe présent qu'un membre du roster ; un présent hors-roster = visiteur (M6-3)."""

    code = "ATT_NOT_A_GROUP_MEMBER"
    http_status = 422


class NotAChurchMemberError(AttendanceError):
    """Déclarer une absence exige d'être membre actif de l'église (M6-2)."""

    code = "ATT_NOT_A_CHURCH_MEMBER"
    http_status = 422


class InvalidAbsencePeriodError(AttendanceError):
    """Période invalide (début après fin) — M6-2."""

    code = "ATT_INVALID_ABSENCE_PERIOD"
    http_status = 422


class PlannedAbsenceNotFoundError(NotFoundError):
    """Absence planifiée introuvable (ou pas la vôtre) — M6-2."""

    code = "ATT_PLANNED_ABSENCE_NOT_FOUND"


class VisitorNotFoundError(NotFoundError):
    """Visiteur introuvable sur cette rencontre — M6-3."""

    code = "ATT_VISITOR_NOT_FOUND"


class VisitorPhoneRequiredError(AttendanceError):
    """Convertir un visiteur en membre exige un téléphone (identité du compte) — M6-3."""

    code = "ATT_VISITOR_PHONE_REQUIRED"
    http_status = 422


class VisitorNotGroupScopedError(AttendanceError):
    """La rencontre n'est pas rattachée à un groupe : pas de cellule où rejoindre — M6-3."""

    code = "ATT_VISITOR_NOT_GROUP_SCOPED"
    http_status = 422


class InvalidCadenceError(AttendanceError):
    """Cadence invalide (weekday manquant pour weekly/biweekly, day_of_month hors 1-28…) — P1."""

    code = "ATT_INVALID_CADENCE"
    http_status = 422


class CadenceAlreadyExistsError(AttendanceError):
    """Une cadence active existe déjà pour ce groupe (au plus une) — P1."""

    code = "ATT_CADENCE_ALREADY_EXISTS"
    http_status = 409


class InvalidSuspensionPeriodError(AttendanceError):
    """Période de suspension invalide (fin avant début) — P1."""

    code = "ATT_INVALID_SUSPENSION_PERIOD"
    http_status = 422
