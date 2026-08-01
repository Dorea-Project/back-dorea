"""Ce que la boucle froide ajoute au produit — **un entier par église, et ses propositions**.

`WatchParameterRepository` sait lire ; personne n'avait encore besoin d'écrire un seuil depuis le
code, parce que le seed posait les valeurs et qu'un humain les changeait en base. La boucle froide
en a besoin, et c'est exactement là qu'il faut regarder ce qu'on lui donne.

Un port **séparé** plutôt qu'une méthode de plus sur le dépôt existant : la lecture est partout
dans le moteur, l'écriture nulle part ailleurs. Les séparer rend visible dans les signatures ce
qui, sinon, ne serait plus qu'une convention — et la seule chose que la calibration peut écrire
dans tout le produit est un `WatchParam` entier, pour une église.

Pas de `subject_id`, pas de cas, pas d'effet. C'est **tout** son pouvoir d'écriture.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from app.contexts.watch.domain.parameters import WatchParam

if TYPE_CHECKING:  # le port ne dépend pas de l'objet qu'il range, seulement de sa forme
    from app.contexts.watch.calibration.proposal import CalibrationProposal


class WatchParameterWriter(ABC):
    @abstractmethod
    async def set_int(self, *, tenant_id: UUID, param: WatchParam, value: int) -> None:
        """Pose la valeur de **cette église**. Ne touche jamais au défaut du produit.

        Une boucle froide qui pourrait écrire la ligne `tenant_id IS NULL` recalibrerait toutes
        les églises à partir de ce qu'une seule a vécu."""
        ...


@dataclass(frozen=True)
class AbsenceEvidence:
    """Ce qu'un cas d'absence a coûté et rapporté — **sans dire de qui il s'agissait**.

    Trois nombres et une issue. Pas d'identifiant : c'est le contrefactuel qui intéresse la
    calibration, pas la personne qu'il concernait."""

    occurrences: int  # rencontres tenues et manquées au moment du tir
    threshold: int  # le seuil **en vigueur ce jour-là**, tel que le fait le porte
    outcome: str | None  # None si le cas est encore vivant


class AbsenceEvidenceReader(ABC):
    """Le pont entre le journal et les issues, réduit à ce que la simulation a besoin de savoir.

    Il existe parce que `CheckFiredV1` écrit `occurrences` et `threshold` dans le payload du fait
    — pour rester pur, pas pour la calibration. Le contrefactuel se lit donc sans rejouer le
    moteur ; c'est le simulateur lourd qu'on n'a pas eu à construire."""

    @abstractmethod
    async def absence_evidence(
        self, *, tenant_id: UUID, since: datetime
    ) -> list[AbsenceEvidence]:
        """La fenêtre est **donnée**, jamais lue en base : la mesure et le contrefactuel doivent
        porter sur exactement les mêmes cas, donc sur exactement le même instant."""
        ...


class CalibrationProposalStore(ABC):
    """Là où les propositions attendent un humain. Une table à elles, **hors du journal**.

    C'est le troisième interdit rendu concret : une proposition n'est pas un fait. Elle n'entre
    pas au ledger, donc aucun rejeu ne la relit et aucun interpreter ne peut la transformer en
    effet. Ce que la boucle froide produit ne peut pas redescendre dans la boucle chaude
    autrement que par un `WatchParam` qu'un humain, ou une borne, a laissé passer."""

    @abstractmethod
    async def add_all(self, proposals: list["CalibrationProposal"]) -> list["CalibrationProposal"]:
        """Enregistre celles qui n'ont pas déjà une jumelle en attente. Rend les enregistrées.

        **Un seul en attente par `(église, paramètre)`.** Sans cette règle, une passe quotidienne
        empilerait trente fois la même proposition, et l'écran du pasteur deviendrait un endroit
        qu'on ferme sans lire."""
        ...

    @abstractmethod
    async def pending(self, tenant_id: UUID) -> list["CalibrationProposal"]: ...

    @abstractmethod
    async def get(
        self, *, proposal_id: UUID, tenant_id: UUID
    ) -> "CalibrationProposal | None": ...

    @abstractmethod
    async def save(self, proposal: "CalibrationProposal") -> None:
        """Persiste la décision posée sur une proposition. Rien d'autre n'est modifiable."""
        ...
