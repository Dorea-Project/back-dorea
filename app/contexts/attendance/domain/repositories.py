"""Ports de persistance du contexte Présence (M6)."""

from abc import abstractmethod
from datetime import datetime
from uuid import UUID

from app._shared.domain.repository import Repository
from app.contexts.attendance.domain.aggregates import AttendanceRecord, Gathering
from app.contexts.attendance.domain.cadence import (
    CadenceAcknowledgement,
    ChurchSuspension,
    GroupCadence,
)
from app.contexts.attendance.domain.planned_absence import PlannedAbsence
from app.contexts.attendance.domain.rsvp import GatheringRsvp
from app.contexts.attendance.domain.visitor import Visitor
from app.contexts.attendance.domain.watch_exclusion import WatchExclusion


class GatheringRsvpRepository(Repository):
    @abstractmethod
    async def set_for(self, rsvp: GatheringRsvp) -> None:
        """Pose un « je viens » (idempotent : une ligne par rencontre et compte)."""
        ...

    @abstractmethod
    async def remove(self, gathering_id: UUID, account_id: UUID) -> None:
        """Retire le « je viens » (se rétracter)."""
        ...

    @abstractmethod
    async def list_account_ids_for(self, gathering_id: UUID) -> set[UUID]:
        """Les comptes ayant dit venir à cette rencontre (pré-remplit le roster)."""
        ...


class GatheringRepository(Repository):
    @abstractmethod
    async def add(self, gathering: Gathering) -> None: ...

    @abstractmethod
    async def get(self, gathering_id: UUID) -> Gathering | None: ...

    @abstractmethod
    async def get_open_by_check_in_code(self, code: str) -> Gathering | None:
        """Résout une rencontre **ouverte** par son code de séance (self-check-in, M6-1)."""
        ...

    @abstractmethod
    async def list_by_group(self, group_id: UUID) -> list[Gathering]:
        """Rencontres d'un groupe, triées par date (M7 — trajectoire)."""
        ...

    @abstractmethod
    async def save(self, gathering: Gathering) -> None:
        """Persiste un état existant (ex. après clôture)."""
        ...


class AttendanceRecordRepository(Repository):
    @abstractmethod
    async def add(self, record: AttendanceRecord) -> None: ...

    @abstractmethod
    async def get_for(self, gathering_id: UUID, account_id: UUID) -> AttendanceRecord | None:
        """Signal existant pour (rencontre, compte), ou None (idempotence)."""
        ...

    @abstractmethod
    async def remove(self, gathering_id: UUID, account_id: UUID) -> None:
        """Retire le signal (dé-pointer)."""
        ...

    @abstractmethod
    async def list_for_gathering(self, gathering_id: UUID) -> list[AttendanceRecord]:
        """Tous les signaux d'une rencontre (présents + excusés)."""
        ...

    @abstractmethod
    async def list_present_for_gatherings(
        self, gathering_ids: list[UUID]
    ) -> list[AttendanceRecord]:
        """Présences sur un ensemble de rencontres (M7 — trajectoire d'un groupe)."""
        ...

    @abstractmethod
    async def has_present_in_other_tenant_since(
        self, account_id: UUID, tenant_id: UUID, since: datetime
    ) -> bool:
        """Le compte a-t-il été **présent dans une AUTRE église** du réseau depuis `since` ?

        Signal « actif ailleurs » (Mme Richmond) — booléen seul, **ne révèle pas où**
        (isolation des églises). S'appuie sur le compte global (M7 §3)."""
        ...


class PlannedAbsenceRepository(Repository):
    @abstractmethod
    async def add(self, absence: PlannedAbsence) -> None: ...

    @abstractmethod
    async def get(self, absence_id: UUID) -> PlannedAbsence | None: ...

    @abstractmethod
    async def save(self, absence: PlannedAbsence) -> None:
        """Persiste un état existant (ex. après annulation)."""
        ...

    @abstractmethod
    async def list_active_by_tenant(self, tenant_id: UUID) -> list[PlannedAbsence]:
        """Absences non annulées d'un tenant (le roster filtre par date en mémoire)."""
        ...

    @abstractmethod
    async def list_active_by_account(
        self, account_id: UUID, tenant_id: UUID
    ) -> list[PlannedAbsence]:
        """Absences non annulées d'un compte dans un tenant (« mes absences »)."""
        ...

    @abstractmethod
    async def get_by_source(
        self, account_id: UUID, source_ref: UUID
    ) -> PlannedAbsence | None:
        """La neutralisation déjà posée par cette annonce sur cette personne, ou None.

        Clé d'idempotence `(annonce, personne)` : rejouer une annonce ne crée pas un doublon."""
        ...

    @abstractmethod
    async def list_open_neutralizations(
        self, account_id: UUID, tenant_id: UUID
    ) -> list[PlannedAbsence]:
        """Neutralisations en cours sur cette personne — celles qu'une nouvelle annonce prolonge.

        Les absences que le membre a déclarées lui-même ne sont pas là : sa parole n'est pas
        écrasée par une annonce faite sur lui."""
        ...

    @abstractmethod
    async def list_open_neutralizations_by_tenant(
        self, tenant_id: UUID
    ) -> list[PlannedAbsence]:
        """Toutes les neutralisations en cours d'une église — celles que le moteur a posées."""
        ...

    @abstractmethod
    async def list_open_explanations(
        self, account_id: UUID, tenant_id: UUID
    ) -> list[PlannedAbsence]:
        """Tout ce qui **explique** le silence de cette personne — les deux origines.

        Deux questions différentes vivaient sous le même mot, et elles ont fini par se contredire :

        - *« quelles lignes le moteur a-t-il posées ? »* — pour les prolonger sans cumuler, et pour
          savoir ce qu'une reprojection a le droit d'effacer. La réponse est `ANNOUNCEMENT` seul, et
          c'est `list_open_neutralizations` ;
        - *« sait-on pourquoi cette personne n'est pas là ? »* — la seule question que la veille
          pose réellement. La réponse est **les deux origines**, et c'est cette méthode-ci.

        Confondre les deux avait un effet précis : le membre qui prend la peine de dire *« je pars
        du 5 au 20 »* recevait quand même *« sans nouvelles — 3 rencontres »*. Le roster honorait la
        dignité de prévenir, la veille l'ignorait — et c'est justement à celui qui a prévenu qu'on
        allait demander pourquoi il n'était pas venu."""
        ...

    @abstractmethod
    async def list_open_explanations_by_tenant(
        self, tenant_id: UUID
    ) -> list[PlannedAbsence]:
        """Toutes les explications en cours d'une église — **la vue que lit le moteur**."""
        ...

    @abstractmethod
    async def delete_projected(self, tenant_id: UUID) -> None:
        """Supprime les neutralisations **posées par le moteur**, avant un rejeu du ledger.

        Seule méthode autorisée à effacer du projeté, et elle ne touche jamais à une absence
        déclarée par le membre : une reconstruction ne doit pas pouvoir effacer sa parole."""
        ...


class WatchExclusionRepository(Repository):
    """Le retrait définitif de la veille (décès). Absorbant : aucune méthode ne le lève."""

    @abstractmethod
    async def add(self, exclusion: WatchExclusion) -> None: ...

    @abstractmethod
    async def get_for(self, account_id: UUID, tenant_id: UUID) -> WatchExclusion | None:
        """L'exclusion de cette personne dans cette église, ou None (idempotence)."""
        ...

    @abstractmethod
    async def excluded_account_ids(self, tenant_id: UUID) -> set[UUID]:
        """Les comptes hors veille d'une église — filtre appliqué en tête de tout calcul M7."""
        ...

    @abstractmethod
    async def delete_all(self, tenant_id: UUID) -> None:
        """Vide les exclusions d'une église avant un rejeu du ledger.

        L'exclusion est une projection : elle se reconstruit intégralement à partir des faits.
        Réservé à la reprojection — il n'existe pas d'opération métier pour lever une exclusion."""
        ...


class VisitorRepository(Repository):
    @abstractmethod
    async def add(self, visitor: Visitor) -> None: ...

    @abstractmethod
    async def get(self, visitor_id: UUID) -> Visitor | None: ...

    @abstractmethod
    async def remove(self, visitor_id: UUID) -> None: ...

    @abstractmethod
    async def list_for_gathering(self, gathering_id: UUID) -> list[Visitor]:
        """Les visages nouveaux capturés à une rencontre (M6-3)."""
        ...


class GroupCadenceRepository(Repository):
    """Le rythme attendu d'un groupe — le `Programme` (P1)."""

    @abstractmethod
    async def add(self, cadence: GroupCadence) -> None: ...

    @abstractmethod
    async def get_active_by_group(self, group_id: UUID) -> GroupCadence | None:
        """La cadence non annulée d'un groupe (au plus une), ou None."""
        ...

    @abstractmethod
    async def save(self, cadence: GroupCadence) -> None:
        """Persiste un état existant (ex. après annulation)."""
        ...


class CadenceAcknowledgementRepository(Repository):
    """Les occurrences attendues **acquittées** (non tenues, motif connu) — P1."""

    @abstractmethod
    async def add(self, ack: CadenceAcknowledgement) -> None: ...

    @abstractmethod
    async def get_for(
        self, group_id: UUID, occurrence_date: datetime
    ) -> CadenceAcknowledgement | None:
        """Acquittement existant pour (groupe, occurrence), ou None (idempotence)."""
        ...

    @abstractmethod
    async def list_by_group(self, group_id: UUID) -> list[CadenceAcknowledgement]:
        """Tous les acquittements d'un groupe (l'état d'occurrence filtre par date en mémoire)."""
        ...


class ChurchSuspensionRepository(Repository):
    """Les suspensions église (Noël, deuil) qui acquittent en cascade — P1."""

    @abstractmethod
    async def add(self, suspension: ChurchSuspension) -> None: ...

    @abstractmethod
    async def get(self, suspension_id: UUID) -> ChurchSuspension | None: ...

    @abstractmethod
    async def save(self, suspension: ChurchSuspension) -> None:
        """Persiste un état existant (ex. après annulation)."""
        ...

    @abstractmethod
    async def list_active_by_tenant(self, tenant_id: UUID) -> list[ChurchSuspension]:
        """Suspensions non annulées d'un tenant (la cascade est calculée à la lecture)."""
        ...
