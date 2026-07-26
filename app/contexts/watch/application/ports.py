"""Ports du moteur de veille vers le monde extérieur.

L'engine décide ; il ne connaît ni les rosters, ni M7, ni les tables de la Présence. Un
adaptateur écrit ce qu'il a décidé, et c'est le **seul** chemin d'écriture — condition pour
qu'une reprojection soit sûre.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID


class NeutralizationStore(ABC):
    """Là où vit la neutralisation matérialisée.

    Implémenté au-dessus de l'absence planifiée M6 : c'est le seul objet que le roster et M7
    consultent déjà. Une table parallèle obligerait sept lectures pastorales à unir deux
    sources — et en oublier une seule ferait réapparaître un endeuillé comme absent silencieux.
    """

    @abstractmethod
    async def neutralize(
        self,
        *,
        subject_id: UUID,
        tenant_id: UUID,
        role: str | None,
        starts_at: datetime,
        expected_return_at: datetime,
        source_ref: UUID,
        declared_by_account_id: UUID,
        reason: str,
    ) -> None:
        """Pose ou **prolonge**. Jamais deux périodes, jamais un cumul de durées."""
        ...

    @abstractmethod
    async def extinguish(
        self, *, subject_id: UUID, tenant_id: UUID, cause: str, at: datetime
    ) -> None:
        """Ferme les neutralisations en cours sur cette personne, avec l'issue **stockée**."""
        ...

    @abstractmethod
    async def exclude_forever(
        self,
        *,
        subject_id: UUID,
        tenant_id: UUID,
        source_ref: UUID,
        declared_by_account_id: UUID,
        reason: str,
        at: datetime,
    ) -> None:
        """Retrait définitif de la veille. Absorbant — rien ne le lève."""
        ...

    @abstractmethod
    async def excluded_subject_ids(self, tenant_id: UUID) -> set[UUID]: ...

    @abstractmethod
    async def open_neutralizations(
        self, tenant_id: UUID
    ) -> list[tuple[UUID, UUID, datetime, datetime]]:
        """`(id, subject_id, starts_at, expected_return_at)` — alimente la vue des interpreters."""
        ...

    @abstractmethod
    async def purge_projected_neutralizations(self, tenant_id: UUID) -> None:
        """Efface **uniquement** ce que le moteur a projeté, avant un rejeu du ledger.

        Ne touche jamais à ce qu'un membre a déclaré lui-même : sa parole n'est pas une
        projection, et une reconstruction ne doit pas pouvoir l'effacer. C'est la seule méthode
        autorisée à supprimer du projeté — tout le reste passe par elle."""
        ...


class SignalStore(ABC):
    """Là où vivent les cas ouverts et la mémoire du lien.

    Contrairement à la neutralisation, le signal n'a pas d'équivalent ailleurs : il n'existe
    qu'ici, et il est **entièrement** une projection du ledger."""

    @abstractmethod
    async def open_case(
        self,
        *,
        subject_id: UUID,
        tenant_id: UUID,
        origin: str,
        reason: str,
        opened_at: datetime,
        expires_at: datetime | None,
        source_ref: UUID,
        held: bool,
    ) -> None:
        """Ouvre un cas, ou **enrichit** celui qui existe déjà. Jamais deux sur une personne."""
        ...

    @abstractmethod
    async def enrich_case(
        self, *, subject_id: UUID, tenant_id: UUID, source_ref: UUID, extend_to: datetime | None
    ) -> None: ...

    @abstractmethod
    async def extinguish(
        self, *, subject_id: UUID, tenant_id: UUID, cause: str, at: datetime
    ) -> None:
        """Ferme les cas en cours **si la cause l'autorise sans humain**. Sinon ne fait rien."""
        ...

    @abstractmethod
    async def record_memory(
        self, *, subject_id: UUID, tenant_id: UUID, item: str, at: datetime, reason: str
    ) -> None:
        """La mémoire du lien — restituée plus tard, une seule fois, et jamais agrégée par
        membre. C'est ce qui permettra au Compagnon de **rendre avant de prendre**."""
        ...

    @abstractmethod
    async def live_cases(self, tenant_id: UUID) -> list[tuple[UUID, UUID, UUID | None, str, bool]]:
        """`(id, subject_id, owner_id, origin, is_held)` — alimente la vue et l'arbitrage."""
        ...

    @abstractmethod
    async def purge_projected(self, tenant_id: UUID) -> None:
        """Efface cas et mémoire avant un rejeu. Tout ici est reconstruit à partir des faits."""
        ...
