"""Le `Signal` — un **cas ouvert**, et la machine à états qui le gouverne.

Fermée, versionnée, non extensible par greffon. Les règles ne sont pas des validations que la
couche applicative pense à appeler : elles sont **dans les transitions**. Une transition qui
n'existe pas ne peut pas être tentée.

Un signal matérialise un cas — pas un statut de personne. Personne n'est « à risque » : il y a
un cas ouvert sur elle, et il se ferme. Cette nuance est tout le produit.

Quatre règles compilées ici :

- **`CLOSED` exige un acte humain**, sauf pour les causes système (§ `SYSTEM_CLOSURE_CAUSES`) —
  celles où le cas n'était pas réel, et où l'on ne demande pas à un responsable de fermer à la
  main une erreur du système ;
- **`DO_NOT_CONTACT` et `DECEASED` sont absorbants** : aucune transition sortante n'existe ;
- **la `reason` est écrite à l'ouverture et jamais réécrite.** Enrichir ajoute une source, pas
  une phrase — un motif reformulé six semaines plus tard ne dit plus la même chose ;
- **`RETRACTED` n'est pas `CLOSED`.** Un signal rétracté est un signal devenu faux, pas un cas
  résolu ; il n'entre dans aucune métrique de résolution.

`HELD` mérite un mot : c'est l'état d'un cas **détecté mais non émis**, retenu par le plafond de
débit. Il est distinct d'`OPEN` parce que confondre les deux ferait mentir toutes les mesures —
et parce qu'un cas retenu doit être réévalué chaque nuit, pas oublié.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from app._shared.domain.entity import AggregateRoot
from app.contexts.watch.domain.effects import (
    SYSTEM_CLOSURE_CAUSES,
    CasePriority,
    ExtinguishCause,
)
from app.contexts.watch.domain.errors import (
    AbsorbingOutcomeError,
    HumanClosureRequiredError,
    InvalidSignalTransitionError,
)


class SignalStatus(StrEnum):
    HELD = "held"  # détecté, retenu par le plafond — réévalué chaque nuit
    OPEN = "open"  # émis, sans propriétaire
    ASSIGNED = "assigned"  # confié à quelqu'un
    IN_CONTACT = "in_contact"  # le contact a commencé
    CLOSED = "closed"  # terminé, avec une issue stockée
    RETRACTED = "retracted"  # devenu faux — hors métriques de résolution


class SignalOutcome(StrEnum):
    """Liste **close**. On n'invente pas une issue pour ranger un cas gênant."""

    RESTORED = "restored"  # revenu(e)
    FOLLOWED = "followed"  # suivi(e), le lien tient
    CHANGED_CHURCH = "changed_church"
    UNREACHABLE_ARCHIVED = "unreachable_archived"
    KNOWN_AND_FOLLOWED = "known_and_followed"  # on sait, quelqu'un s'en occupe déjà
    NO_RETURN = "no_return"  # l'échéance est passée, pas de retour constaté
    # « J'ai pris contact, tout allait bien. » Sans cette issue, la calibration du signalement
    # par un tiers ne veut rien dire : aucune autre ne permet de distinguer une intuition juste
    # d'une intuition fausse, et le taux de justesse mesurerait le vide.
    NOTHING_TO_REPORT = "nothing_to_report"
    EPISODE_NO_GESTURE = "episode_no_gesture"  # l'épisode a expiré sans qu'un geste soit posé
    EXPLAINED_BY_ANNOUNCEMENT = "explained_by_announcement"  # clôture système
    DECEASED = "deceased"  # absorbant
    DO_NOT_CONTACT = "do_not_contact"  # absorbant — la personne a demandé qu'on cesse
    # Un défaut de couverture ne se résout pas par un contact, mais par une **désignation**.
    DESIGNATED = "designated"


# Absorbants : une fois posés, plus aucune transition. Ce ne sont pas des états « terminés »
# comme les autres — ce sont des portes fermées à clé, sur demande ou par la mort.
ABSORBING_OUTCOMES: frozenset[SignalOutcome] = frozenset(
    {SignalOutcome.DECEASED, SignalOutcome.DO_NOT_CONTACT}
)


_OUTCOME_OF_CAUSE: dict[ExtinguishCause, SignalOutcome] = {
    ExtinguishCause.EXPLAINED_BY_ANNOUNCEMENT: SignalOutcome.EXPLAINED_BY_ANNOUNCEMENT,
    ExtinguishCause.RETURNED: SignalOutcome.RESTORED,
    ExtinguishCause.DECEASED: SignalOutcome.DECEASED,
    ExtinguishCause.UNREACHABLE: SignalOutcome.UNREACHABLE_ARCHIVED,
}


# Les transitions qui existent. Tout le reste est refusé — pas validé, refusé.
_TRANSITIONS: dict[SignalStatus, frozenset[SignalStatus]] = {
    # `HELD → ASSIGNED` existe depuis que tout cas naît avec un destinataire : un cas retenu qu'on
    # relâche n'a pas à repasser par `OPEN`, où il attendrait qu'on le lui attribue une seconde
    # fois. `OPEN` reste la place d'un cas relâché dont le propriétaire aurait disparu entre-temps.
    SignalStatus.HELD: frozenset(
        {SignalStatus.OPEN, SignalStatus.ASSIGNED, SignalStatus.RETRACTED}
    ),
    SignalStatus.OPEN: frozenset(
        {SignalStatus.ASSIGNED, SignalStatus.CLOSED, SignalStatus.RETRACTED}
    ),
    SignalStatus.ASSIGNED: frozenset(
        {SignalStatus.IN_CONTACT, SignalStatus.CLOSED, SignalStatus.RETRACTED}
    ),
    SignalStatus.IN_CONTACT: frozenset({SignalStatus.CLOSED, SignalStatus.RETRACTED}),
    SignalStatus.CLOSED: frozenset(),  # terminal
    SignalStatus.RETRACTED: frozenset(),  # terminal
}

# L'urgence vient de l'**origine du dire**, jamais d'une gravité supposée. Plus le rang est
# petit, plus c'est urgent — le déclaré passe devant tout.
_PRIORITY_RANK: dict[CasePriority, int] = {
    CasePriority.DECLARED: 0,
    CasePriority.DEADLINE: 1,
    CasePriority.ANNOUNCEMENT: 2,
    # La parole d'un tiers : plus qu'une absence calculée, moins que celle de l'intéressé.
    CasePriority.CONCERN: 3,
    CasePriority.ABSENCE: 4,
}


LIVE_STATUSES: frozenset[SignalStatus] = frozenset(
    {SignalStatus.HELD, SignalStatus.OPEN, SignalStatus.ASSIGNED, SignalStatus.IN_CONTACT}
)

# Ce qui pèse réellement sur quelqu'un. `HELD` en est exclu : un cas retenu est détecté, pas
# encore confié — l'afficher dans la file ferait mentir le plafond au moment même où il protège.
ON_SHOULDERS_STATUSES: frozenset[SignalStatus] = frozenset(
    {SignalStatus.OPEN, SignalStatus.ASSIGNED, SignalStatus.IN_CONTACT}
)


# Ce que l'issue précédente dit, en clair et sans jargon, à qui rouvre un cas. Court exprès :
# la phrase s'ajoute à la raison, elle ne la remplace pas.
_OUTCOME_LABELS: dict[SignalOutcome, str] = {
    SignalOutcome.RESTORED: "retour constaté",
    SignalOutcome.FOLLOWED: "repris contact, situation suivie",
    SignalOutcome.CHANGED_CHURCH: "a rejoint une autre église",
    SignalOutcome.UNREACHABLE_ARCHIVED: "resté sans réponse",
    SignalOutcome.KNOWN_AND_FOLLOWED: "déjà suivi par quelqu'un",
    SignalOutcome.NO_RETURN: "pas de retour constaté",
    SignalOutcome.EPISODE_NO_GESTURE: "aucun geste posé",
    SignalOutcome.NOTHING_TO_REPORT: "contact pris, rien à signaler",
    SignalOutcome.EXPLAINED_BY_ANNOUNCEMENT: "expliqué par une annonce",
    SignalOutcome.DECEASED: "décès",
    SignalOutcome.DO_NOT_CONTACT: "a demandé qu'on cesse",
    SignalOutcome.DESIGNATED: "un référent a été désigné",
}

_MONTHS: tuple[str, ...] = (
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
)


def _spoken_date(at: datetime) -> str:
    """« 3 février » — une date qui se lit, pas un horodatage qu'on déchiffre."""
    day = "1er" if at.day == 1 else str(at.day)
    return f"{day} {_MONTHS[at.month - 1]}"


class Signal(AggregateRoot):
    def __init__(
        self,
        *,
        id: UUID,
        tenant_id: UUID,
        subject_id: UUID,
        origin: CasePriority,
        reason: str,
        opened_at: datetime,
        status: SignalStatus = SignalStatus.OPEN,
        expires_at: datetime | None = None,
        # Le destinataire. Nul reste **techniquement** admis pour relire une ligne d'avant le
        # 30/07/2026, mais plus aucun chemin n'en écrit : un cas sans destinataire est un cas que
        # personne ne traite, et que n'importe quel responsable de la portée pouvait s'attribuer,
        # donc lire. C'est le référent qui peut être nul, jamais le propriétaire d'un cas.
        owner_account_id: UUID | None = None,
        source_refs: list[UUID] | None = None,
        priority: CasePriority | None = None,  # à défaut, celle de l'origine
        annotations: list[str] | None = None,
        gestures_count: int = 0,
        first_seen_at: datetime | None = None,
        first_contact_at: datetime | None = None,
        episode_id: UUID | None = None,  # à défaut, le cas ouvre son propre épisode
        occurrence_number: int = 1,
        previous_outcome: SignalOutcome | None = None,
        previous_closed_at: datetime | None = None,
        outcome: SignalOutcome | None = None,
        closed_at: datetime | None = None,
        closed_by_account_id: UUID | None = None,
        retracted_at: datetime | None = None,
        held_reason: str | None = None,
    ) -> None:
        super().__init__()
        self.id = id
        self.tenant_id = tenant_id
        self.subject_id = subject_id
        self.origin = origin
        self._reason = reason  # privé : immuable après l'ouverture
        self.opened_at = opened_at
        self.status = status
        self.expires_at = expires_at
        self.owner_account_id = owner_account_id
        self.source_refs = source_refs or []
        self.priority = priority or origin
        # Ce qu'on a **appris depuis** l'ouverture. Ajouté, jamais substitué à la raison :
        # « Absente depuis 4 semaines. » puis « A annulé le rendez-vous qu'elle avait demandé. »
        self.annotations = annotations or []
        # Les deux métriques du pilote. `first_seen_at` alimente le taux d'ignorés — le seul
        # indicateur qui **anticipe** l'abandon ; `first_contact_at` le délai détection → contact.
        self.first_seen_at = first_seen_at
        self.first_contact_at = first_contact_at
        # L'**épisode** : la chaîne des cas successifs sur une même personne. Il n'existe que
        # pour une raison — la réouverture. Sans lui, le troisième cas d'affilée s'affiche comme
        # le premier, et le responsable qui a déjà appelé deux fois recommence de zéro. Trois
        # champs suffisent à produire la phrase ; on n'a pas construit une histoire complète.
        self.episode_id = episode_id or id
        self.occurrence_number = occurrence_number
        self.previous_outcome = previous_outcome
        self.previous_closed_at = previous_closed_at
        self.gestures_count = gestures_count
        self.outcome = outcome
        self.closed_at = closed_at
        self.closed_by_account_id = closed_by_account_id
        self.retracted_at = retracted_at
        # Pourquoi il est retenu : le plafond du responsable, ou le rodage de l'église.
        self.held_reason = held_reason

    # --- Lecture ---

    @property
    def reason(self) -> str:
        """Écrite à l'ouverture, jamais réécrite. Il n'existe pas de setter."""
        return self._reason

    @property
    def is_live(self) -> bool:
        return self.status in LIVE_STATUSES

    @property
    def is_held(self) -> bool:
        return self.status is SignalStatus.HELD

    @property
    def is_absorbing(self) -> bool:
        return self.outcome in ABSORBING_OUTCOMES

    @property
    def is_reopening(self) -> bool:
        return self.occurrence_number > 1

    @property
    def previous_case_note(self) -> str | None:
        """« Cas précédent clos le 3 février — repris contact, situation suivie. »

        Elle s'**ajoute** à la raison, elle ne la remplace pas : le motif d'aujourd'hui reste
        celui d'aujourd'hui. Ce que cette phrase évite est très concret — rappeler quelqu'un en
        ouvrant par « je vois que tu n'es pas venue » alors qu'on lui a déjà parlé en février.

        Une rétractation n'en produit aucune : un cas devenu faux n'a rien à transmettre."""
        if self.previous_outcome is None or self.previous_closed_at is None:
            return None
        return (
            f"Cas précédent clos le {_spoken_date(self.previous_closed_at)} — "
            f"{_OUTCOME_LABELS[self.previous_outcome]}."
        )

    @property
    def counts_as_resolved(self) -> bool:
        """Une rétraction n'entre dans aucune métrique de résolution : elle n'a rien résolu."""
        return self.status is SignalStatus.CLOSED

    # --- Transitions ---

    def _move_to(self, target: SignalStatus) -> None:
        if self.is_absorbing:
            raise AbsorbingOutcomeError(
                "Cette issue est absorbante : aucune transition n'en sort.",
                details={"outcome": self.outcome.value if self.outcome else None},
            )
        if target not in _TRANSITIONS[self.status]:
            raise InvalidSignalTransitionError(
                "Cette transition n'existe pas.",
                details={"from": self.status.value, "to": target.value},
            )
        self.status = target

    def release(self) -> None:
        """Le plafond s'est desserré : le cas retenu devient visible.

        Ne relâche **que** ce que le plafond retient — la passe nocturne le vérifie avant
        d'appeler. Relâcher un cas retenu par le rodage ferait parler toute seule, pendant la
        nuit, une église qui observait.

        Il va directement chez son destinataire — il en a un depuis son ouverture. Le faire passer
        par `OPEN` le rendrait « prenable » par n'importe quel responsable de la portée, ce qui est
        exactement la porte qu'on a fermée en rendant le propriétaire obligatoire."""
        self._move_to(
            SignalStatus.ASSIGNED if self.owner_account_id is not None else SignalStatus.OPEN
        )
        self.held_reason = None

    def see(self, *, at: datetime) -> None:
        """Le propriétaire a **ouvert** le cas. Un cas jamais ouvert est le vrai signal d'alarme
        du produit : il monte *avant* l'abandon, quand tout le reste a encore l'air normal."""
        if self.first_seen_at is None:
            self.first_seen_at = at

    def assign(self, *, owner_account_id: UUID) -> None:
        self._move_to(SignalStatus.ASSIGNED)
        self.owner_account_id = owner_account_id

    def record_contact_attempt(self, *, at: datetime) -> None:
        """L'intention est écrite **avant** que l'application perde la main.

        Si le responsable ne revient jamais dire ce qui s'est passé, on saura au moins qu'il a
        essayé — et le produit ne conclura pas à un échec là où il y a eu un appel."""
        self.see(at=at)
        if self.first_contact_at is None:
            self.first_contact_at = at
        if self.status is SignalStatus.ASSIGNED:
            self._move_to(SignalStatus.IN_CONTACT)

    def start_contact(self) -> None:
        self._move_to(SignalStatus.IN_CONTACT)

    def record_gesture(self) -> None:
        """Un geste réel posé. Compté **par cas**, jamais par membre — un compteur par personne
        deviendrait un classement des bons et des mauvais."""
        self.gestures_count += 1

    def enrich(
        self,
        *,
        source_ref: UUID,
        expires_at: datetime | None = None,
        annotation: str | None = None,
        priority: CasePriority | None = None,
        downgrade: bool = False,
    ) -> bool:
        """Un cas de plus sur la même personne : on **enrichit**, on ne duplique jamais.

        La raison d'origine ne bouge **jamais** — on ajoute d'où ça vient, ce qu'on a appris, et
        on repousse l'échéance si la nouvelle va plus loin. C'est ce qui permet au responsable de
        lire une trajectoire au lieu d'un instantané : « Absente depuis 4 semaines. A annulé le
        rendez-vous qu'elle avait demandé. »

        La priorité ne monte que si la nouvelle est **plus urgente** — sinon un événement anodin
        ferait redescendre un cas grave. `downgrade` est la seule façon de l'abaisser, et elle
        doit être demandée explicitement.

        Renvoie True si quelque chose a changé.
        """
        changed = False
        if source_ref not in self.source_refs:
            self.source_refs.append(source_ref)
            changed = True
        if expires_at is not None and (self.expires_at is None or expires_at > self.expires_at):
            self.expires_at = expires_at
            changed = True
        if annotation and annotation not in self.annotations:
            self.annotations.append(annotation)
            changed = True
        if priority is not None:
            rank = _PRIORITY_RANK
            more_urgent = rank[priority] < rank[self.priority]
            if more_urgent or (downgrade and rank[priority] > rank[self.priority]):
                self.priority = priority
                changed = True
        return changed

    def close(
        self,
        *,
        outcome: SignalOutcome,
        at: datetime,
        closed_by_account_id: UUID | None = None,
        cause: ExtinguishCause | None = None,
    ) -> None:
        """Clôt le cas. **Un humain est exigé**, sauf cause système.

        Sans cette règle, le premier réflexe d'exploitation serait de fermer automatiquement les
        vieux signaux pour « nettoyer la file » — et le produit deviendrait un théâtre."""
        is_system = cause is not None and cause in SYSTEM_CLOSURE_CAUSES
        if closed_by_account_id is None and not is_system:
            raise HumanClosureRequiredError(
                "Fermer un cas est un acte humain.",
                details={"outcome": outcome.value, "cause": cause.value if cause else None},
            )
        self._move_to(SignalStatus.CLOSED)
        self.outcome = outcome
        self.closed_at = at
        self.closed_by_account_id = closed_by_account_id

    def retract(self, *, at: datetime) -> None:
        """Le cas est devenu **faux** — une saisie tardive a montré qu'il n'avait pas lieu d'être.

        Ce n'est pas une clôture : rien n'a été résolu, personne n'a rien fait. Il sort des
        métriques au lieu d'y figurer comme un succès."""
        self._move_to(SignalStatus.RETRACTED)
        self.retracted_at = at


def priority_rank(priority: CasePriority) -> int:
    """Le rang d'urgence — plus petit, plus urgent. Défini **une fois**, ici."""
    return _PRIORITY_RANK[priority]


def outcome_for(cause: ExtinguishCause) -> SignalOutcome:
    return _OUTCOME_OF_CAUSE[cause]


def is_system_closure(cause: ExtinguishCause) -> bool:
    return cause in SYSTEM_CLOSURE_CAUSES
