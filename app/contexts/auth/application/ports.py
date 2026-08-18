"""Ports applicatifs du contexte Auth — implémentés en infrastructure."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
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


class AccountContentEraser(ABC):
    """Efface ce qu'un compte a produit, hors du contexte Auth.

    Auth sait fermer un compte ; il ne sait pas ce qu'il y a dedans, et ne doit pas
    l'apprendre. Chaque contexte qui garde du contenu personnel implémente ce port et
    se charge de son propre ménage — c'est ce qui évite qu'`auth` importe les tables
    des autres pour les vider.
    """

    @abstractmethod
    async def erase(self, account_id: UUID) -> None: ...


@dataclass(frozen=True, slots=True)
class TokenClaims:
    """Ce qu'un jeton valide désigne : **qui**, et **depuis quel appareil**.

    L'appareil (DOREA-016) est ce qui rend la révocation possible : révoquer l'appareil
    tue d'un coup l'access, le refresh et la session qui le portent."""

    account_id: UUID
    device_id: str


class TokenService(ABC):
    """Émet et décode les jetons : paire mobile (JWT Bearer) + session backoffice."""

    @abstractmethod
    def issue_pair(self, account_id: UUID, device_id: str) -> TokenPair: ...

    @abstractmethod
    def decode_access(self, token: str) -> TokenClaims:
        """Retourne les claims d'un access token valide (sinon lève)."""
        ...

    @abstractmethod
    def decode_refresh(self, token: str) -> TokenClaims:
        """Retourne les claims d'un refresh token valide (sinon lève)."""
        ...

    @abstractmethod
    def issue_session(self, account_id: UUID, device_id: str) -> str:
        """Jeton de **session backoffice** (livré en cookie HttpOnly, TTL long)."""
        ...

    @abstractmethod
    def decode_session(self, token: str) -> TokenClaims:
        """Retourne les claims d'un jeton de session valide (sinon lève).

        Un jeton de type `access`/`refresh` est **refusé** ici (types cloisonnés) :
        un JWT mobile ne peut pas servir de session backoffice, et inversement.
        """
        ...
