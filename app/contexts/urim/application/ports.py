"""Ce dont le service d'étude a besoin, et qu'il ne sait pas faire lui-même.

La préparation persistée est **maigre par choix** : elle garde les décisions, pas la
trace. Le moteur étant déterministe à corpus constant, la trace se **rejoue** — la
stocker en dupliquerait la vérité et permettrait aux deux de diverger.

C'est aussi pourquoi `corpus_snapshot` est persisté : rejouer contre un corpus qui a
bougé doit se **voir**, pas se deviner.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol
from uuid import UUID


@dataclass(slots=True)
class PreparationRecord:
    """La préparation telle que la base la garde — **les décisions, pas le raisonnement**."""

    id: UUID
    church_id: UUID
    author_id: UUID
    raw_input: str
    entry_mode: str | None = None
    entry_origin: str | None = None
    corpus_snapshot: str | None = None

    #: Le choix du pasteur à l'étage 1, sérialisé « livre|ch|vs|ve ». Le format est un
    #: séparateur explicite et non la phrase affichée : « 1 Jean 3:16 » et « Jean 3:16 »
    #: ne se distinguent pas fiablement à la relecture d'une chaîne humaine.
    resolved_ref: str | None = None

    pericope_id: UUID | None = None
    bounds_overridden: bool = False
    version_id: UUID | None = None
    axis_code: str | None = None
    plan_source: str | None = None
    subject_matter: str | None = None
    theme: str | None = None
    service_date: date | None = None
    service_timezone: str = "Africa/Abidjan"
    status: str = "ouverte"
    opened_at: datetime | None = None
    closed_at: datetime | None = None


@dataclass(slots=True)
class ElementRecord:
    """Un champ du squelette homilétique — libre, jamais imposé."""

    element_code: str
    ordinal: int
    body: str | None = None


@dataclass(slots=True)
class UsageSnapshot:
    """L'état du plafond d'une église à l'instant de la demande.

    `ceiling_reached` est la seule chose que le moteur en voit : il ne connaît ni le
    décompte ni le quota, il sait seulement s'il doit se replier sur le domaine public."""

    window_id: UUID | None = None
    metered_units: int = 0
    ceiling: int = 0
    ceiling_reached: bool = False


@dataclass(slots=True)
class StudyDTO:
    """Ce que le pasteur voit — la trace **rejouée**, pas relue."""

    record: PreparationRecord
    outcome: str
    rationale: str
    trace: tuple[tuple[str, str], ...] = ()
    options: tuple[tuple[str, str, str], ...] = ()
    elements: tuple[ElementRecord, ...] = ()
    resolved_label: str | None = None
    #: Vrai quand le corpus a bougé depuis l'ouverture — la trace affichée n'est plus
    #: celle qui a été produite ce jour-là, et le pasteur doit le savoir.
    corpus_drifted: bool = False


class StudyRepository(Protocol):
    async def add(self, record: PreparationRecord) -> None: ...

    async def get(self, study_id: UUID) -> PreparationRecord | None: ...

    async def save(self, record: PreparationRecord) -> None: ...

    async def record_attempt(
        self,
        *,
        study_id: UUID,
        input_hash: str,
        candidates: list[str],
        chosen_ref: str | None,
        chosen_by: str | None,
        at: datetime,
    ) -> None:
        """Trace d'une résolution — `chosen_by` dit **qui** a tranché, moteur ou pasteur.

        Ce n'est pas de la journalisation : c'est la provenance. Une référence choisie par
        le moteur et une référence choisie par le pasteur n'ont pas la même autorité, et
        rien d'autre dans le schéma ne les distingue."""
        ...

    async def set_elements(self, study_id: UUID, elements: list[ElementRecord]) -> None: ...

    async def list_elements(self, study_id: UUID) -> list[ElementRecord]: ...

    async def recently_preached_axes(self, author_id: UUID, since: date) -> list[str]: ...


class PreacherAuthorization(Protocol):
    """A-t-on le droit de préparer dans cette église ?

    Un **port**, et pas un appel direct à la politique d'accès partagée : le cœur d'Urim
    n'importe rien des autres contextes, et c'est un test d'architecture qui le tient, pas
    une intention. La question posée ici est volontairement pauvre — *cette personne
    peut-elle préparer ici ?* — pour qu'aucune notion de rôle, de groupe ou de hiérarchie
    ne s'infiltre dans le raisonnement d'Urim.
    """

    async def ensure_may_prepare(self, *, account_id: UUID, church_id: UUID) -> None:
        """Laisse passer, ou lève. Le silence vaut autorisation."""
        ...


class ReservationPort(Protocol):
    """La réservation d'étude (§6) — ce qui empêche de facturer deux fois le même travail."""

    async def reserve(
        self, *, church_id: UUID, author_id: UUID, pericope_key: str, at: datetime
    ) -> UUID:
        """Réserve sous une clé **provisoire** — celle de la saisie, faute de mieux."""
        ...

    async def rekey_for(
        self, *, church_id: UUID, provisional_key: str, pericope_key: str, at: datetime
    ) -> None:
        """Re-clé sur la péricope réellement résolue (S9).

        C'est le geste qui rend la réservation juste. À l'ouverture, on ne sait pas encore
        sur quel texte on travaille : la clé provisoire est la saisie brute, et deux
        formulations du même passage (« 2 Co 5.17 » et « une nouvelle créature ») en
        produisent deux différentes. Une fois la péricope résolue, les deux se rejoignent
        — et la seconde réservation se libère au lieu d'être comptée.

        On retrouve la réservation par sa **clé provisoire** et non par son identifiant :
        la table ne porte pas de lien vers la préparation, et la clé dérive de la saisie,
        donc elle est stable d'un appel à l'autre. C'est le seul fil qui relie les deux."""
        ...

    async def usage(self, church_id: UUID, at: datetime) -> UsageSnapshot: ...
