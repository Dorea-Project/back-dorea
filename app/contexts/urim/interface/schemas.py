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
from app.contexts.urim.infrastructure.corpus import morphology, morphology_hebrew
from app.contexts.urim.interface.turn import TurnView, construire_tour


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
    #: Le pasteur l'a écartée. Elle **reste dans la liste**, reléguée en fin — la retirer lui
    #: ferait perdre ce qu'on lui avait proposé, et rendrait son geste irréversible par accident.
    dismissed: bool = False

    #: Ce que le texte fait de l'axe — `dominant`, `porte`, `resiste`, ou `null`. C'est ce qui
    #: permet au client de séparer *en fait son sujet* de *le soutient* sans lire le libellé.
    strength: str | None = None


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
            options=[
                OptionView(
                    code=c, label=lib, rationale=m, origin=o, dismissed=e, strength=f
                )
                for c, lib, m, o, e, f in dto.options
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
        return vue.model_copy(update={"turn": construire_tour(vue, say=dto.reponse)})


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
            original=[
                OriginalWordView(
                    reference=r, position=p, surface=s, lemma=lem,
                    pos=_nature(nat, langue), morphology=_decrire(par, langue),
                    parsing=par, language=langue,
                )
                for r, p, s, lem, nat, par, langue in dto.original
            ],
        )

