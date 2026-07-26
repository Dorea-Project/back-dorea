"""Domaine **Onboarding** — la *demande* d'une église (avant matérialisation).

Principe (message « scénario ») : on ne matérialise le tenant/owner que quand la
**confiance est établie**. La demande porte l'intention (données du tenant + de
l'owner + credential déjà hashé) et son **statut**. À l'approbation Dorea, la genèse
est déclenchée ; au rejet, rien n'est créé dans `tenants`/`accounts`.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from app._shared.domain.entity import AggregateRoot
from app.contexts.tenant.domain.drafts import OwnerDraft, TenantDraft
from app.contexts.tenant.domain.errors import InvalidOnboardingTransitionError


class OnboardingStatus(StrEnum):
    SUBMITTED = "submitted"  # soumise, email non vérifié
    EMAIL_VERIFIED = "email_verified"  # OTP email OK, en attente de validation Dorea
    APPROVED = "approved"  # validée → tenant/owner matérialisés
    REJECTED = "rejected"  # refusée


class OnboardingRequest(AggregateRoot):
    def __init__(
        self,
        *,
        id: UUID,
        status: OnboardingStatus,
        submitted_at: datetime,
        tenant: TenantDraft,
        owner: OwnerDraft,
        owner_password_hash: str,
        decided_at: datetime | None = None,
        rejection_reason: str | None = None,
    ) -> None:
        super().__init__()
        self.id = id
        self.status = status
        self.submitted_at = submitted_at
        self.tenant = tenant
        self.owner = owner
        self.owner_password_hash = owner_password_hash
        self.decided_at = decided_at
        self.rejection_reason = rejection_reason

    def mark_email_verified(self) -> None:
        self._require(OnboardingStatus.SUBMITTED, "vérifier l'email")
        self.status = OnboardingStatus.EMAIL_VERIFIED

    def approve(self, at: datetime) -> None:
        self._require(OnboardingStatus.EMAIL_VERIFIED, "approuver")
        self.status = OnboardingStatus.APPROVED
        self.decided_at = at

    def reject(self, at: datetime, reason: str) -> None:
        if self.status in (OnboardingStatus.APPROVED, OnboardingStatus.REJECTED):
            raise InvalidOnboardingTransitionError(
                "Demande déjà tranchée.", details={"status": self.status.value}
            )
        self.status = OnboardingStatus.REJECTED
        self.decided_at = at
        self.rejection_reason = reason

    def _require(self, expected: OnboardingStatus, action: str) -> None:
        if self.status is not expected:
            raise InvalidOnboardingTransitionError(
                f"Impossible de {action} depuis l'état '{self.status.value}'.",
                details={"status": self.status.value, "expected": expected.value},
            )
