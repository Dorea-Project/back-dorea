"""Schémas HTTP d'Urim.

La forme de `StudyView` porte une décision de produit : **la trace et les options sont
au même niveau que le résultat**. Une préparation n'est pas une réponse qu'on consomme,
c'est un raisonnement qu'on suit — et le motif de chaque étage est ce que le pasteur lit
pour décider s'il est d'accord.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field

from app.contexts.urim.application.ports import StudyDTO
from app.contexts.urim.engine.state import EntryOrigin


class OpenStudyBody(BaseModel):
    """Un champ, et rien à cocher.

    ⚠️ **`entry_mode` n'est plus ici, et son absence est la fonctionnalité.** Référence,
    citation et intention ne sont pas des cases que le pasteur remplit : c'est au moteur de
    les reconnaître, en croisant la saisie avec les 31 170 versets. Tant qu'un défaut
    `reference` comblait le silence, l'étage 0 posait une question de désaccord à quelqu'un
    qui n'avait rien dit — deux saisies sur trois interrompues avant que le moteur n'ait rien
    fait d'utile.

    Le mode ne s'écrit plus que par une correction explicite, sur la route de décision.
    """

    raw_input: str = Field(min_length=1, max_length=4000)
    #: Tapée ou dictée (S36). Le système **sait** d'où vient la chaîne — le module de
    #: capture connaît son `provider`. Il n'a donc pas à le déduire des mots. C'est le seul
    #: signal d'entrée qui reste, et il ne dit rien du *contenu*, seulement de sa provenance.
    entry_origin: EntryOrigin = EntryOrigin.TYPED
    service_date: date | None = None


class DecisionBody(BaseModel):
    stage_code: str = Field(min_length=1, max_length=64)
    option_code: str = Field(min_length=1, max_length=200)


class ElementBody(BaseModel):
    element_code: str = Field(min_length=1, max_length=64)
    ordinal: int = Field(ge=0, le=999)
    body: str | None = Field(default=None, max_length=20000)


class ElementsBody(BaseModel):
    elements: list[ElementBody] = Field(default_factory=list, max_length=50)


class TraceEntryView(BaseModel):
    stage_code: str
    rationale: str


class OptionView(BaseModel):
    """⚠️ `origin` dit **d'où vient la proposition** — deux options côte à côte ne valent pas
    la même chose.

    « Jean 5:42 partage 1 des mots rares » et « Parabole du bon Samaritain, illustrant qui est
    notre prochain » arrivaient dans la même liste avec la même apparence. Groupez-les :

        lettre    trouvé parce que vos mots figurent dans le verset
        sens      proposé parce que le passage traite votre sujet
        curation  lu dans le corpus relu — unité, pesée, couple plan x matière
        locus     l'un des dix loci de la dogmatique
        bornage   un choix de bornes (« mes bornes », « le tout en un seul »)
        entree    une correction de lecture (« ce n'est pas ça », « c'est mon sujet »)
        moteur    défaut"""

    code: str
    label: str
    rationale: str
    origin: str


class ElementView(BaseModel):
    element_code: str
    ordinal: int
    body: str | None


class VerseView(BaseModel):
    reference: str
    text: str


class VariantView(BaseModel):
    """⚠️ S17 — **à afficher avec le texte, toujours.**

    Prêcher Romains 8:1 sans signaler que le Texte Reçu y ajoute « qui ne marchent pas selon
    la chair » expose à une contradiction avec l'auditoire : sans la clause, la non-condamnation
    est inconditionnelle ; avec elle, c'est une condition morale."""

    reference: str
    body: str
    doctrinal_weight: str
    note: str
    families_with: list[str]
    families_without: list[str]
    source_ref: str


class BearingView(BaseModel):
    """`strength` a quatre valeurs, et **`resiste` est celle qui compte** — un texte qui
    complique un axe n'est pas un texte qui s'en tait. Elle s'affiche au même rang."""

    axis_code: str
    label: str
    strength: str
    rationale: str


def _borne(bounds) -> str:
    """« Livre ch:v-v » depuis des bornes — la référence que le pasteur ira ouvrir."""
    debut, fin = bounds.start, bounds.end
    if debut.verse_start is None:
        return f"{debut.book} {debut.chapter}"
    dernier = fin.verse_end or fin.verse_start
    if fin.chapter != debut.chapter:
        return f"{debut.book} {debut.chapter}:{debut.verse_start}-{fin.chapter}:{dernier}"
    if dernier and dernier != debut.verse_start:
        return f"{debut.book} {debut.chapter}:{debut.verse_start}-{dernier}"
    return f"{debut.book} {debut.chapter}:{debut.verse_start}"


class ResistingElsewhereView(BaseModel):
    """Un texte d'AILLEURS qui complique l'axe retenu — **au même rang que ce qui le porte**.

    C'est ce que `BearingView` ne peut pas dire : elle parle de l'unité qu'on prépare, pas de
    celles qui la contredisent. Un pasteur préparant Romains 8 sur la guérison doit rencontrer
    2 Corinthiens 12:7-10, et il ne le rencontrera pas tout seul — c'est précisément le texte
    qu'on ne cherche pas quand on a déjà son idée."""

    reference: str
    label: str
    rationale: str


class ContextView(BaseModel):
    kind: str
    body: str
    source_ref: str


class CoupleView(BaseModel):
    """Les refusés voyagent avec les faisables : *une combinaison impossible est signalée,
    jamais fabriquée*. Les cacher laisserait croire qu'on n'y a pas pensé."""

    plan_source: str
    subject_matter: str
    feasible: bool
    refusal_reason: str
    proof_text_risk: str


class StudyView(BaseModel):
    id: UUID
    status: str
    #: Le mode **retenu par le moteur** — ce que le pasteur veut voir. La colonne, elle,
    #: reste vide tant qu'il n'a rien corrigé.
    entry_mode: str | None
    raw_input: str

    outcome: str
    rationale: str
    trace: list[TraceEntryView]
    options: list[OptionView]

    resolved: str | None
    pericope_id: UUID | None
    #: Vrai quand le pasteur a forcé ses bornes. Tout ce qui est curé devient alors
    #: illisible pour les étages avals — c'est la contrepartie assumée de la liberté.
    bounds_overridden: bool
    version_id: UUID | None
    axis_code: str | None
    plan_source: str | None
    subject_matter: str | None
    theme: str | None

    elements: list[ElementView]

    #: **Ce sur quoi le raisonnement porte** — la `trace` est le raisonnement lui-même.
    verses: list[VerseView]
    variants: list[VariantView]
    bearings: list[BearingView]
    caveats: list[str]
    context: list[ContextView]
    couples: list[CoupleView]

    #: L'intitulé de l'unité littéraire retenue — il n'apparaissait que noyé dans le motif de
    #: l'étage 2, donc illisible pour un front qui veut l'afficher en titre.
    pericope_label: str | None
    #: Les textes qui resistent, venus d'ailleurs — le garde-fou du chemin reference.
    resisting_elsewhere: list[ResistingElsewhereView]
    #: ⚠️ **Qui a signé cette unité** — `ia-mistral` ou le nom d'un relecteur.
    #:
    #: C'est la contrepartie du découpage produit par le modèle, et elle n'est pas cosmétique :
    #: sans elle, une structure générée arrive sur l'écran du pasteur exactement comme une
    #: structure relue par un bibliste. `reviewed_by NOT NULL` porte cette distinction depuis le
    #: premier jour ; elle ne servait à rien tant qu'elle s'arrêtait à la base.
    curation_reviewed_by: str | None

    corpus_snapshot: str | None
    corpus_drifted: bool

    @classmethod
    def from_dto(cls, dto: StudyDTO) -> StudyView:
        r = dto.record
        return cls(
            id=r.id,
            status=r.status,
            entry_mode=dto.entry_mode,
            raw_input=r.raw_input,
            outcome=dto.outcome,
            rationale=dto.rationale,
            trace=[TraceEntryView(stage_code=c, rationale=m) for c, m in dto.trace],
            options=[
                OptionView(code=c, label=lib, rationale=m, origin=o)
                for c, lib, m, o in dto.options
            ],
            resolved=dto.resolved_label,
            pericope_id=r.pericope_id,
            pericope_label=dto.pericope_label,
            resisting_elsewhere=[
                ResistingElsewhereView(
                    reference=_borne(s.bounds), label=s.label, rationale=s.rationale
                )
                for s in dto.resisting_elsewhere
            ],
            curation_reviewed_by=dto.pericope_reviewed_by,
            bounds_overridden=r.bounds_overridden,
            version_id=r.version_id,
            axis_code=r.axis_code,
            plan_source=r.plan_source,
            subject_matter=r.subject_matter,
            theme=r.theme,
            elements=[
                ElementView(element_code=e.element_code, ordinal=e.ordinal, body=e.body)
                for e in dto.elements
            ],
            verses=[VerseView(reference=v.reference, text=v.text) for v in dto.verses],
            variants=[
                VariantView(
                    reference=v.reference, body=v.body,
                    doctrinal_weight=v.doctrinal_weight, note=v.note,
                    families_with=list(v.families_with),
                    families_without=list(v.families_without),
                    source_ref=v.source_ref,
                )
                for v in dto.variants
            ],
            bearings=[
                BearingView(
                    axis_code=b.axis_code, label=b.label,
                    strength=b.strength, rationale=b.rationale,
                )
                for b in dto.bearings
            ],
            caveats=list(dto.caveats),
            context=[
                ContextView(kind=c.kind, body=c.body, source_ref=c.source_ref)
                for c in dto.context
            ],
            couples=[
                CoupleView(
                    plan_source=c.plan_source, subject_matter=c.subject_matter,
                    feasible=c.feasible, refusal_reason=c.refusal_reason,
                    proof_text_risk=c.proof_text_risk,
                )
                for c in dto.couples
            ],
            corpus_snapshot=r.corpus_snapshot,
            corpus_drifted=dto.corpus_drifted,
        )


class UnitRefView(BaseModel):
    """Une unité littéraire qui couvre le passage demandé — son nom et pourquoi ces bornes."""

    id: str
    label: str
    reference: str
    rationale: str


class PassageDetailView(BaseModel):
    """**En savoir plus sur un passage**, sans ouvrir de préparation.

    Le pasteur à qui l'on propose six passages veut les ouvrir avant de choisir : ce qu'ils
    portent, ce sur quoi les traditions divergent, ce que disent les manuscrits. Lecture pure —
    aucune écriture, aucune réservation, aucun appel de modèle.

    ⚠️ **Les DIX pesées ici, `absent` compris**, alors que `StudyView` n'affiche que ce qui
    porte. Un locus `absent` dit *quelqu'un a regardé et le texte n'en dit rien* ; un locus
    manquant dit *personne n'a regardé*. Ce sont des choses opposées, et c'est l'écran d'étude
    qui doit les distinguer.

    ⚠️ **Il n'y a pas de langue originale, et ce n'est pas un oubli.** `urim_corpus_lemma` et
    `urim_corpus_token` existent au schéma et sont vides : ni hébreu, ni grec, ni morphologie
    dans ce corpus. Le plus proche est `variants`, qui porte les familles de manuscrits — ce que
    le Texte Reçu ajoute là où les éditions critiques se taisent. Servir une glose inventée à la
    place serait pire que le silence."""

    reference: str

    #: Toutes les unités qui couvrent la demande. **Plus d'une** signifie que le passage
    #: chevauche plusieurs unités littéraires : la curation ci-dessous reste alors vide, et
    #: c'est au pasteur d'ouvrir celle qu'il veut lire.
    units: list[UnitRefView]

    #: L'unité littéraire qui couvre ce passage, si elle existe — avec **qui l'a signée**.
    pericope_id: UUID | None
    pericope_label: str | None
    #: Pourquoi ces bornes-là. C'est la phrase que le pasteur lit pour vous contredire.
    pericope_rationale: str | None
    reviewed_by: str | None

    verses: list[VerseView]
    #: Le plus proche de « la traduction originale » que ce corpus sache dire.
    variants: list[VariantView]
    #: Les dix, `absent` compris — voir l'avertissement ci-dessus.
    bearings: list[BearingView]
    #: Ce que le texte NE dit PAS. Le confessionnel nomme les traditions qui divergent, et la
    #: formulation reste « ici les traditions divergent », jamais « votre tradition dit X ».
    caveats: list[str]
    context: list[ContextView]
    couples: list[CoupleView]
    resisting_elsewhere: list[ResistingElsewhereView]

    @classmethod
    def from_dto(cls, dto) -> PassageDetailView:
        return cls(
            reference=dto.reference,
            units=[
                UnitRefView(id=i, label=lab, reference=r, rationale=m)
                for i, lab, r, m in dto.units
            ],
            pericope_id=dto.pericope_id,
            pericope_label=dto.pericope_label,
            pericope_rationale=dto.pericope_rationale,
            reviewed_by=dto.reviewed_by,
            verses=[VerseView(reference=v.reference, text=v.text) for v in dto.verses],
            variants=[
                VariantView(
                    reference=v.reference, body=v.body,
                    doctrinal_weight=v.doctrinal_weight, note=v.note,
                    families_with=list(v.families_with),
                    families_without=list(v.families_without),
                    source_ref=v.source_ref,
                )
                for v in dto.variants
            ],
            bearings=[
                BearingView(
                    axis_code=b.axis_code, label=b.label,
                    strength=b.strength, rationale=b.rationale,
                )
                for b in dto.bearings
            ],
            caveats=list(dto.caveats),
            context=[
                ContextView(kind=c.kind, body=c.body, source_ref=c.source_ref)
                for c in dto.context
            ],
            couples=[
                CoupleView(
                    plan_source=c.plan_source, subject_matter=c.subject_matter,
                    feasible=c.feasible, refusal_reason=c.refusal_reason,
                    proof_text_risk=c.proof_text_risk,
                )
                for c in dto.couples
            ],
            resisting_elsewhere=[
                ResistingElsewhereView(
                    reference=_borne(s.bounds), label=s.label, rationale=s.rationale
                )
                for s in dto.resisting_elsewhere
            ],
        )
