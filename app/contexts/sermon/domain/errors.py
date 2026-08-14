"""Erreurs du module Sermon — codes préfixés `SER_`."""

from app._shared.domain.errors import DomainError, NotFoundError


class SermonError(DomainError):
    code = "SER_ERROR"


class SermonNotFoundError(NotFoundError):
    code = "SER_NOT_FOUND"


class SermonTitleRequiredError(SermonError):
    """Un sermon porte un titre — c'est ainsi qu'il vit dans le fil."""

    code = "SER_TITLE_REQUIRED"
    http_status = 422


class SermonContentRequiredError(SermonError):
    """Un sermon sans texte n'a rien à digérer."""

    code = "SER_CONTENT_REQUIRED"
    http_status = 422


class UnsupportedSermonFormatError(SermonError):
    """Format de dépôt non pris en charge (ex. audio avant S-6, ou format inconnu)."""

    code = "SER_FORMAT_UNSUPPORTED"
    http_status = 422


class SermonFileTypeMismatchError(SermonError):
    """Les octets déposés ne sont pas ceux du format déclaré (DOREA-024, côté sermon).

    Le `kind` est **déclaré par le client** : il dit ce qu'il veut. Recouper les premiers
    octets empêche d'envoyer un fichier arbitraire dans le parseur d'un format qu'il n'est
    pas — et, le jour où l'extraction se facture (S-6), de faire payer ce mensonge."""

    code = "SER_FILE_TYPE_MISMATCH"
    http_status = 415


class SermonFileTooComplexError(SermonError):
    """Le fichier déposé coûte trop cher à ouvrir (DOREA-011).

    Un `.pptx` est un ZIP : quinze mégaoctets compressés peuvent en peser des milliers
    une fois décompressés. Un PDF peut porter des dizaines de milliers de pages. Le
    plafond d'upload borne ce qui **entre** ; celui-ci borne ce que ça **coûte**."""

    code = "SER_FILE_TOO_COMPLEX"
    http_status = 413


class SermonNotEditableError(SermonError):
    """Transition de cycle de vie illégale (approuver hors brouillon, publier hors approuvé)."""

    code = "SER_NOT_EDITABLE"
    http_status = 409


class SermonNotPublishedError(SermonError):
    """Le compagnon ne s'ouvre que sur un sermon **publié**."""

    code = "SER_NOT_PUBLISHED"
    http_status = 409


class NotAChurchMemberError(SermonError):
    """Le compagnon accompagne les membres de l'église."""

    code = "SER_NOT_MEMBER"
    http_status = 403


class CompanionSessionNotFoundError(NotFoundError):
    code = "SER_COMPANION_NOT_FOUND"


class NotSessionOwnerError(SermonError):
    """Une session de compagnon est **privée** — seul son membre y accède."""

    code = "SER_COMPANION_NOT_OWNER"
    http_status = 403


class CompanionClosedError(SermonError):
    """Geste illégal sur la session (répondre deux fois, avancer sans réponse, ou déjà terminée)."""

    code = "SER_COMPANION_CLOSED"
    http_status = 409
