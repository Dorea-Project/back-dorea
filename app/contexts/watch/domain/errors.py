"""Erreurs du moteur de veille — codes préfixés `WATCH_`."""

from app._shared.domain.errors import DomainError


class WatchError(DomainError):
    code = "WATCH_ERROR"


class ForbiddenFactKindError(WatchError):
    """Un type de fait d'une famille que le produit s'interdit : inaction, argent, inférence.

    Levée à l'**enregistrement** d'une source, donc au démarrage — jamais en production."""

    code = "WATCH_FORBIDDEN_FACT_KIND"
    http_status = 500


class SourceNotRegisteredError(WatchError):
    """Un fait venu d'une source que l'engine ne connaît pas. Ajouter ≠ modifier."""

    code = "WATCH_SOURCE_NOT_REGISTERED"
    http_status = 422


class FactKindNotAllowedError(WatchError):
    """Cette source est enregistrée, mais pas pour dire cela."""

    code = "WATCH_KIND_NOT_ALLOWED"
    http_status = 422


class ConsentRequiredError(WatchError):
    """Ce type de fait ne peut pas entrer sans preuve de consentement."""

    code = "WATCH_CONSENT_REQUIRED"
    http_status = 422


class InvalidPayloadError(WatchError):
    """Le payload ne porte pas ce que ce type de fait exige."""

    code = "WATCH_INVALID_PAYLOAD"
    http_status = 422


class InvalidSignalTransitionError(WatchError):
    """Cette transition n'existe pas dans la machine à états. Refusée, pas invalidée."""

    code = "WATCH_INVALID_TRANSITION"
    http_status = 409


class AbsorbingOutcomeError(WatchError):
    """L'issue est absorbante : décès, ou demande explicite qu'on cesse. Rien n'en sort."""

    code = "WATCH_ABSORBING_OUTCOME"
    http_status = 409


class HumanClosureRequiredError(WatchError):
    """Fermer un cas est un acte humain — sauf quand le cas n'était pas réel."""

    code = "WATCH_HUMAN_CLOSURE_REQUIRED"
    http_status = 422


class NoInterpreterError(WatchError):
    """Aucun interpreter enregistré pour ce type de fait à cette date.

    Le fait reste au ledger — il sera interprété quand l'interpreter existera. On ne perd rien."""

    code = "WATCH_NO_INTERPRETER"
    http_status = 500
