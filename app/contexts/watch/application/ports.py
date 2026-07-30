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
        owner_account_id: UUID | None = None,
    ) -> None:
        """Ouvre un cas, ou **enrichit** celui qui existe déjà. Jamais deux sur une personne.

        `owner_account_id` non nul assigne le cas dès l'ouverture. C'est ce qui permet à
        l'escalade et au garde-fou de ratio d'exister : un cas sans destinataire est un cas que
        personne ne traite, et dont personne ne répond."""
        ...

    @abstractmethod
    async def enrich_case(
        self,
        *,
        subject_id: UUID,
        tenant_id: UUID,
        source_ref: UUID,
        extend_to: datetime | None,
        annotation: str | None = None,
        priority: str | None = None,
        downgrade: bool = False,
    ) -> None:
        """Ajoute ce qu'on vient d'apprendre. L'annotation s'ajoute à la fiche, la raison
        d'origine ne bouge jamais, et la priorité ne monte que si c'est plus urgent."""
        ...

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
    async def do_not_contact_ids(self, tenant_id: UUID) -> set[UUID]:
        """Les personnes qui ont demandé qu'on cesse de les contacter.

        Une veille dont on ne peut pas sortir est un fichage. Ce retrait est absorbant et
        s'impose à **toutes** les surfaces, y compris à celles qui n'appartiennent pas au
        moteur — un rendez-vous en attente ne survit pas à cette parole."""
        ...

    @abstractmethod
    async def mark_contact_started(
        self, *, signal_id: UUID, tenant_id: UUID, at: datetime
    ) -> None:
        """L'effort est enregistré **au départ** — avant que l'application perde la main."""
        ...

    @abstractmethod
    async def origin_of(self, signal_id: UUID, tenant_id: UUID):
        """L'origine du cas — la péremption dure ne vaut que pour le régime d'échéance."""
        ...

    @abstractmethod
    async def extinguish_by_id(
        self, *, signal_id: UUID, tenant_id: UUID, cause: str, at: datetime
    ) -> None: ...

    # --- Ce que le signalement par un tiers a besoin de relire -----------------------------
    #
    # Trois lectures, et **aucune** ne prend le déclarant en argument ni ne le renvoie : elles
    # portent sur le cas, son propriétaire, son issue. « Qui a signalé qui » n'est reconstituable
    # par aucune d'elles, et c'est structurel — l'information n'est pas dans la table.

    @abstractmethod
    async def cases_of_owner(self, *, account_id: UUID, tenant_id: UUID) -> list:
        """La file d'un responsable : ses cas vivants, le plus urgent d'abord.

        Les cas `HELD` n'y figurent pas — ils sont détectés, pas encore sur ses épaules. Les
        montrer ferait mentir le plafond au moment même où il protège quelqu'un."""
        ...

    @abstractmethod
    async def get_case(self, *, signal_id: UUID, tenant_id: UUID):
        """Un cas, ou None. Le `tenant_id` est dans la signature, jamais déduit du cas."""
        ...

    @abstractmethod
    async def live_case_of(self, *, subject_id: UUID, tenant_id: UUID):
        """Le cas vivant d'une personne, ou None. **Il n'y en a jamais deux.**"""
        ...

    @abstractmethod
    async def cases_by_subjects(self, *, subject_ids, tenant_id: UUID) -> dict:
        """`{subject_id: cas vivant}` — une seule requête pour une liste de personnes.

        C'est ce qui permet à une surface d'afficher un état **dérivé du cas** sans maintenir sa
        propre liste : deux listes sur les mêmes personnes finissent par se contredire, et
        celui qui les lit ne sait plus laquelle croire."""
        ...

    @abstractmethod
    async def save_case(self, signal) -> None:
        """Persiste ce que l'agrégat a décidé. Le dépôt ne rejoue aucune règle."""
        ...

    @abstractmethod
    async def stale_concerns(
        self, *, tenant_id: UUID, opened_before: datetime
    ) -> list[tuple[UUID, UUID | None, datetime]]:
        """`(signal_id, owner_id, opened_at)` — inquiétudes vivantes sans **aucun** contact.

        Le critère est `first_contact_at IS NULL`, pas la clôture : un engagement tenu tard reste
        un engagement tenu, et ce qu'on cherche est celui que personne n'a commencé."""
        ...

    @abstractmethod
    async def concern_activity(
        self, *, tenant_id: UUID, since: datetime
    ) -> list[tuple[UUID | None, bool]]:
        """`(owner_id, contacté)` par inquiétude ouverte depuis. Le garde-fou lit un **ratio**."""
        ...

    @abstractmethod
    async def concern_outcomes(self, *, tenant_id: UUID, since: datetime) -> list[str]:
        """Les issues des inquiétudes **closes**. Agrégat de calibration, jamais nominatif."""
        ...

    @abstractmethod
    async def purge_projected(self, tenant_id: UUID) -> None:
        """Efface cas et mémoire avant un rejeu. Tout ici est reconstruit à partir des faits."""
        ...


class ScheduledCheckStore(ABC):
    """Les échéances du moteur — la seule porte par laquelle le temps entre dans la veille."""

    @abstractmethod
    async def schedule(
        self,
        *,
        subject_id: UUID,
        tenant_id: UUID,
        kind: str,
        reason: str,
        due_at: datetime,
        at: datetime,
    ) -> None:
        """Pose une échéance. Idempotent par `(sujet, kind, due_at)` — rejouer ne duplique pas."""
        ...

    @abstractmethod
    async def cancel_for(
        self, *, subject_id: UUID, tenant_id: UUID, kind: str | None, at: datetime
    ) -> int:
        """Annule les échéances en attente. `kind=None` = toutes.

        **Vital.** Sans annulation, on programme des rappels sur des gens décédés ou qui ont
        demandé qu'on cesse — l'échec le plus coûteux que ce produit puisse produire."""
        ...

    @abstractmethod
    async def due(self, *, tenant_id: UUID, now: datetime, limit: int) -> list:
        """Ce qui est dû, **les plus anciennes d'abord**, borné par le garde anti-orage."""
        ...

    @abstractmethod
    async def mark_fired(self, *, check_id: UUID, at: datetime) -> None: ...

    @abstractmethod
    async def pending_count(self, *, tenant_id: UUID, now: datetime) -> int:
        """Combien restent dues après la passe — ce qu'on doit dire plutôt que taire."""
        ...


class ContactAttemptStore(ABC):
    """Les tentatives de contact. Écrites au départ, résolues au retour — ou jamais."""

    @abstractmethod
    async def add(self, attempt) -> None: ...

    @abstractmethod
    async def get(self, attempt_id: UUID): ...

    @abstractmethod
    async def save(self, attempt) -> None: ...

    @abstractmethod
    async def count_not_reached(self, signal_id: UUID) -> int:
        """Combien de fois on a essayé sans joindre — le compteur de la péremption dure."""
        ...

    @abstractmethod
    async def pending_for(self, *, account_id: UUID, tenant_id: UUID, since: datetime) -> list:
        """Ce qu'on demandera à la réouverture, borné dans le temps."""
        ...
