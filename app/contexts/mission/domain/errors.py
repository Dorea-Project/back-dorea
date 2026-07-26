"""Erreurs du contexte Mission — codes préfixés `MISSION_`."""

from app._shared.domain.errors import DomainError, NotFoundError


class MissionError(DomainError):
    code = "MISSION_ERROR"


class MissionLinkNotFoundError(NotFoundError):
    code = "MISSION_LINK_NOT_FOUND"


class MissionLinkInactiveError(MissionError):
    """Le lien d'invitation a expiré ou a été révoqué."""

    code = "MISSION_LINK_INACTIVE"
    http_status = 409


class InvalidMissionLinkError(MissionError):
    """Carte incohérente (ni personne ni groupe, message vide, géo incomplète…)."""

    code = "MISSION_LINK_INVALID"
    http_status = 422


class SeekerContactRequiredError(MissionError):
    """Accepter l'invitation exige au moins un nom (pour être accompagné)."""

    code = "MISSION_SEEKER_CONTACT_REQUIRED"
    http_status = 422


class NotAChurchMemberError(MissionError):
    """Seul un membre d'une église peut évangéliser en son nom."""

    code = "MISSION_NOT_A_CHURCH_MEMBER"
    http_status = 403


class VerseNotFoundError(MissionError):
    """L'IA n'a pas su reconnaître de référence dans la citation (trop floue / hors Écriture)."""

    code = "MISSION_VERSE_NOT_FOUND"
    http_status = 422


class VerseTextUnavailableError(MissionError):
    """Référence reconnue mais absente de la Bible canonique disponible (couverture du dataset)."""

    code = "MISSION_VERSE_TEXT_UNAVAILABLE"
    http_status = 422


class SeekerNotFoundError(NotFoundError):
    """Chercheur introuvable."""

    code = "MISSION_SEEKER_NOT_FOUND"


class SeekerAlreadyResolvedError(MissionError):
    """Le parcours du chercheur est déjà clos (intégré ou clôturé) — pas de retour en arrière."""

    code = "MISSION_SEEKER_ALREADY_RESOLVED"
    http_status = 409


class SeekerPhoneRequiredError(MissionError):
    """Intégrer un chercheur exige un téléphone (l'identité membre est fondée sur le numéro)."""

    code = "MISSION_SEEKER_PHONE_REQUIRED"
    http_status = 422
