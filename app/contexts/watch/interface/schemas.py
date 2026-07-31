"""Schémas d'entrée/sortie du moteur de veille.

Un seul corps, et il est **volontairement pauvre** : la personne, et une nuance choisie dans une
liste fermée. Il n'y a aucun champ de texte libre, et il ne faut jamais en ajouter — un champ
libre sur quelqu'un devient une fiche, et il survivra à celui qui l'a écrite.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.contexts.watch.domain.concern import NUANCE_LABELS, Nuance
from app.contexts.watch.domain.contact import ContactChannel, ContactResult
from app.contexts.watch.domain.regime import TenantRegime
from app.contexts.watch.domain.signal import SignalOutcome


class RaiseConcernBody(BaseModel):
    subject_account_id: UUID = Field(..., description="La personne à qui on pense")
    nuance: Nuance | None = Field(
        None,
        description=(
            "Optionnelle, et sur la **relation** — jamais sur un état intérieur supposé. "
            "Elle n'existe que pour le suivant : si le cas est transféré ou escaladé, "
            "il reçoit sinon un cas muet."
        ),
    )


class ConcernAckView(BaseModel):
    """« Noté. » — la personne concernée, elle, n'apprendra jamais qu'un tiers a signalé."""

    message: str


class NuanceOptionView(BaseModel):
    value: Nuance
    label: str


class NuanceListView(BaseModel):
    """La liste fermée, telle que le client doit l'afficher — jamais un champ de saisie."""

    items: list[NuanceOptionView]

    @classmethod
    def all(cls) -> "NuanceListView":
        return cls(
            items=[
                NuanceOptionView(value=n, label=label) for n, label in NUANCE_LABELS.items()
            ]
        )


class CaseView(BaseModel):
    """Un cas tel que son responsable le lit."""

    id: UUID
    subject_id: UUID
    reason: str
    annotations: list[str]
    # « Cas précédent clos le 3 février — repris contact, situation suivie. » Ce qui évite de
    # rappeler quelqu'un en ouvrant par « je vois que tu n'es pas venue ».
    previous_case_note: str | None
    occurrence_number: int
    priority: str
    status: str
    opened_at: datetime
    first_seen_at: datetime | None
    first_contact_at: datetime | None

    @classmethod
    def of(cls, dto) -> "CaseView":
        return cls(
            id=dto.id, subject_id=dto.subject_id, reason=dto.reason,
            annotations=list(dto.annotations), previous_case_note=dto.previous_case_note,
            occurrence_number=dto.occurrence_number, priority=dto.priority,
            status=dto.status, opened_at=dto.opened_at,
            first_seen_at=dto.first_seen_at, first_contact_at=dto.first_contact_at,
        )


class CaseListView(BaseModel):
    items: list[CaseView]

    @classmethod
    def of(cls, dtos) -> "CaseListView":
        return cls(items=[CaseView.of(d) for d in dtos])


class CloseCaseBody(BaseModel):
    outcome: SignalOutcome = Field(
        ...,
        description=(
            "**Choisie**, jamais déduite — aucune valeur par défaut. Une issue pré-cochée "
            "deviendrait le rangement automatique, et la calibration ne mesurerait plus que "
            "la paresse du formulaire."
        ),
    )


class StartContactBody(BaseModel):
    channel: ContactChannel
    person_label: str = Field(..., description="Le nom affiché dans le rappel de retour")


class StartedContactView(BaseModel):
    attempt_id: UUID
    prompt_at: datetime | None


class AnswerContactBody(BaseModel):
    result: ContactResult
    # **Ce que je m'engage à faire ensuite** — « je la rappelle jeudi », « je passe déposer le
    # colis ». Jamais ce que je pense d'elle : la note porte sur mon geste, pas sur la personne,
    # et c'est le seul champ de texte libre de toute la veille.
    commitment: str | None = Field(default=None, max_length=280)


class PendingAttemptView(BaseModel):
    id: UUID
    signal_id: UUID
    attempted_at: datetime


class PendingAttemptListView(BaseModel):
    """Ce qu'on demande à la réouverture de l'application, et une seule fois."""

    items: list[PendingAttemptView]

    @classmethod
    def of(cls, attempts) -> "PendingAttemptListView":
        return cls(
            items=[
                PendingAttemptView(
                    id=a.id, signal_id=a.signal_id, attempted_at=a.attempted_at
                )
                for a in attempts
            ]
        )


class WouldHaveSignalledView(BaseModel):
    """Un cas que l'église aurait reçu. La raison est celle qui **aurait été affichée**."""

    subject_account_id: UUID
    reason: str
    origin: str
    detected_at: datetime
    owner_account_id: UUID | None


class ShadowReportView(BaseModel):
    """Ce que Dorea aurait dit — dans l'ordre où elle l'aurait dit."""

    regime: str
    observing: bool
    count: int
    cases: list[WouldHaveSignalledView]

    @classmethod
    def of(cls, report) -> "ShadowReportView":
        return cls(
            regime=report.regime.value,
            observing=report.is_observing,
            count=report.count,
            cases=[
                WouldHaveSignalledView(
                    subject_account_id=c.subject_id,
                    reason=c.reason,
                    origin=c.origin,
                    detected_at=c.detected_at,
                    owner_account_id=c.owner_account_id,
                )
                for c in report.cases
            ],
        )


class LetDoreaSpeakBody(BaseModel):
    """Le régime visé. `ASSISTED` par défaut : on sort du rodage sans sauter à l'automatique."""

    regime: TenantRegime = TenantRegime.ASSISTED


class RegimeView(BaseModel):
    regime: str
    emits: bool  # ce régime laisse-t-il un cas atteindre un responsable ?
