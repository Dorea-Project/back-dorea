"""Ports du module Event vers l'extérieur (tenant / iam) — pour la portée et la dénomination."""

from abc import ABC, abstractmethod
from uuid import UUID


class EventAudiencePort(ABC):
    """Résout l'**audience** : la dénomination d'une église et sa taille (membres actifs).

    Events lit tenant + iam à travers ce port : la **portée** d'un événement (combien de personnes
    il peut toucher) et la **dénomination** d'un spectateur, sans coupler les contextes."""

    @abstractmethod
    async def denomination_of(self, tenant_id: UUID) -> str | None: ...

    @abstractmethod
    async def count_active_members(self, tenant_id: UUID) -> int:
        """La portée « église » : le nombre de membres actifs du tenant."""
        ...

    @abstractmethod
    async def tenants_in_denomination(self, denomination: str) -> list[UUID]:
        """Les églises (tenants) partageant cette dénomination — pour la diffusion élargie."""
        ...

    @abstractmethod
    async def all_tenant_ids(self) -> list[UUID]:
        """Toutes les églises de la plateforme — la cible d'un broadcast portée plateforme."""
        ...

    @abstractmethod
    async def location_of(self, tenant_id: UUID) -> tuple[float, float] | None:
        """Les coordonnées d'une église, ou None si elle ne les a pas renseignées.

        Une église sans coordonnées ne voit aucun événement de voisinage, et n'apparaît dans
        l'audience d'aucun : c'est une donnée manquante, pas une exclusion — l'onboarding la
        demande déjà."""
        ...

    @abstractmethod
    async def tenants_near(
        self, *, latitude: float, longitude: float, radius_km: float
    ) -> list[UUID]:
        """Les églises dans un rayon autour d'un point — **toutes dénominations confondues**.

        C'est la seule question géographique du produit, et elle était absente : `country`,
        `city`, `latitude` et `longitude` sont collectés à l'onboarding de chaque église, portés
        par chaque événement, et n'ont jamais servi à choisir qui est atteint.

        On interroge les coordonnées, pas la commune : `city` est du texte libre, et « Yopougon »
        y sera saisi « Yopougon », « Abidjan » ou « Abidjan-Yopougon » selon la personne. Un rayon
        se vérifie ; une chaîne de caractères se discute."""
        ...

    @abstractmethod
    async def member_account_ids(self, tenant_ids: list[UUID]) -> list[UUID]:
        """Les comptes des membres actifs d'un ensemble d'églises — la cible d'un broadcast."""
        ...


class BusinessTierPort(ABC):
    """Le tier d'une personne — la porte du rayonnement au-delà de son église.

    Events lit le module Billing à travers ce port : publier en portée dénomination/plateforme
    exige que l'**auteur** ait le compte Business actif."""

    @abstractmethod
    async def is_business(self, account_id: UUID) -> bool: ...
