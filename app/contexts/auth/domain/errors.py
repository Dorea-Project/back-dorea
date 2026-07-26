"""Erreurs du contexte Auth — codes préfixés `AUTH_`."""

from app._shared.domain.errors import DomainError, UnauthorizedError


class AuthError(DomainError):
    code = "AUTH_ERROR"


class InvalidSecretCodeFormatError(AuthError):
    code = "AUTH_INVALID_SECRET_CODE_FORMAT"
    http_status = 422


class InvalidPasswordError(AuthError):
    code = "AUTH_INVALID_PASSWORD"
    http_status = 422


class InvalidCredentialsError(UnauthorizedError):
    """Identifiants invalides.

    Message volontairement indifférencié (téléphone inconnu, mauvais code,
    credentials absentes) pour ne pas révéler l'existence d'un compte.
    """

    code = "AUTH_INVALID_CREDENTIALS"


class AccountInactiveError(UnauthorizedError):
    code = "AUTH_ACCOUNT_INACTIVE"


class TooManyLoginAttemptsError(AuthError):
    """Trop d'échecs de connexion pour cet identifiant → verrou temporaire (anti-brute-force)."""

    code = "AUTH_TOO_MANY_ATTEMPTS"
    http_status = 429


class InvalidTokenError(UnauthorizedError):
    code = "AUTH_INVALID_TOKEN"


class PhoneAlreadyRegisteredError(AuthError):
    """Le numéro possède déjà un PIN mobile → passer par la connexion, pas l'inscription."""

    code = "AUTH_PHONE_ALREADY_REGISTERED"
    http_status = 409


# --- OTP (vérification de contact / nouvel appareil / opérations sensibles) ---


class OtpNotFoundError(AuthError):
    """Aucun défi OTP actif pour ce contact/objet (ou déjà consommé)."""

    code = "AUTH_OTP_NOT_FOUND"
    http_status = 404


class OtpExpiredError(AuthError):
    code = "AUTH_OTP_EXPIRED"
    http_status = 410


class OtpInvalidError(AuthError):
    code = "AUTH_OTP_INVALID"
    http_status = 401


class OtpTooManyAttemptsError(AuthError):
    code = "AUTH_OTP_TOO_MANY_ATTEMPTS"
    http_status = 429
