"""Ports de persistance du contexte Auth."""

from abc import abstractmethod
from datetime import datetime
from uuid import UUID

from app._shared.domain.repository import Repository
from app.contexts.auth.domain.credentials import AuthCredentials
from app.contexts.auth.domain.login_attempt import LoginAttempt
from app.contexts.auth.domain.otp import OtpChallenge, OtpPurpose


class LoginAttemptRepository(Repository):
    """Compteur d'échecs de login par identifiant (anti-brute-force, DOREA-004)."""

    @abstractmethod
    async def get(self, identifier: str) -> LoginAttempt | None: ...

    @abstractmethod
    async def save(self, attempt: LoginAttempt) -> None:
        """Upsert du compteur pour cet identifiant."""
        ...


class CredentialsRepository(Repository):
    @abstractmethod
    async def get_by_phone(self, phone_number: str) -> AuthCredentials | None:
        """Projection d'authentification pour un numéro (membre), ou None."""
        ...

    @abstractmethod
    async def get_by_email(self, email: str) -> AuthCredentials | None:
        """Projection d'authentification pour un email (owner/backoffice), ou None."""
        ...

    @abstractmethod
    async def get_by_account_id(self, account_id: UUID) -> AuthCredentials | None:
        """Projection pour un compte (opérations sensibles), ou None."""
        ...


class AccountSecurityRepository(Repository):
    """Écritures de sécurité sur `accounts` (PIN mobile, mot de passe backoffice, numéro)."""

    @abstractmethod
    async def create_self_registered(
        self,
        *,
        account_id: UUID,
        phone_number: str,
        pin_hash: str,
        hash_algo_version: int,
        created_at: datetime,
    ) -> None:
        """Crée un compte global **auto-inscrit** (mobile, `self_service`) avec son PIN (M-1)."""
        ...

    @abstractmethod
    async def set_pin(self, account_id: UUID, pin_hash: str, hash_algo_version: int) -> None:
        """Pose/renouvelle le PIN mobile (`pin_hash`) — surface Flutter (décision C)."""
        ...

    @abstractmethod
    async def set_password(
        self, account_id: UUID, password_hash: str, hash_algo_version: int
    ) -> None:
        """Pose/renouvelle le mot de passe backoffice (`password_hash`) — surface PWA."""
        ...

    @abstractmethod
    async def set_phone(self, account_id: UUID, phone_number: str) -> None: ...


class DeviceRepository(Repository):
    """Appareils **de confiance** : un appareil déjà vérifié par OTP ne redemande pas."""

    @abstractmethod
    async def is_trusted(self, account_id: UUID, device_id: str) -> bool: ...

    @abstractmethod
    async def trust(self, account_id: UUID, device_id: str, trusted_at: datetime) -> None:
        """Marque un appareil comme de confiance (idempotent)."""
        ...

    @abstractmethod
    async def revoke(self, account_id: UUID, device_id: str, revoked_at: datetime) -> None:
        """Révoque **un** appareil : ses jetons cessent d'être acceptés (DOREA-016).

        C'est ce que fait une déconnexion. L'appareil redeviendra de confiance après
        un nouvel OTP."""
        ...

    @abstractmethod
    async def revoke_all(self, account_id: UUID, revoked_at: datetime) -> int:
        """Révoque **tous** les appareils d'un compte — « me déconnecter partout ».

        Le geste à faire quand on soupçonne un vol. Retourne le nombre d'appareils."""
        ...


class OtpChallengeRepository(Repository):
    @abstractmethod
    async def add(self, challenge: OtpChallenge) -> None: ...

    @abstractmethod
    async def count_issued_since(self, target: str, since: datetime) -> int:
        """Combien de codes ont été **envoyés** à ce contact depuis `since` (DOREA-022).

        Le plafond se lit sur les défis eux-mêmes : émettre laisse une trace datée, donc
        il n'y a rien de plus à stocker pour savoir qu'on émet trop."""
        ...

    @abstractmethod
    async def get_active(
        self, purpose: OtpPurpose, target: str, now: datetime
    ) -> OtpChallenge | None:
        """Dernier défi **non consommé** pour (purpose, target). None si aucun."""
        ...

    @abstractmethod
    async def increment_attempts(self, challenge_id: UUID) -> None: ...

    @abstractmethod
    async def mark_consumed(self, challenge_id: UUID, consumed_at: datetime) -> None: ...
