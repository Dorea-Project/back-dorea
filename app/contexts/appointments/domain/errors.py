"""Erreurs du module Rendez-vous — codes préfixés `APPT_`."""

from app._shared.domain.errors import DomainError, NotFoundError


class AppointmentError(DomainError):
    code = "APPT_ERROR"


class AppointmentNotFoundError(NotFoundError):
    code = "APPT_NOT_FOUND"


class AvailabilityRuleNotFoundError(NotFoundError):
    code = "APPT_AVAILABILITY_NOT_FOUND"


class AppointmentSubjectRequiredError(AppointmentError):
    """Une demande de rendez-vous doit dire, même brièvement, de quoi il s'agit."""

    code = "APPT_SUBJECT_REQUIRED"
    http_status = 422


class AppointmentClosedError(AppointmentError):
    """Transition impossible : le rendez-vous est déjà résolu (décliné/annulé/honoré)."""

    code = "APPT_CLOSED"
    http_status = 409


class NotAppointmentRequesterError(AppointmentError):
    """Seul le demandeur peut annuler sa propre demande."""

    code = "APPT_NOT_REQUESTER"
    http_status = 403


class RequesterNotMemberError(AppointmentError):
    """Seul un membre de l'église peut demander un rendez-vous avec le pasteur."""

    code = "APPT_REQUESTER_NOT_MEMBER"
    http_status = 403


class RequesterIdentityRequiredError(AppointmentError):
    """Un rendez-vous a besoin d'un demandeur : un membre (compte) ou, au bureau, un nom."""

    code = "APPT_REQUESTER_IDENTITY_REQUIRED"
    http_status = 422


class NotAPastorError(AppointmentError):
    """On ne pose une disponibilité (ou un rendez-vous) que pour un membre ayant le rôle Pasteur."""

    code = "APPT_NOT_A_PASTOR"
    http_status = 422


class InvalidAvailabilityError(AppointmentError):
    """Fenêtre de disponibilité incohérente (jour hors 0-6, fin ≤ début, créneau trop grand…)."""

    code = "APPT_AVAILABILITY_INVALID"
    http_status = 422


class SlotNotAvailableError(AppointmentError):
    """Ce créneau n'existe pas, est déjà réservé, ou est passé."""

    code = "APPT_SLOT_NOT_AVAILABLE"
    http_status = 409
