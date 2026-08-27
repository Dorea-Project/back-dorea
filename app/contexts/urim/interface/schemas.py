"""Schémas HTTP d'Urim.

La forme de `StudyView` porte une décision de produit : **la trace et les options sont
au même niveau que le résultat**. Une préparation n'est pas une réponse qu'on consomme,
c'est un raisonnement qu'on suit — et le motif de chaque étage est ce que le pasteur lit
pour décider s'il est d'accord.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.contexts.urim.application.ports import StudyDTO
from app.contexts.urim.domain.libelles import LOCI, en_clair, forme_en_clair
from app.contexts.urim.engine.stages.propose_theme import theme_propose
from app.contexts.urim.engine.state import EntryOrigin
from app.contexts.urim.infrastructure.corpus import morphology, morphology_hebrew
from app.contexts.urim.interface.turn import TurnView, construire_tour


def theme_en_clair(record) -> str | None:
    """Le theme du moteur, dit en francais — **et rien quand la phrase est du pasteur**.

    `theologie_propre, en textuel doctrinal` est du vocabulaire de schema montre a un
    predicateur. Ce champ le double en clair : « Dieu lui-meme — un plan colle au texte sur une
    doctrine ». Le client affiche `theme_label` s'il existe, `theme` sinon.

    🔴 **Le gabarit ne bouge pas d'un caractere.** `theme_propose` est une **empreinte** : le
    moteur compare le theme enregistre a ce qu'il rendrait pour savoir si le pasteur l'a
    reecrit. Le rendre lisible ferait cesser de correspondre *tous les themes deja en base*, et
    le systeme conclurait que chaque pasteur a reecrit le sien — sans lever la moindre erreur.
    On ajoute donc a cote, on ne traduit jamais en place.

    Et l'empreinte sert **ici aussi** : un theme qui ne correspond plus au gabarit est une
    phrase d'homme, deja lisible. La traduire serait la recouvrir. On rend `None`, et c'est la
    sienne qui s'affiche."""
    theme = record.theme
    if not theme:
        return None

    plan = getattr(record, "plan_source", None)
    matiere = getattr(record, "subject_matter", None)
    if theme != theme_propose(record.axis_code, plan, matiere):
        return None

    axe = en_clair(record.axis_code, LOCI) if record.axis_code else ""
    forme = forme_en_clair(plan, matiere)
    if axe and forme:
        return f"{axe} — {forme}"
    return axe or forme or None


def _decrire(code: str | None, langue: str) -> str:
    """⚠️ **La langue choisit la grille, jamais la forme du code.**

    Le grec range huit dimensions à position fixe ; l'hébreu empile des morphèmes séparés par
    `/`. Lire l'un avec la grille de l'autre ne lève aucune erreur — ça produit une glose
    grammaticale fausse, c'est-à-dire exactement ce qu'un pasteur redit sans le vérifier."""
    table = morphology_hebrew if langue == "hbo" else morphology
    return table.decrire(code)


def _nature(code: str | None, langue: str) -> str:
    table = morphology_hebrew if langue == "hbo" else morphology
    return table.nature(code)


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


class TurnBody(BaseModel):
    """Un tour de parole **en cours de** préparation — le trou 2 du contrat (§6).

    Un seul champ, et c'est le même que celui de l'ouverture : le pasteur écrit une phrase.
    Aucun `stage_code` à renvoyer — c'est précisément ce qui distingue ce geste d'une décision.
    L'étage, le serveur le sait ; le pasteur, lui, parle.

    ⚠️ Pas d'`entry_origin` ici. Il dit d'où vient la chaîne à l'**ouverture**, où il décide
    qu'une dictée se fait confirmer (S36) ; en cours de préparation, ce qui protège du micro
    resté ouvert n'est plus la confirmation mais le vocabulaire — `indechiffrable` existe pour
    cela, et il ne demande rien à personne."""

    raw_input: str = Field(min_length=1, max_length=4000)

    #: ⚠️ **Ce qui rend une parole rejouable sans dommage.**
    #:
    #: Un client sans reseau met ses gestes en file. Decider et ecarter posent un
    #: etat : les renvoyer donne le meme resultat. Une parole, non — le serveur y
    #: repond, et la renvoyer couterait un second passage du repondeur, donc un
    #: appel de modele en plus et peut-etre une autre phrase.
    #:
    #: Avec cette cle, une parole deja traitee ne rejoue rien : le serveur rend
    #: l'etat courant, qui est exactement ce que le client attendait. Absente,
    #: le comportement est celui d'avant — aucun client existant ne casse.
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=64)


class ElementBody(BaseModel):
    element_code: str = Field(min_length=1, max_length=64)
    ordinal: int = Field(ge=0, le=999)
    body: str | None = Field(default=None, max_length=20000)


class ElementsBody(BaseModel):
    elements: list[ElementBody] = Field(default_factory=list, max_length=50)


class TraceEntryView(BaseModel):
    stage_code: str
    rationale: str


def _option_view(ligne: tuple) -> OptionView:
    """Une ligne d'option du DTO, quel que soit le nombre de champs qu'elle porte.

    ⚠️ **Le déballage positionnel strict était une bombe à retardement.** La ligne a gagné
    `strength`, puis `signature`, puis `reference` : chaque ajout cassait tous les appelants
    d'un coup, et l'un d'eux — la note du livrable — en déballait cinq depuis longtemps sans
    que personne ne s'en aperçoive, parce que l'étage qui la produit n'a pas d'options.

    Les champs qui arrivent après sont donc facultatifs à la lecture. Ce qui manque prend sa
    valeur par défaut, et rien ne se tait."""
    code, label, rationale, origin, dismissed, *reste = ligne
    strength, signature, reference = [*reste, None, None, ""][:3]
    return OptionView(
        code=code, label=label, rationale=rationale, origin=origin, dismissed=dismissed,
        strength=strength, signature=signature, reference=reference or "",
    )


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
    #: Le pasteur l'a écartée. Elle **reste dans la liste**, reléguée en fin — la retirer lui
    #: ferait perdre ce qu'on lui avait proposé, et rendrait son geste irréversible par accident.
    dismissed: bool = False

    #: Ce que le texte fait de l'axe — `dominant`, `porte`, `resiste`, ou `null`. C'est ce qui
    #: permet au client de séparer *en fait son sujet* de *le soutient* sans lire le libellé.
    strength: str | None = None

    #: ⚠️ **Qui a écrit ce libellé** — `null` quand il vient du corpus, `ia-mistral` quand un
    #: modèle l'a habillé. C'est §5.4 appliqué à l'écran des axes : *pour que rien de généré ne
    #: se confonde avec une relecture*. Sept des dix loci portent le mot de la dogmatique, les
    #: autres celui du pasteur — et ils avaient exactement la même apparence.
    signature: str | None = None

    #: La référence du passage désigné — « Colossiens 1:1-14 ». Vide quand l'option n'en
    #: désigne aucun : un locus, un couple plan x matière, un choix de bornes.
    reference: str = ""


class ParoleView(BaseModel):
    """Une ligne du fil — **ce qui s'est dit, et où le pasteur l'a posée**.

    🔴 Le fil disparaissait quand on quittait l'écran : le serveur ne gardait que la saisie
    d'ouverture. C'est ce champ qui le rend enfin relisible trois jours plus tard.

    `element_code` porte l'adresse, quand le pasteur a désigné un point — « le deuxième »,
    « point 3 », ou les mots du point. Nul, la phrase attend sans adresse, et c'est un état
    normal : *ça peut être point ou pas*.

    ⚠️ **`promue` dit ce que le document imprimera.** Tant qu'elle est fausse, cette phrase
    n'atteint aucun fichier — le livrable n'imprime que le plan du pasteur."""

    id: UUID
    speaker: Literal["pasteur", "urim"]
    body: str
    element_code: str | None = None
    element_ordinal: int | None = None
    promue: bool = False


class ElementView(BaseModel):
    element_code: str
    ordinal: int
    body: str | None


class ReferenceElsewhereView(BaseModel):
    """⚠️ **Le numéro que ce verset porte ailleurs**, et seulement quand il en change.

    Le pasteur prépare sur la Segond et ouvre en chaire la Bible de son assemblée. « Exode 7:26 »
    y désigne un autre texte si cette Bible est une Ostervald : le verset y est en 8:1, poussé
    par le découpage hébreu. Les deux références sont bien formées, donc rien ne l'avertirait.

    `reference` à `null` : ce témoin **ne porte pas** ce verset — Darby n'a pas Actes 8:37, que
    le texte critique ne retient pas. À afficher comme une absence, pas comme une erreur."""

    version: str
    reference: str | None


class VerseView(BaseModel):
    reference: str
    text: str
    #: Vide dès que la numérotation concorde, ce qui est le cas presque partout.
    elsewhere: list[ReferenceElsewhereView] = []


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

    #: Le meme theme en francais, ou NULL quand `theme` est deja une phrase du pasteur.
    #: Voir `theme_en_clair` : l'empreinte reste intacte, on ajoute a cote.
    theme_label: str | None = None

    elements: list[ElementView]

    #: **Ce qui s'est dit**, dans l'ordre. Lu en base, jamais rejoué.
    fil: list[ParoleView] = []

    #: **Ce sur quoi le raisonnement porte** — la `trace` est le raisonnement lui-même.
    verses: list[VerseView]
    variants: list[VariantView]
    bearings: list[BearingView]
    caveats: list[str]
    context: list[ContextView]
    couples: list[CoupleView]

    #: **La chaîne de textes** — ce que le sermon convoque autour de son passage.
    supports: list[SupportView]

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

    #: ⚠️ **Le tour vient EN PLUS, il ne remplace rien.** `StudyView` reste le contrat d'état et
    #: ses tests restent valides ; `turn` est la présentation conversationnelle des mêmes
    #: données. Un client ancien l'ignore et continue de fonctionner.
    #:
    #: Il est calculé après coup, dans `construire_tour`, pour que la vue ne dépende pas de sa
    #: propre présentation — c'est ce qui garantit que les deux ne peuvent pas se contredire.
    turn: TurnView | None = None

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
            options=[_option_view(ligne) for ligne in dto.options],
            resolved=dto.resolved_label,
            pericope_id=r.pericope_id,
            pericope_label=dto.pericope_label,
            resisting_elsewhere=[
                ResistingElsewhereView(
                    reference=_borne(s.bounds), label=s.label, rationale=s.rationale
                )
                for s in dto.resisting_elsewhere
            ],
            supports=[
                SupportView(raw=r_, reference=ref, text=t, verdict=m)
                for r_, ref, t, m in dto.supports
            ],
            curation_reviewed_by=dto.pericope_reviewed_by,
            bounds_overridden=r.bounds_overridden,
            version_id=r.version_id,
            axis_code=r.axis_code,
            plan_source=r.plan_source,
            subject_matter=r.subject_matter,
            theme=r.theme,
            theme_label=theme_en_clair(r),
            elements=[
                ElementView(element_code=e.element_code, ordinal=e.ordinal, body=e.body)
                for e in dto.elements
            ],
            fil=[
                ParoleView(
                    id=p.id,
                    speaker=p.speaker,
                    body=p.body,
                    element_code=p.element_code,
                    element_ordinal=p.element_ordinal,
                    promue=p.promue,
                )
                for p in dto.fil
            ],
            verses=[
                VerseView(
                    reference=v.reference, text=v.text,
                    elsewhere=[
                        ReferenceElsewhereView(version=a.version, reference=a.reference)
                        for a in v.elsewhere
                    ],
                )
                for v in dto.verses
            ],
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

    @classmethod
    def avec_tour(cls, dto: StudyDTO) -> StudyView:
        """La vue, **plus** sa présentation conversationnelle.

        Deux temps et non un : la vue se construit sans rien savoir du tour, puis le tour se
        construit à partir d'elle. Un tour bâti dans `from_dto` aurait pu lire le DTO
        directement et diverger de ce que la vue affiche — c'est-à-dire dire au pasteur autre
        chose que ce que l'écran lui montre.

        ⚠️ La seule chose que le DTO souffle au tour est `reponse` — la phrase d'un répondeur,
        quand le tour a été aiguillé plutôt que décidé. Elle prend la place de `say` et rien
        d'autre : ce n'est pas une donnée que la vue affiche, donc les deux ne peuvent pas se
        contredire."""
        vue = cls.from_dto(dto)
        return vue.model_copy(
            update={
                "turn": construire_tour(
                    vue, say=dto.reponse, relance=dto.relance
                )
            }
        )


class PromotionBody(BaseModel):
    """Sous quel point cette note devient un point — **quand elle ne le dit pas elle-même**.

    Les deux champs sont facultatifs : une note posée sous un point porte déjà son adresse.
    Ils servent au cas où le pasteur n'avait rien désigné en écrivant, et range plus tard."""

    element_code: str | None = Field(default=None, min_length=1, max_length=64)
    ordinal: int | None = Field(default=None, ge=0, le=999)


class ArticulationBody(BaseModel):
    """Quel point développer — **son point, désigné par lui**."""

    element_code: str = Field(min_length=1, max_length=64, examples=["divisions"])
    ordinal: int = Field(ge=0, le=999)


class ArticulationView(BaseModel):
    """Ce que le modèle propose pour ce point.

    ⚠️ **Rien de tout ceci n'entre dans un document.** Le livrable n'imprime que
    `preparation_element.body` : cette proposition n'atteint un fichier que si le pasteur la
    reprend dans son plan — c'est-à-dire s'il l'a lue et adoptée.

    `model` voyage avec le texte : une proposition sans son auteur ressemblerait, dans six
    mois, à quelque chose que quelqu'un a écrit."""

    body: str
    transition: str
    model: str
    #: `false` = aucun modèle branché, plafond atteint, ou point vide. **Pas une erreur** :
    #: l'atelier fonctionne sans, et le pasteur écrit son point comme il l'a toujours fait.
    disponible: bool


class DiapositiveBody(BaseModel):
    """Une diapositive composée par le pasteur. `texte_projete` est **le sien** — il coupe, il
    abrège, il glose entre crochets — et c'est ce que le serveur juge contre le corpus."""

    titre: str = Field(default="", max_length=200)
    reference: str = Field(min_length=2, max_length=80, examples=["Romains 8:1"])
    texte_projete: str = Field(default="", max_length=4000)


class DeliverableBody(BaseModel):
    """⚠️ **Aucune case « introduction proposée ».** Le modèle n'a pas de canal de sortie en
    prose, et un gabarit de document est exactement l'endroit où ce canal se rouvrirait."""

    kind: str = Field(default="deck", pattern="^(deck|note)$")
    diapositives: list[DiapositiveBody] = Field(default_factory=list, max_length=120)


class ControleView(BaseModel):
    """Le verdict d'une diapositive — **ce que le produit veut montrer**, pas une erreur.

    `version` nomme celle qui reconnaît le texte, et ce n'est pas cosmétique : sur Romains 8:1,
    reconnaître Ostervald plutôt que la LSG change la doctrine du verset projeté."""

    slide_no: int
    reference: str
    projected_text: str
    verdict: str
    rationale: str
    version_id: UUID | None


class DeliverableView(BaseModel):
    """Le dossier de validation. **Aucun fichier n'existe encore** : le contrôle est en amont,
    parce qu'un fichier produit est un fichier qui circule."""

    id: UUID
    kind: str
    format: str
    validation: str
    validated_by: UUID | None
    generated_at: datetime
    corpus_snapshot: str | None
    content_fingerprint: str | None
    controles: list[ControleView]

    @classmethod
    def from_dto(cls, dto) -> DeliverableView:
        r = dto.record
        return cls(
            id=r.id, kind=r.kind, format=r.format, validation=r.validation,
            validated_by=r.validated_by, generated_at=r.generated_at,
            corpus_snapshot=r.corpus_snapshot, content_fingerprint=r.content_fingerprint,
            controles=[
                ControleView(
                    slide_no=c.slide_no, reference=c.reference,
                    projected_text=c.projected_text, verdict=c.verdict,
                    rationale=c.rationale, version_id=c.version_id,
                )
                for c in dto.controles
            ],
        )


class StudySummaryView(BaseModel):
    """Une ligne du fil d'accueil.

    ⚠️ **Aucune phrase d'Urim ici.** Le `say` et le `why` d'un tour viennent du
    rejeu ; les servir dans une liste obligerait à faire tourner le moteur
    autant de fois qu'il y a de lignes. Le fil dit **où l'on en est**, l'écran
    de la préparation dit **ce qu'Urim a dit**.
    """

    id: UUID

    #: Ce que le pasteur a écrit en ouvrant. C'est le titre tant que rien n'est
    #: résolu — « l'amour fraternel n'existe plus dans l'église ».
    raw_input: str

    #: Le titre écrit à la main, quand il y en a un. **Il passe devant** `raw_input` et
    #: `pericope_label` à l'affichage ; il ne les remplace pas dans la base.
    title: str | None = None

    #: L'unité une fois bornée, quand elle l'est.
    pericope_label: str | None = None
    theme: str | None = None
    #: Voir `theme_en_clair`. NULL quand le pasteur a ecrit le sien.
    theme_label: str | None = None
    axis_code: str | None = None
    service_date: date | None = None

    #: `ouverte`, `close`, `rangee`. Une rangée ne remonte pas dans le fil courant :
    #: il faut la demander (`GET /studies?rangees=true`).
    status: str

    #: Le vocabulaire du moteur : `await_decision` **est** « rend la main ».
    #: NULL tant qu'aucun tour n'a été rendu.
    last_outcome: str | None = None
    last_stage_code: str | None = None
    last_turn_at: datetime | None = None

    opened_at: datetime | None = None

    @classmethod
    def from_record(cls, record, *, pericope_label: str | None = None) -> StudySummaryView:
        return cls(
            id=record.id,
            raw_input=record.raw_input,
            title=record.title,
            pericope_label=pericope_label,
            theme=record.theme,
            theme_label=theme_en_clair(record),
            axis_code=record.axis_code,
            service_date=record.service_date,
            status=record.status,
            last_outcome=record.last_outcome,
            last_stage_code=record.last_stage_code,
            last_turn_at=record.last_turn_at,
            opened_at=record.opened_at,
        )


class ArchiveFromStudyBody(BaseModel):
    """« J'ai prêché cette préparation. »

    ⚠️ **`preached_on` par défaut = aujourd'hui, jamais `service_date`.** Une préparation datée
    du dimanche prochain n'a pas été prêchée pour autant."""

    preached_on: date | None = None
    capture_kind: str = Field(default="saisie", max_length=16)


class ArchiveManualBody(BaseModel):
    """Un sermon sans préparation — prêché ailleurs, ou avant Dorea."""

    reference: str = Field(min_length=2, max_length=80, examples=["Actes 1:1-14"])
    preached_on: date
    church_id: UUID | None = None
    axis_code: str | None = Field(default=None, max_length=40)
    theme: str | None = Field(default=None, max_length=2000)
    capture_kind: str = Field(default="import", max_length=16)


class ArchiveEntryView(BaseModel):
    id: UUID
    preached_on: date
    reference: str
    pericope_label: str | None
    #: NULL = **non rangé**, et c'est un état normal : hors unité curée, il n'y a aucun axe à
    #: retenir. Le client doit le nommer plutôt que de masquer la ligne.
    axis_code: str | None
    theme: str | None
    #: Voir `theme_en_clair`. NULL quand le pasteur a ecrit le sien.
    theme_label: str | None = None
    capture_kind: str | None
    preparation_id: UUID | None
    church_id: UUID | None

    @classmethod
    def from_dto(cls, dto) -> ArchiveEntryView:
        r = dto.record
        return cls(
            id=r.id, preached_on=r.preached_on, reference=dto.reference,
            pericope_label=dto.pericope_label, axis_code=r.axis_code, theme=r.theme,
            theme_label=theme_en_clair(r),
            capture_kind=r.capture_kind, preparation_id=r.preparation_id,
            church_id=r.church_id,
        )


class BookCoverageView(BaseModel):
    """⚠️ **Deux nombres, jamais additionnés.** `passages` compte des lieux distincts —
    prêcher deux fois le même texte n'élargit pas un canon ; `preachings` compte des
    événements, parce que deux assemblées ont entendu."""

    book: str
    passages: int
    preachings: int
    last_preached_on: date


class AxisTallyView(BaseModel):
    """Un rayon du rangement. `axis_code` à NULL = **non rangé** — il s'affiche."""

    axis_code: str | None
    preachings: int
    last_preached_on: date


class CoverageView(BaseModel):
    """Le parcours d'un prédicateur — **des faits, aucune consigne**.

    ⚠️ Cet écran ne propose jamais de sermon. Un rayon vide se montre, il ne se comble pas :
    *le signal informe l'homme, l'homme commande la machine*. Aucun score, aucune série,
    aucun pourcentage de complétude doctrinale — ce serait mesurer la fidélité d'un pasteur,
    et transformer une aide en performance à tenir.

    ⚠️ **`books_untouched` dit « aucun sermon rangé ici », pas « il n'a jamais prêché cela »**
    (S38) : un texte peut avoir été prêché sous une autre unité, ou sans axe retenu."""

    books: list[BookCoverageView]
    axes: list[AxisTallyView]
    books_untouched: int

    @classmethod
    def from_dto(cls, dto) -> CoverageView:
        return cls(
            books=[
                BookCoverageView(
                    book=libelle, passages=c.passages, preachings=c.preachings,
                    last_preached_on=c.last_preached_on,
                )
                for libelle, c in dto.books
            ],
            axes=[
                AxisTallyView(
                    axis_code=a.axis_code, preachings=a.preachings,
                    last_preached_on=a.last_preached_on,
                )
                for a in dto.axes
            ],
            books_untouched=dto.books_untouched,
        )


class OriginalWordView(BaseModel):
    """Un mot de l'original — **ce que sa forme fait**, pas ce qu'il signifie.

    `Ἀγαπήσεις` dans Luc 10:27 est un futur de l'indicatif : « tu aimeras », et non
    l'impératif qu'on prêche d'ordinaire. La différence change le sermon.

    ⚠️ **`gloss` n'existe pas et c'est assumé.** MorphGNT ne porte aucune traduction, et les
    lexiques libres sont en anglais. Le pasteur voit le lemme et la forme, pas « aimer ». Une
    glose inventée aurait l'air d'une source — personne ne relit une analyse grammaticale, on
    la croit, et l'erreur ressort en chaire.

    `parsing` porte le code brut à côté du texte décodé : une analyse contestée doit pouvoir
    se vérifier contre la source."""

    reference: str
    position: int
    surface: str
    lemma: str
    #: « verbe », « nom », « article »… — vide si la nature est absente.
    pos: str
    #: « 2ᵉ personne · futur · actif · indicatif · singulier ».
    morphology: str
    #: Le code brut tel quel — `2FAI-S--` en grec, `HR/Ncfsa` en hébreu.
    parsing: str
    #: `grc` ou `hbo`. Le client en a besoin pour la **direction du texte** : l'hébreu s'écrit
    #: de droite à gauche, et un mot rendu à l'envers est illisible pour qui le lit vraiment.
    language: str


#: 🔴 **La phrase qui accompagne chaque répartition — écrite ici, une seule fois, et relue.**
#:
#: Le client n'écrit jamais une phrase de sa propre autorité (`docs/Urim_Conversation.md`) : ce
#: que le pasteur lit vient du serveur, sinon il échapperait à la relecture et aux tests. Une
#: collision est justement l'endroit où une phrase mal choisie ferait le plus de dégâts — il
#: suffirait d'écrire « les manuscrits divergent » pour transformer un choix de traducteur en
#: variante textuelle, dans la bouche d'un pasteur, devant une assemblée qui ne peut pas
#: vérifier.
#:
#: Les trois phrases disent donc **ce qui a été observé** et rien de plus, et chacune finit par
#: renvoyer au texte plutôt qu'à une conclusion. Y compris sur ce qui paraît anodin : la phrase
#: du partage a d'abord dit *« c'est le signe que l'original porte plus d'un sens »*, ce qui est
#: souvent vrai et que rien ici ne permet d'affirmer — c'est le test de vocabulaire qui l'a
#: attrapée, en refusant le mot « original ».
_CE_QUE_LA_FORME_DIT = {
    "temoin_isole": (
        "Une seule de ces traductions rend ce mot autrement ; les autres s'accordent "
        "avec la Segond. Lisez-les en regard."
    ),
    "partage": (
        "Les traducteurs se partagent sur ce mot : certains le rendent comme la Segond, "
        "d'autres non. Lisez les deux façons de le dire."
    ),
    "segond_seule": (
        "Aucune des autres traductions ne rend ce mot comme la Segond. Si votre prédication "
        "s'appuie sur lui, allez d'abord voir ce que les autres en ont fait."
    ),
}

#: ⚠️ **Le rappel voyage avec la donnée, pas dans une note de bas de page.**
#:
#: C'est la seule chose que ce module doit absolument empêcher, et la seule qui ne coûte rien :
#: `urim_corpus_textual_variant` dit ce que les manuscrits portent, et se remplit depuis un
#: apparat critique par un humain qui signe. Une collision ne dit que ce que des hommes ont
#: **lu**.
_JAMAIS_UNE_VARIANTE = (
    "Ce n'est pas une variante des manuscrits : c'est une divergence entre traducteurs."
)


class WitnessReadView(BaseModel):
    """Un traducteur devant ce mot.

    `stance` a **trois** valeurs et non deux. `muet` dit que ce témoin ne se prononce pas — il
    ne tient pas ce verset, ou il l'a reformulé d'un bout à l'autre, et l'absence du mot chez
    lui ne veut donc rien dire. Le compter comme un accord retournerait le sens de la
    répartition."""

    code: str
    label: str
    #: `texte_recu` · `critique` · `eclectique` · `massoretique` — l'édition dont ce traducteur
    #: part. **Affichée, jamais interprétée** : le produit ne conclut rien de la famille, le
    #: pasteur lit qui suit quoi.
    text_family: str
    stance: str
    #: Le mot qu'il écrit à la place — **vide quand l'appariement n'est pas certain**, et c'est
    #: alors le verset entier qui parle. Nommer un remplaçant qu'on n'a pas su apparier est la
    #: seule façon de rendre cet écran menteur.
    reading: str | None = None
    body: str


class CollisionView(BaseModel):
    """**Là où des traducteurs sérieux n'ont pas lu la même chose.**

    ⚠️⚠️ Voir `_JAMAIS_UNE_VARIANTE`, que chaque ligne porte : ce n'est **pas** un signalement
    de manuscrit. La distinction n'est pas une précaution de langage — c'est une propriété
    mesurée du détecteur, qui rejette par construction ce dont une variante est faite (une
    proposition entière ajoutée ou retirée) et ne voit que des substitutions de mot.

    Aucun poids, aucun score n'est rendu. Un chiffre à côté d'un verset se lit comme une note,
    et rien ici n'est noté : le seuil a servi à choisir ce qui s'affiche, il n'a rien à dire au
    pasteur."""

    reference: str
    word: str
    form: str
    #: La phrase du produit pour cette répartition — le client la rend, il ne l'écrit pas.
    says: str
    caution: str = _JAMAIS_UNE_VARIANTE
    witnesses: list[WitnessReadView]

    @classmethod
    def from_dto(cls, dto) -> CollisionView:
        return cls(
            reference=dto.reference, word=dto.word, form=dto.form,
            says=_CE_QUE_LA_FORME_DIT.get(dto.form, ""),
            witnesses=[
                WitnessReadView(
                    code=t.code, label=t.label, text_family=t.text_family,
                    stance=t.stance, reading=t.reading, body=t.body,
                )
                for t in dto.witnesses
            ],
        )


class RenameBody(BaseModel):
    """Le titre écrit à la main.

    **Vide efface** au lieu de poser un blanc : c'est le seul moyen de revenir à
    l'affichage automatique — la phrase d'ouverture, puis l'unité bornée — sans deviner
    une formule. Un champ effacé par mégarde rend donc son nom d'origine, il ne laisse
    pas une ligne sans nom.
    """

    title: str | None = Field(default=None, examples=["Le pardon entre deux familles"])


class ShelveBody(BaseModel):
    """Ranger, ou ressortir.

    Un booléen plutôt que deux routes : c'est un état, pas deux gestes, et un client qui
    ne sait plus où il en est peut poser la valeur qu'il veut sans se demander laquelle
    des deux routes appeler.
    """

    rangee: bool = Field(examples=[True])


class SupportsBody(BaseModel):
    """Les textes d'appui, **dans l'ordre du pasteur** — pas celui du canon.

    Il écrit sa progression : l'annonce avant l'accomplissement, l'antécédent avant la
    reprise. Retrier serait défaire son plan."""

    supports: list[str] = Field(default_factory=list, max_length=40)


class SupportView(BaseModel):
    """Un texte d'appui — **avec ce que la saisie a donné, ou pourquoi elle n'a rien donné**.

    C'est ici que le contrôle de référence atteint enfin le pasteur. Ses notes portaient
    `Hb 2v29` et `Ph 28v9` ; Urim savait dire « Hébreux 2 compte 18 versets » depuis le premier
    jour et ne l'avait jamais dit, faute d'une surface où ces textes soient soumis.

    ⚠️ **`raw` survit toujours.** Une saisie illisible reste dans la liste avec son motif : la
    perdre obligerait le pasteur à se souvenir de ce qu'il voulait citer."""

    raw: str
    #: La référence résolue — vide si la saisie n'a rien donné.
    reference: str
    #: Le texte servi, vide de même.
    text: str
    #: Ce qui manque **au corpus**, jamais au pasteur : « Hébreux 2 compte 18 versets ».
    verdict: str

class OccurrenceView(BaseModel):
    """Un endroit où le mot paraît — la référence, le verset français, la forme, sa grammaire."""

    reference: str
    text: str
    surface: str
    morphology: str


class ConcordanceView(BaseModel):
    """**La première pierre du module de recherche, et celle qui ne peut rien inventer.**

    Le pasteur qui voit `ὑπόδημα` dans Luc 15:22 veut savoir ce que ce mot porte. Une note
    historique le lui dirait — « chez les Hébreux les esclaves allaient pieds nus » — et
    pourrait se tromper sans que personne dans l'assemblée ne puisse le vérifier. La
    concordance ne fait que **montrer le texte** : Jean-Baptiste indigne de délier la sandale,
    les disciples envoyés sans sandales, et le père qui fait chausser son fils venu se proposer
    comme mercenaire. La culture matérielle s'y enseigne par la récurrence.

    ⚠️ **`total` et le nombre rendu sont distincts.** `δοῦλος` paraît 126 fois ; en montrer
    cinquante sans le dire ferait passer un extrait pour l'ensemble, et un pasteur conclurait
    d'un échantillon qu'il croit complet."""

    lemma: str
    #: `grc` ou `hbo` — le client en a besoin pour la direction du texte.
    language: str
    #: Le compte **réel**, indépendant de ce qui est rendu.
    total: int
    occurrences: list[OccurrenceView]

    @classmethod
    def from_dto(cls, dto) -> ConcordanceView:
        return cls(
            lemma=dto.lemma, language=dto.language, total=dto.total,
            occurrences=[
                OccurrenceView(
                    reference=r, text=t, surface=s,
                    morphology=_decrire(m, dto.language),
                )
                for r, t, s, m in dto.occurrences
            ],
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

    #: Les mots de l'original. **Vide sur l'Ancien Testament** tant que l'hébreu n'est pas
    #: semé — un état normal, qui se voit plutôt qu'il ne se devine.
    original: list[OriginalWordView]

    #: 🔴 **Les endroits où les traducteurs se séparent.**
    #:
    #: Elle est ici et non dans le tour de la conversation. Un bloc de tour présente ce qu'un
    #: étage vient de produire ; aucun étage ne produit une collision, et aucun ne le doit —
    #: c'est une propriété du verset, au même titre que `variants`. Dans le fil, elle
    #: ressemblerait à une question posée au pasteur ; ici, c'est une trouvaille qu'il ouvre
    #: quand il veut, sur l'écran fait pour regarder avant de choisir.
    #:
    #: ⚠️ **Ce n'est pas `variants`, et les deux ne doivent pas se ressembler à l'écran.**
    #: `variants` dit ce que les manuscrits portent ; ceci dit ce que des hommes ont lu. Chaque
    #: ligne porte son `caution` pour que la distinction voyage avec la donnée.
    #:
    #: Vide sur la très grande majorité des passages : seuls les 5 % où le désaccord pèse le
    #: plus lourd sont retenus. *Rien plutôt qu'une vraisemblance.*
    collisions: list[CollisionView] = []

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
            verses=[
                VerseView(
                    reference=v.reference, text=v.text,
                    elsewhere=[
                        ReferenceElsewhereView(version=a.version, reference=a.reference)
                        for a in v.elsewhere
                    ],
                )
                for v in dto.verses
            ],
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
            original=[
                OriginalWordView(
                    reference=r, position=p, surface=s, lemma=lem,
                    pos=_nature(nat, langue), morphology=_decrire(par, langue),
                    parsing=par, language=langue,
                )
                for r, p, s, lem, nat, par, langue in dto.original
            ],
            collisions=[CollisionView.from_dto(c) for c in dto.collisions],
        )

