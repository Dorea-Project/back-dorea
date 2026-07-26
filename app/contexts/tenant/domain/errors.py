"""Erreurs de domaine du contexte Tenant — codes préfixés `TENANT_` (cf. M1 §6)."""

from app._shared.domain.errors import DomainError, ForbiddenError, NotFoundError, UnauthorizedError


class TenantError(DomainError):
    """Base des erreurs du contexte Tenant (M0)."""

    code = "TENANT_ERROR"


class TenantNotFoundError(NotFoundError):
    code = "TENANT_NOT_FOUND"


class TenantForbiddenError(ForbiddenError):
    """Acteur non-Owner de ce tenant (lecture/édition réservées à son Owner)."""

    code = "TENANT_FORBIDDEN"


class OnboardingNotFoundError(NotFoundError):
    code = "ONBOARDING_NOT_FOUND"


class InvalidOnboardingTransitionError(TenantError):
    """Transition d'onboarding non permise depuis l'état courant."""

    code = "ONBOARDING_INVALID_TRANSITION"
    http_status = 409


class PlatformAuthRequiredError(UnauthorizedError):
    """Acte Plateforme sans jeton de service valide (garde du provisionnement)."""

    code = "TENANT_PLATFORM_AUTH_REQUIRED"


class InvalidParentTenantError(TenantError):
    """`parent_id` fourni mais invalide : mère inexistante, suspendue, ou elle-même annexe.

    Une annexe est une église-fille (M0 §4.1) : sa mère doit exister, être active et
    être un **principal** (filiation plate en V1 — pas d'annexe d'annexe)."""

    code = "TENANT_INVALID_PARENT"
    http_status = 422


class NewOwnerNotEligibleError(TenantError):
    """Le futur titulaire n'est pas membre confirmé actif de ce tenant.

    On ne confie une église qu'à quelqu'un qui y appartient : le transfert clôt
    l'ancien siège, il doit donc refuser **avant** tout acte irréversible un
    compte inexistant ou étranger au tenant."""

    code = "TENANT_NEW_OWNER_NOT_ELIGIBLE"
    http_status = 409
