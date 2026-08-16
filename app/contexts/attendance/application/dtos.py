"""DTO applicatifs du contexte Présence (M6)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class GatheringDTO:
    id: UUID
    tenant_id: UUID
    group_id: UUID | None
    type: str
    title: str | None
    scheduled_at: datetime
    status: str
    check_in_code: str | None  # code de séance à afficher (self-check-in, M6-1)


@dataclass(frozen=True)
class SelfCheckInDTO:
    gathering_id: UUID
    group_id: UUID | None
    title: str | None
    #: Le **type** voyage avec le titre, et c'est indispensable depuis que le culte
    #: n'écrit plus « Culte » en base : un titre nul se nomme par son type, dans la
    #: langue du lecteur, côté client. Sans lui la rencontre serait sans nom.
    type: str = "service"


@dataclass(frozen=True)
class RosterEntryDTO:
    account_id: UUID
    present: bool
    excused: bool  # absence pre-declaree (M6-2) ; absent = ni present ni excuse
    rsvp: bool  # a dit « je viens » (pre-signal M8) ; le present l'emporte a l'affichage


@dataclass(frozen=True)
class RosterDTO:
    gathering_id: UUID
    status: str
    total_expected: int
    present_count: int
    excused_count: int
    rsvp_count: int  # combien ont dit venir (roster + hors-roster)
    entries: list[RosterEntryDTO]


@dataclass(frozen=True)
class PlannedAbsenceDTO:
    id: UUID
    account_id: UUID
    tenant_id: UUID
    reason: str
    gravity: str  # poids du tag (transient/watch/structural) — crochet effectif M7
    note: str | None
    from_date: datetime
    to_date: datetime


@dataclass(frozen=True)
class VisitorDTO:
    id: UUID
    gathering_id: UUID
    name: str
    phone: str | None


@dataclass(frozen=True)
class ConvertVisitorResult:
    """L'entonnoir bouclé : le visage capturé devient membre (invited) + inscrit dans sa cellule."""

    account_id: UUID
    tenant_id: UUID
    group_id: UUID
    status: str  # invited (début du parcours membre)
    reused_account: bool  # le téléphone existait déjà (compte global réutilisé, M-2)


@dataclass(frozen=True)
class PulseEntryDTO:
    account_id: UUID
    state: str  # new / engaged / at_risk / shared / dormant
    missed: int  # silence concerné (rencontres absentes depuis la dernière venue)
    needs_care: bool  # à interpeller (at_risk ou dormant)
    last_present_at: datetime | None


@dataclass(frozen=True)
class GroupPulseDTO:
    group_id: UUID
    total: int
    needs_care_count: int
    entries: list[PulseEntryDTO]


@dataclass(frozen=True)
class ReviewCandidateDTO:
    account_id: UUID
    reason: str  # prolonged_silence (dormant) | declared_moved (gravité structural)


@dataclass(frozen=True)
class GroupEffectifDTO:
    group_id: UUID
    total_members: int  # inscrits (roster)
    active_count: int  # effectif reel vivant (hors dormants et demenages)
    at_risk_count: int
    shared_count: int  # a cheval sur une autre eglise (Mme Richmond)
    review_candidates: list[ReviewCandidateDTO]  # suggestions, jamais automatique


@dataclass(frozen=True)
class CareEntryDTO:
    account_id: UUID
    group_id: UUID
    group_name: str
    state: str  # at_risk | dormant
    missed: int
    last_present_at: datetime | None


@dataclass(frozen=True)
class CareListDTO:
    tenant_id: UUID
    count: int
    entries: list[CareEntryDTO]  # « à interpeller » sur toute l'eglise, plus silencieux d'abord


@dataclass(frozen=True)
class CellHealthDTO:
    group_id: UUID
    type: str
    roster_count: int  # inscrits
    active_count: int  # presents reels (M7)
    ready_to_multiply: bool  # cellule ET presents reels >= seuil (honnete, M7-3)


@dataclass(frozen=True)
class GroupVitalsDTO:
    """Carte d'un groupe : ses **infos** + ses **realites** (mobile detail & grille backoffice)."""

    group_id: UUID
    name: str
    type: str
    status: str
    generation: int
    roster_count: int  # inscrits
    active_count: int  # presents reels
    at_risk_count: int
    shared_count: int
    review_count: int  # candidats a revoir (dormants + demenages)
    ready_to_multiply: bool


@dataclass(frozen=True)
class TrajectoryPointDTO:
    gathering_id: UUID
    scheduled_at: datetime
    outcome: str  # present | excused | absent
    title: str | None
    #: Le **type** voyage avec le titre, et c'est indispensable depuis que le culte
    #: n'écrit plus « Culte » en base : un titre nul se nomme par son type, dans la
    #: langue du lecteur, côté client. Sans lui la rencontre serait sans nom.
    type: str = "service"


@dataclass(frozen=True)
class MemberTrajectoryDTO:
    """La frise d'un membre : l'histoire tendue a l'humain avant la conversation de soin."""

    account_id: UUID
    group_id: UUID
    state: str  # new | engaged | at_risk | shared | dormant
    needs_care: bool
    missed: int
    last_present_at: datetime | None
    active_elsewhere: bool  # actif dans une autre eglise (sans reveler ou)
    current_absence_reason: str | None  # a-t-il prevenu ? (tag M6-2)
    current_absence_gravity: str | None
    points: list[TrajectoryPointDTO]  # chronologique, depuis son adhesion


@dataclass(frozen=True)
class TrendPointDTO:
    as_of: datetime
    roster_count: int  # inscrits a cette date (arrives seulement)
    active_count: int  # presents reels a cette date
    at_risk_count: int


@dataclass(frozen=True)
class GroupTrendDTO:
    """La derivee du groupe : monte-t-il ou fond-il ? (momentum, pas photo)."""

    group_id: UUID
    points: list[TrendPointDTO]  # chronologique, une par periode (plus ancien d'abord)


@dataclass(frozen=True)
class ChurchDashboardDTO:
    """Le cockpit du pasteur : la grille de tous les groupes + les totaux qui aident a decider."""

    tenant_id: UUID
    groups_count: int
    cells_ready_to_multiply: int
    members_needing_care: int  # comptes distincts a interpeller (dedupliques)
    groups: list[GroupVitalsDTO]


@dataclass(frozen=True)
class LineageNodeDTO:
    """Un noeud de la foret de reproduction : une cellule + les filles qu'elle a enfantees."""

    vitals: GroupVitalsDTO
    children: list[LineageNodeDTO]  # cellules-filles (via multiplied_from_id)


@dataclass(frozen=True)
class MultiplicationTreeDTO:
    """La vision cellulaire rendue visible : qui enfante qui, la fertilite par generation."""

    tenant_id: UUID
    cells_count: int
    max_generation: int  # profondeur de reproduction atteinte
    roots: list[LineageNodeDTO]  # cellules souches (sans mere active connue)


# --- Fondation A (P1) : cadence attendue / couverture ---


@dataclass(frozen=True)
class GroupCadenceDTO:
    id: UUID
    group_id: UUID
    frequency: str  # weekly | biweekly | monthly
    weekday: int | None
    day_of_month: int | None
    anchor_date: datetime
    active_from: datetime
    active_until: datetime | None


@dataclass(frozen=True)
class CadenceAcknowledgementDTO:
    id: UUID
    group_id: UUID
    occurrence_date: datetime
    reason: str  # holiday | leader_absent | venue_unavailable | other


@dataclass(frozen=True)
class ChurchSuspensionDTO:
    id: UUID
    tenant_id: UUID
    reason: str  # holiday | national_mourning | other
    from_date: datetime
    to_date: datetime


@dataclass(frozen=True)
class CoverageOccurrenceDTO:
    occurrence_at: datetime
    state: str  # saisie | acquittee | silencieuse


@dataclass(frozen=True)
class GroupCoverageDTO:
    """La couverture d'un groupe sur une fenêtre : combien d'occurrences saisies / acquittées /
    silencieuses. `silencieuse` = trou de veille. `has_cadence=False` → veille aveugle sur ce
    groupe (aucun rythme déclaré). L'émission d'alerte est P2 ; ceci n'est que le calcul."""

    group_id: UUID
    from_date: datetime
    to_date: datetime
    has_cadence: bool
    expected_count: int
    saisie_count: int
    acquittee_count: int
    silencieuse_count: int
    occurrences: list[CoverageOccurrenceDTO]
