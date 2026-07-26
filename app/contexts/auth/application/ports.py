"""Ports applicatifs du contexte Auth — implémentés en infrastructure."""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.contexts.auth.application.dtos import TokenPair
from app.contexts.auth.domain.otp import OtpChannel, OtpPurpose


class CodeGenerator(ABC):
    """Génère un code OTP (aléatoire cryptographique)."""

    @abstractmethod
    def generate(self) -> str: ...


class OtpSender(ABC):
    """Achemine un code OTP vers son destinataire (email/SMS). Abstrait du domaine."""

    @abstractmethod
    async def send(
        self, *, channel: OtpChannel, target: str, code: str, purpose: OtpPurpose
    ) -> None: ...


class PasswordHasher(ABC):
    """Vérifie/produit un hash de code secret (argon2id).

    Le canal backoffice *écrit* les hash (création de compte) ; sur le canal
    mobile on ne fait que `verify` au login. `hash` sert uniquement au seed de
    développement.
    """

    @abstractmethod
    def verify(self, hashed: str, plain: str) -> bool: ...

    @abstractmethod
    def hash(self, plain: str) -> str: ...


class TokenService(ABC):
    """Émet et décode les jetons : paire mobile (JWT Bearer) + session backoffice."""

    @abstractmethod
    def issue_pair(self, account_id: UUID) -> TokenPair: ...

    @abstractmethod
    def decode_access(self, token: str) -> UUID:
        """Retourne l'`account_id` porté par un access token valide (sinon lève)."""
        ...

    @abstractmethod
    def decode_refresh(self, token: str) -> UUID:
        """Retourne l'`account_id` porté par un refresh token valide (sinon lève)."""
        ...

    @abstractmethod
    def issue_session(self, account_id: UUID) -> str:
        """Jeton de **session backoffice** (livré en cookie HttpOnly, TTL long)."""
        ...

    @abstractmethod
    def decode_session(self, token: str) -> UUID:
        """Retourne l'`account_id` d'un jeton de session valide (sinon lève).

        Un jeton de type `access`/`refresh` est **refusé** ici (types cloisonnés) :
        un JWT mobile ne peut pas servir de session backoffice, et inversement.
        """
        ...
