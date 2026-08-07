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
from app.contexts.watch.domain.gesture import GESTURE_LABELS, GestureKind
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


class DeclareGestureBody(BaseModel):
    """Aussi pauvre que le signalement, et pour la même raison — **plus** une interdiction.

    Il n'y a pas de champ « pourquoi ». Le motif appartient à la personne : c'est à elle de le
    déclarer, ou à l'église de le publier. Un tiers qui pourrait l'écrire construirait un dossier
    de santé tenu par les voisins."""

    subject_account_id: UUID = Field(..., description="La personne pour qui le geste a été posé")
    gesture: GestureKind = Field(
        ..., description="Ce qui a été fait — liste fermée, on tape, on n'écrit pas"
    )


class DeclareLinkBody(BaseModel):
    """Un nom, et rien d'autre. Pas de champ « lien de parenté », pas de « conjoint ».

    Qualifier la relation ferait une donnée sur le foyer de quelqu'un — et le lien qu'on a le plus
    de raisons de retirer est justement le lien conjugal."""

    linked_account_id: UUID = Field(..., description="Quelqu'un par qui on peut vous rejoindre")


class LinkAckView(BaseModel):
    """« C'est noté. » — et **rien ne part vers la personne nommée**.

    `remaining` dit combien de places restent, jamais combien de gens vous ont cité : le degré
    entrant n'existe nulle part, c'est un score de popularité et, par son complément, la carte
    d'isolement."""

    message: str
    remaining: int


class FraternalReactView(BaseModel):
    """Une invitation à écrire. **Un identifiant, une date — et rien d'autre.**

    Pas de nom (le client résout), pas de motif, et surtout aucune mesure du silence de l'autre :
    `last_gesture_at` est la date du geste de **celui qui lit**. C'est ce qui fait que cette liste
    n'apprend rien à personne — et qu'elle ne peut donc pas servir à deviner qui va mal."""

    account_id: UUID
    last_gesture_at: datetime


class FraternalReactListView(BaseModel):
    items: list[FraternalReactView]

    @classmethod
    def of(cls, reacts) -> "FraternalReactListView":
        return cls(
            items=[
                FraternalReactView(
                    account_id=r.account_id, last_gesture_at=r.last_gesture_at
                )
                for r in reacts
            ]
        )


class GestureOptionView(BaseModel):
    value: GestureKind
    label: str


class GestureListView(BaseModel):
    """Les trois gestes, tels que le compagnon doit les afficher — jamais une saisie."""

    items: list[GestureOptionView]

    @classmethod
    def all(cls) -> "GestureListView":
        return cls(
            items=[
                GestureOptionView(value=g, label=label)
                for g, label in GESTURE_LABELS.items()
            ]
        )


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


class CalibrationProposalView(BaseModel):
    """Une proposition de seuil. **`evidence` est la phrase qu'on peut contester.**

    Aucun champ ne nomme quelqu'un : la calibration porte sur `(église, paramètre)`, et une vue
    qui exposerait un membre trahirait exactement ce que le module s'interdit."""

    id: UUID
    param: str
    current: int
    proposed: int
    evidence: str

    @classmethod
    def of(cls, proposal) -> "CalibrationProposalView":
        return cls(
            id=proposal.id,
            param=proposal.param.value,
            current=proposal.current,
            proposed=proposal.proposed,
            evidence=proposal.evidence,
        )


class DecideOnProposalBody(BaseModel):
    """Accepter, ou refuser. Sans défaut : ranger d'un clic ne doit pas être plus facile que
    décider."""

    accept: bool


class ContextSegmentView(BaseModel):
    """Une ligne du bloc, et la source qu'on peut déplier pour vérifier."""

    kind: str  # episode | link | gesture | present | last_contact | commitment
    text: str
    at: datetime | None
    source: str | None
    # Le lien fraternel : **un identifiant, jamais un nom**. Le client résout, comme pour tout le
    # reste de ce contexte — et c'est ce qui garde le lien à un saut, sur un cas, pour son
    # propriétaire. Aucune route ne le rend en liste, et il n'existe pas de sens inverse.
    account_id: UUID | None = None


class CaseContextView(BaseModel):
    """Ce que le responsable relit avant d'appeler. Vide si le cas n'a pas d'histoire."""

    case_id: UUID
    segments: list[ContextSegmentView]

    @classmethod
    def of(cls, dto) -> "CaseContextView":
        return cls(
            case_id=dto.case_id,
            segments=[
                ContextSegmentView(
                    kind=s.kind, text=s.text, at=s.at, source=s.source,
                    account_id=s.account_id,
                )
                for s in dto.segments
            ],
        )
