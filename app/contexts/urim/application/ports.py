"""Ce dont le service d'étude a besoin, et qu'il ne sait pas faire lui-même.

La préparation persistée est **maigre par choix** : elle garde les décisions, pas la
trace. Le moteur étant déterministe à corpus constant, la trace se **rejoue** — la
stocker en dupliquerait la vérité et permettrait aux deux de diverger.

C'est aussi pourquoi `corpus_snapshot` est persisté : rejouer contre un corpus qui a
bougé doit se **voir**, pas se deviner.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol
from uuid import UUID

from app.contexts.urim.engine.deps import (
    AxisBearing,
    BearingSite,
    ContextNote,
    Feasibility,
)
from app.contexts.urim.engine.state import (
    AxisGloss,
    Maturite,
    PassageSuggestion,
    Reference,
)

#: ⚠️ **Ré-exporté depuis le moteur, et pas défini ici.** La maturité est lue par un étage
#: (`vestibule`), donc elle appartient au noyau pur : l'application peut importer le
#: moteur, jamais l'inverse. Le ré-export existe pour que la bordure — l'adaptateur
#: Mistral, le service — n'ait pas à connaître deux adresses pour un même vocabulaire.
__all__ = ["Maturite"]


@dataclass(slots=True)
class PreparationRecord:
    """La préparation telle que la base la garde — **les décisions, pas le raisonnement**."""

    id: UUID
    #: **NULL = aucune église** — l'antichambre. Voir le modèle SQL pour la règle d'accès.
    church_id: UUID | None
    author_id: UUID
    raw_input: str
    #: Le titre ecrit a la main, quand il y en a un. Voir le modele SQL : il passe
    #: devant `raw_input` et l'etiquette de la pericope, il ne les remplace pas.
    title: str | None = None
    entry_mode: str | None = None
    entry_origin: str | None = None
    #: La version dans laquelle la citation a été reconnue, quand l'index ne la portait
    #: pas. Stockée pour que l'étage d'entrée donne le même motif à chaque relecture.
    citation_version: str | None = None
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
    #: --- Le vestibule --------------------------------------------------------------------
    #:
    #: 🔴 **`confirme` ne s'écrit que sur un tour du pasteur.** Voir `Maturite`, et l'étage
    #: `vestibule` qui est le seul à lire ce champ.
    maturity: str = Maturite.ABSENT

    #: La charge nettoyée de son emballage — c'est **elle** qui descend au consentement.
    carried_subject: str | None = None

    #: Un sujet décliné ne revient pas (RT1).
    declined_subjects: tuple[str, ...] = ()

    service_date: date | None = None
    service_timezone: str = "Africa/Abidjan"
    status: str = "ouverte"

    #: Ou en etait le moteur au dernier tour. Voir le modele SQL : c'est une
    #: projection, pas une source.
    last_stage_code: str | None = None
    last_outcome: str | None = None
    last_turn_at: datetime | None = None

    #: La derniere cle d'idempotence vue sur une parole. Voir le modele SQL.
    last_turn_key: str | None = None

    opened_at: datetime | None = None
    closed_at: datetime | None = None


@dataclass(slots=True)
class ElementRecord:
    """Un champ du squelette homilétique — libre, jamais imposé."""

    element_code: str
    ordinal: int
    body: str | None = None


@dataclass(slots=True)
class SupportRecord:
    """Un texte d'appui, tel que la base le garde — **la saisie d'abord, la résolution ensuite**.

    ⚠️ `raw` survit même quand rien ne résout. Les notes du Pasteur X portaient `Hb 2v29` et
    `Ph 28v9` : deux références inexistantes qu'Urim savait détecter et n'avait jamais vues,
    faute d'une surface où le pasteur soumette ses appuis. Ne garder que ce qui résout
    effacerait exactement ce qu'il faut lui montrer.

    Le motif du refus n'est **pas** stocké : il se recalcule à l'affichage, parce que le corpus
    peut apprendre demain un sigle qu'il ignore aujourd'hui — `hb` y est entré cette semaine."""

    raw: str
    book_id: int | None = None
    chapter: int | None = None
    verse_start: int | None = None
    verse_end: int | None = None


@dataclass(slots=True)
class UsageSnapshot:
    """L'état du plafond à l'instant de la demande — d'une église, ou d'un compte.

    `ceiling_reached` est la seule chose que le moteur en voit : il ne connaît ni le
    décompte ni le quota, il sait seulement s'il doit se replier sur le domaine public.

    ⚠️ **`assistance_exhausted` est un autre plafond, et il ne faut pas les confondre.**

    `ceiling_reached` protège une **licence** : trop de versets servis depuis une traduction
    sous licence, on retombe sur le domaine public. Une église qui l'atteint ne doit rien
    perdre de l'IA — ce sont deux ressources sans rapport.

    `assistance_exhausted` protège le **quota d'appels de modèle** d'une personne. Il éteint
    l'assistance et rien d'autre : le corpus, les pesées, la concordance et le contrôle de
    référence continuent. Les avoir fondus dans un seul booléen aurait fait perdre l'IA à une
    église pour une raison de traduction, et le texte à un pasteur pour une raison de jetons."""

    window_id: UUID | None = None
    metered_units: int = 0
    ceiling: int = 0
    ceiling_reached: bool = False
    assistance_exhausted: bool = False


@dataclass(frozen=True, slots=True)
class ReferenceElsewhere:
    """Le même verset sous le numéro d'un autre témoin — ou l'aveu qu'il ne le porte pas.

    🔴 **Le pasteur a une Bible sur son bureau, et ce n'est pas forcément la nôtre.** Urim sert
    la Segond ; beaucoup d'assemblées francophones lisent Ostervald. Préparer sur « Exode 7:26 »
    puis ouvrir un Ostervald à 7:26, c'est lire un autre texte — le verset y est en 8:1, poussé
    par le découpage hébreu. Rien ne le signale, et rien ne pourrait le signaler : les deux
    références sont parfaitement formées, et c'est bien ce qui rend l'erreur silencieuse.

    `reference` à `None` dit que ce témoin **ne porte pas** ce verset : Darby n'a pas Actes 8:37,
    que le texte critique ne retient pas. C'est une information, pas une panne — la taire
    laisserait le pasteur chercher dans son livre quelque chose qui n'y est pas.

    ⚠️ **Ce n'est pas un choix de traduction.** Urim ne demande jamais au pasteur de configurer :
    il signale. On ne lui propose pas de lire ailleurs, on le prévient que le numéro change."""

    version: str
    reference: str | None


@dataclass(slots=True)
class VerseServed:
    """Un verset **rendu au pasteur** — la chose pour laquelle Urim existe.

    Elle manquait : `serve_corpus` annonçait « texte servi depuis une version du domaine
    public », posait `version_id`, et la réponse ne portait que cet identifiant. Le pasteur
    recevait une référence et un UUID à la place de soixante-trois caractères."""

    reference: str
    text: str

    #: ⚠️ **Seulement les témoins qui rangent ce verset AILLEURS**, jamais ceux qui le rangent
    #: au même endroit. Sur 31 170 versets, la numérotation concorde presque partout : signaler
    #: la concordance noierait les quelques centaines d'endroits où elle manque, et c'est
    #: exactement à ces endroits-là que le pasteur se trompe de verset.
    elsewhere: tuple[ReferenceElsewhere, ...] = ()


@dataclass(slots=True)
class VariantSeen:
    """Une variante textuelle **affichée à côté du texte** (S17).

    Elle ne change aucun raisonnement : elle prévient. *Prêcher Romains 8:1 sans signaler que
    le Texte Reçu y ajoute une condition expose à une contradiction avec l'auditoire.*"""

    reference: str
    body: str
    doctrinal_weight: str
    note: str
    families_with: tuple[str, ...]
    families_without: tuple[str, ...]
    source_ref: str


@dataclass(frozen=True, slots=True)
class WitnessRead:
    """Un traducteur devant un mot — son édition, ce qu'il en fait, et son verset entier."""

    code: str
    label: str
    #: L'édition dont il part : `texte_recu`, `critique`, `eclectique`, `massoretique`. **Un
    #: fait affiché à côté de lui**, dont le produit ne tire aucune conclusion.
    text_family: str
    #: `accorde` | `diverge` | `muet` — et `muet` n'est pas `accorde`.
    stance: str
    #: Le mot qu'il écrit à la place, **seulement quand l'écart est un mot pour un mot**.
    reading: str | None
    body: str


@dataclass(frozen=True, slots=True)
class CollisionSeen:
    """Un mot que les traducteurs n'ont pas rendu de la même façon.

    ⚠️⚠️ **À ne jamais présenter comme une variante textuelle** — c'est `VariantSeen` qui dit ce
    que les manuscrits portent, et elle vient d'un apparat critique relu par un humain. Ici on
    n'affirme rien du texte : *des traducteurs sérieux ont lu autrement, allez voir.*

    La distinction n'est pas rhétorique. Une variante est une **proposition entière** présente
    ou absente ; le détecteur ne voit que des substitutions d'un mot par un autre, et rejette
    par construction ce dont une variante est faite."""

    reference: str
    #: Le mot de la Segond, normalisé. Un seul côté est nommé : apparier les deux supposerait un
    #: alignement positionnel que le texte ne donne pas.
    word: str
    #: `temoin_isole` | `partage` | `segond_seule`. **Une répartition, jamais une cause.**
    form: str
    witnesses: tuple[WitnessRead, ...]


@dataclass(frozen=True, slots=True)
class SuggestionSnapshot:
    """Ce que le modèle a offert, tel qu'on le rejouera.

    `model` est à cet instantané ce que `corpus_snapshot` est à la préparation : sans lui, une
    réponse gardée ne dit pas *qui* l'a produite, et le jour où l'alias du modèle bouge on ne
    saurait pas distinguer ce qui a été rendu hier de ce qu'on rendrait aujourd'hui."""

    input_hash: str
    model: str
    axes: tuple[AxisGloss, ...] = ()
    flags: tuple[str, ...] = ()
    passages: tuple[PassageSuggestion, ...] = ()


@dataclass(frozen=True, slots=True)
class WeighedOption:
    """Une proposition **telle qu'un étage l'a pesée** — et ce que le pasteur en a fait.

    `rationale` est le motif de l'étage, pas celui du pasteur : on n'enregistre nulle part
    pourquoi il écarte. Ce qu'on peut dire honnêtement, c'est *ce qu'Urim avançait* et *qu'il
    ne l'a pas retenu* — et c'est exactement ce qui manque quand une option disparaît."""

    code: str
    label: str
    rationale: str
    dismissed: bool = False


@dataclass(frozen=True, slots=True)
class StageWeighing:
    """Un étage traversé, et **ce qu'il a eu en main**.

    ⚠️ Le pipeline pèse à chaque étage et **ne garde que le dernier** : `StudyDTO.options`
    porte les propositions de l'étage qui a rendu la main, les autres tombent. Le pasteur voit
    donc ce qu'Urim conclut, jamais par où il est passé.

    `weighed` est vide sans que ce soit un défaut — la plupart des étages continuent sans rien
    proposer. **On ne remplit pas d'une phrase pour meubler** : un étage qui n'a rien pesé rend
    une liste vide, et son motif suffit."""

    stage_code: str
    rationale: str
    weighed: tuple[WeighedOption, ...] = ()


@dataclass(slots=True)
class StudyDTO:
    """Ce que le pasteur voit — la trace **rejouée**, pas relue."""

    record: PreparationRecord
    outcome: str
    rationale: str
    trace: tuple[tuple[str, str], ...] = ()

    #: **Le même parcours, avec ce que chaque étage tenait** — la trace dit *pourquoi*, ceci
    #: dit *sur quoi*. Additif : `trace` ne change pas d'un octet.
    weighings: tuple[StageWeighing, ...] = ()
    #: `(code, label, rationale, origin, dismissed)` — la provenance voyage avec l'option,
    #: sinon le client la devine depuis la forme du motif, ce qui marche jusqu'au jour où non.
    #:
    #: `dismissed` dit que le pasteur l'a **écartée**. Elle reste dans la liste, reléguée en
    #: fin : la retirer lui ferait perdre ce qu'on lui avait proposé, et rendrait son geste
    #: irréversible par accident.
    #: `(code, libellé, motif, origine, écartée, force, signature)` — la force dit ce que le
    #: texte fait de l'axe (`dominant`, `porte`, `resiste`), ou `None` quand l'option ne pèse
    #: aucun axe ; la signature dit **qui a écrit le libellé** (`None` = le corpus).
    options: tuple[tuple[str, str, str, str, bool, str | None, str | None], ...] = ()
    elements: tuple[ElementRecord, ...] = ()
    resolved_label: str | None = None

    #: ⚠️ **Ce sur quoi le raisonnement porte** — distinct de la trace, qui est le raisonnement.
    #:
    #: Tout cela existait déjà dans l'index et ne sortait qu'écrasé dans des phrases : un front
    #: ne pouvait ni afficher une mise en garde à part, ni marquer le texte qui **résiste**, ni
    #: citer le relecteur. Aucun étage n'a bougé — le moteur avait tout, il ne le laissait pas
    #: passer.
    verses: tuple[VerseServed, ...] = ()
    variants: tuple[VariantSeen, ...] = ()
    bearings: tuple[AxisBearing, ...] = ()
    caveats: tuple[str, ...] = ()
    context: tuple[ContextNote, ...] = ()
    couples: tuple[Feasibility, ...] = ()
    #: L'unité littéraire retenue, et **qui l'a signée**.
    #:
    #: `reviewed_by` n'a jamais exigé un humain, seulement une signature — les huit unités de
    #: démonstration portaient `semis-demo`, et le découpage produit par le modèle porte
    #: `ia-mistral`. La distinction n'a de valeur que si elle **sort** : sans elle, une
    #: structure générée et une structure relue arrivent identiques sur l'écran du pasteur, ce
    #: qui est exactement la confusion que la colonne existe pour empêcher.
    pericope_label: str | None = None
    pericope_reviewed_by: str | None = None

    #: ⚠️ **Les textes qui résistent, venus d'AILLEURS** — et c'est le cœur de l'anti-proof-texting.
    #:
    #: `bearings` dit ce que *cette* unité complique ; ceci dit quelles *autres* unités
    #: compliquent l'axe retenu. Un pasteur qui prépare Romains 8 sur la guérison doit
    #: rencontrer 2 Corinthiens 12:7-10 — une écharde non retirée, trois prières sans réponse,
    #: présentée comme une grâce.
    #:
    #: La donnée existait depuis le premier jour (`sites_by_axis`) et ne sortait que du chemin
    #: intention. Le pasteur qui tape sa référence est pourtant celui qui a déjà son idée : il
    #: en a plus besoin, pas moins.
    resisting_elsewhere: tuple[BearingSite, ...] = ()
    #: **La chaîne de textes** — `(saisie, référence, texte, motif)` par appui.
    #:
    #: `motif` est rempli quand la saisie n'a pas résolu, et il porte les mots du corpus :
    #: *« Hébreux 2 compte 18 versets »*. C'est la seule façon dont le contrôle de référence
    #: atteint le pasteur — il ne soumettait jusqu'ici que son passage principal.
    supports: tuple[tuple[str, ...], ...] = ()
    #: Le mode **retenu par l'étage 0** — distinct de la colonne, qui ne porte qu'une
    #: correction du pasteur.
    entry_mode: str | None = None
    #: Vrai quand le corpus a bougé depuis l'ouverture — la trace affichée n'est plus
    #: celle qui a été produite ce jour-là, et le pasteur doit le savoir.
    corpus_drifted: bool = False

    #: ⚠️ **La phrase d'un répondeur, quand le tour a été aiguillé plutôt que décidé.**
    #:
    #: Elle prend la place de `turn.say` — *ce qu'Urim vient de faire* — et rien d'autre ne
    #: bouge : le motif reste celui du moteur, les blocs restent l'état. Un tour aiguillé n'a
    #: fait avancer aucun étage, et la vue doit continuer de dire la vérité sur l'état.
    #:
    #: `None` est le cas ordinaire : tous les autres chemins rendent la phrase de l'étage.
    reponse: str | None = None

    #: **Ce qui s'est dit, dans l'ordre** — et qui ne se rejoue pas.
    #:
    #: 🔴 Le fil disparaissait à chaque sortie d'écran. Tout le reste de la vue se **rejoue**
    #: — les pesées, les couples, les options se recalculent à chaque lecture, et c'est ce qui
    #: rend la trace fiable. Les paroles, non : elles viennent d'un modèle à un instant, et ne
    #: reviendront pas les mêmes. Elles sont donc lues en base, pas reconstruites.
    fil: tuple[ParoleDuFil, ...] = ()

    #: ⚠️ **La relance du vestibule — la passerelle, et elle doit être nommée.**
    #:
    #: Elle prend la place de `turn.ask`. Sans elle, un tour du vestibule laisse le pasteur
    #: devant un champ vide sans savoir ce qu'on attend de lui : le banc de l'arbre appelle ça
    #: *« barre ouverte, mais aucune passerelle nommée »*, et c'est un mur — exactement la forme
    #: sous laquelle un mur survit à une relecture.
    #:
    #: Elle voyage **séparée** de la parole parce que les deux n'ont pas le même rôle : l'une
    #: accueille, l'autre ouvre. Les fondre en une seule chaîne les rendait invisibles au
    #: détecteur, qui ne sait pas lire à l'intérieur d'une phrase.
    relance: str | None = None


@dataclass(slots=True)
class PassageDetailDTO:
    """**Tout ce que le corpus sait d'un passage**, lu sans ouvrir de préparation.

    Le pasteur à qui l'on propose six passages veut les ouvrir avant de choisir. Jusqu'ici il
    fallait en ouvrir une pour lire les pesées et les mises en garde — donc réserver, écrire, et
    s'engager sur un texte qu'on voulait seulement regarder.

    ⚠️ **Les DIX pesées, `absent` compris.** L'écran de préparation n'affiche que ce qui porte ;
    ici on montre tout. Un locus marqué `absent` dit *quelqu'un a regardé, le texte n'en dit
    rien* ; un locus manquant dit *personne n'a regardé*. Ce sont des choses opposées.

    ⚠️ **La langue originale n'y est pas, et ce n'est pas un oubli.** `urim_corpus_lemma` et
    `urim_corpus_token` existent au schéma et sont **vides** : il n'y a ni hébreu, ni grec, ni
    morphologie dans ce corpus. Ce qui s'en rapproche le plus est `variants`, qui porte les
    familles de manuscrits. Servir une glose inventée à la place serait pire que le silence."""

    reference: str

    #: ⚠️ **Toutes les unités qui couvrent la demande**, et pas seulement celle qu'on a retenue.
    #:
    #: « Luc 10:25-37 » en chevauche deux : le dialogue avec le docteur de la loi, et le bon
    #: Samaritain. Je prenais la première en silence — le pasteur recevait quatre versets et les
    #: pesées d'un texte qu'il n'avait pas demandé. Quand il y en a plusieurs, la curation ne
    #: s'attache à aucune ; elles sont nommées, et il ouvre celle qu'il veut lire.
    #:
    #: `(id, libellé, référence, motif)`.
    units: tuple[tuple[str, str, str, str], ...] = ()

    pericope_id: UUID | None = None
    pericope_label: str | None = None
    pericope_rationale: str | None = None
    reviewed_by: str | None = None
    verses: tuple[VerseServed, ...] = ()
    variants: tuple[VariantSeen, ...] = ()
    bearings: tuple[AxisBearing, ...] = ()
    caveats: tuple[str, ...] = ()
    context: tuple[ContextNote, ...] = ()
    couples: tuple[Feasibility, ...] = ()
    resisting_elsewhere: tuple[BearingSite, ...] = ()

    #: ⚠️ **L'original, verset par verset** — `(référence, position, surface, lemme, nature,
    #: parsing)`, le parsing en code brut.
    #:
    #: C'est ce qui donne un sens au clic : `Ἀγαπήσεις` dans Luc 10:27 est un **futur de
    #: l'indicatif**, donc « tu aimeras » — et non l'impératif qu'on prêche d'ordinaire. Aucun
    #: modèle n'intervient : les 137 554 mots viennent de MorphGNT, et le décodage du code est
    #: une table.
    #:
    #: **Vide sur l'Ancien Testament**, tant que l'hébreu n'est pas semé. Un état normal, et
    #: qui se voit.
    original: tuple[tuple[str, int, str, str, str, str, str], ...] = ()

    #: 🔴 **Les endroits où les traducteurs se séparent** — la dimension que ce corpus peut
    #: réellement offrir là où l'apparat critique lui manque.
    #:
    #: Elle est ici, à côté des mots de l'original, et **pas dans le tour de la conversation**.
    #: Un bloc de tour est la présentation de ce qu'un étage vient de produire ; aucun étage ne
    #: produit une collision, et aucun ne le doit — c'est une propriété du verset, comme une
    #: variante. Mise dans le fil, elle ferait croire au pasteur qu'il doit y répondre ; ici,
    #: c'est une trouvaille qu'il ouvre quand il veut, sur l'écran fait pour ça.
    #:
    #: Vide sur la très grande majorité des passages, et c'est normal : seuls les 5 % où le
    #: désaccord pèse le plus lourd sont retenus. *Rien plutôt qu'une vraisemblance.*
    collisions: tuple[CollisionSeen, ...] = ()


@dataclass(slots=True)
class ConcordanceDTO:
    """Toutes les fois où un mot de l'original paraît — **la seule réponse qui n'invente rien**.

    Le pasteur qui voit `ὑπόδημα` dans Luc 15:22 veut savoir ce que ce mot porte. Une note
    historique le lui dirait, et pourrait se tromper sans que personne dans l'assemblée ne
    puisse le vérifier. La concordance, elle, ne fait que **montrer le texte** : Jean-Baptiste
    indigne de délier la sandale — la tâche de l'esclave —, les disciples envoyés sans
    sandales, et le père qui fait chausser son fils venu se proposer comme mercenaire.

    La culture matérielle du texte s'enseigne par sa récurrence. Rien à sourcer, rien à
    signer, rien à croire sur parole.

    ⚠️ **`total` et `shown` sont distincts, toujours.** `δοῦλος` paraît 126 fois ; en afficher
    cinquante sans le dire ferait passer un extrait pour l'ensemble, et un pasteur conclurait
    d'un échantillon qu'il croit exhaustif."""

    lemma: str
    language: str
    total: int
    #: `(référence, texte français, forme dans l'original, code morphologique)`.
    occurrences: tuple[tuple[str, str, str, str], ...] = ()


class StudyRepository(Protocol):
    async def add(self, record: PreparationRecord) -> None: ...

    async def get(self, study_id: UUID) -> PreparationRecord | None: ...

    async def save(self, record: PreparationRecord) -> None: ...

    async def append_thread(self, parole: ParoleDuFil, *, study_id: UUID) -> None:
        """Garder ce qui vient d'être dit. **Rien ne s'écrase** : le fil s'ajoute."""
        ...

    async def list_thread(self, study_id: UUID) -> tuple[ParoleDuFil, ...]:
        """Le fil, dans l'ordre où il s'est dit."""
        ...

    async def promote_thread(self, entry_id: UUID, *, at: datetime) -> ParoleDuFil | None:
        """Marquer une note comme reprise — **une fois, et une seule**.

        Rend `None` si elle n'existe pas ou si elle est déjà promue : reprendre deux fois la
        même note écrirait deux points identiques dans le plan."""
        ...

    async def record_attempt(
        self,
        *,
        study_id: UUID,
        input_hash: str,
        candidates: list[str],
        chosen_ref: str | None,
        chosen_by: str | None,
        at: datetime,
        version_detected: UUID | None = None,
    ) -> None:
        """Trace d'une résolution — `chosen_by` dit **qui** a tranché, moteur ou pasteur.

        Ce n'est pas de la journalisation : c'est la provenance. Une référence choisie par
        le moteur et une référence choisie par le pasteur n'ont pas la même autorité, et
        rien d'autre dans le schéma ne les distingue."""
        ...

    async def set_elements(self, study_id: UUID, elements: list[ElementRecord]) -> None: ...

    async def list_elements(self, study_id: UUID) -> list[ElementRecord]: ...

    async def set_supports(self, study_id: UUID, supports: list[SupportRecord]) -> None:
        """Remplace la chaîne **entière** — elle n'a pas d'identité, elle a un ordre."""
        ...

    async def list_supports(self, study_id: UUID) -> list[SupportRecord]: ...

    async def dismiss(
        self, *, study_id: UUID, stage_code: str, option_code: str, at: datetime
    ) -> None:
        """Écarter une option — **idempotent**, parce qu'écarter deux fois est un seul fait."""
        ...

    async def restore(self, *, study_id: UUID, stage_code: str, option_code: str) -> None:
        """Reprendre ce qu'on avait écarté.

        Appelé quand le pasteur **décide** sur une option écartée : choisir une chose qu'on
        avait repoussée dit assez qu'on la reprend, et lui demander de la restaurer d'abord
        serait exiger un geste pour une intention déjà claire."""
        ...

    async def list_dismissals(self, study_id: UUID) -> list[tuple[str, str]]:
        """`(stage_code, option_code)` — ce qui a été écarté, pour le **marquer**, pas
        pour le retirer."""
        ...

    async def save_suggestions(
        self, study_id: UUID, snapshot: SuggestionSnapshot, at: datetime
    ) -> None:
        """Garder ce que le modèle vient d'offrir, **une ligne par question posée**.

        Une préparation en pose plusieurs : le chemin conviction demande les loci, les drapeaux
        et les passages ; le chemin impasse ne demande que des passages, sur la même saisie.
        Les ranger sous une seule ligne les faisait s'écraser, et chaque rejeu redemandait au
        modèle celle que l'autre venait de chasser."""
        ...

    async def get_suggestions(
        self, study_id: UUID, input_hash: str
    ) -> SuggestionSnapshot | None: ...

    async def recently_preached_axes(self, author_id: UUID, since: date) -> list[str]: ...


@dataclass(frozen=True, slots=True)
class ParoleDuFil:
    """Une ligne du fil — **ce qui s'est dit, et où il l'a posé**.

    🔴 Le fil disparaissait à chaque sortie d'écran : rien n'était gardé sauf la saisie
    d'ouverture. Un pasteur qui s'arrête le mardi et reprend le vendredi retrouvait une
    conversation vide et un moteur qui, lui, se souvenait de tout.

    ⚠️ **`element_code` ne fait pas d'elle un point.** C'est une adresse, pas une promotion :
    *« ça peut être point ou pas, il peut mettre une pause et revenir changer »*. Tant que
    `promue` est faux, le document ne l'imprime pas — il n'imprime que ce qu'il a repris."""

    id: UUID
    speaker: str
    body: str
    element_code: str | None = None
    element_ordinal: int | None = None
    promue: bool = False
    written_at: datetime | None = None

    @property
    def est_du_pasteur(self) -> bool:
        return self.speaker == "pasteur"

    @property
    def attend_sa_promotion(self) -> bool:
        """Une note posée sous un point, que le pasteur n'a pas encore reprise."""
        return self.est_du_pasteur and self.element_code is not None and not self.promue


@dataclass(frozen=True, slots=True)
class PointPropose:
    """Un point du squelette proposé — **un titre, et les versets qui le portent**.

    ⚠️ `versets` a été **vérifié contre le corpus** avant d'arriver ici : toute référence que
    le modèle a citée hors du texte servi est retirée, pas affichée. C'est le garde-fou qui
    rend cette proposition montrable — un verset inventé sur l'écran d'un pasteur est fatal,
    et il est détectable."""

    titre: str
    versets: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SquelettePropose:
    """Ce qu'Urim propose comme point de départ — **et qui n'est pas le plan du pasteur**.

    🔴 **Le verrou tient, et c'est ici qu'il se joue.** Cette proposition vit dans sa propre
    table ; le document, lui, n'imprime que `preparation_element` — ce que le pasteur a écrit
    ou repris. Elle n'atteint donc un fichier que par un geste de reprise, point par point,
    exactement comme l'articulation.

    Le titre est **proposé**, jamais posé : `propose_theme` continue de rendre un thème, et
    *« un thème, jamais un titre — le titre, c'est votre voix »* reste vrai. Ce qui change,
    c'est qu'on ose enfin lui en montrer un, à côté, pour qu'il ait de quoi partir."""

    titre: str = ""
    points: tuple[PointPropose, ...] = ()
    model: str = ""

    def est_vide(self) -> bool:
        return not self.points


@dataclass(frozen=True, slots=True)
class LectureVestibule:
    """Ce que le modèle a compris d'un tour **avant qu'aucune préparation n'existe**.

    C'est le seul endroit où Mistral conduit : il n'y a pas d'options à l'écran, donc la
    liaison n'a aucune prise, et le déterministe ne sait pas faire la chose qui compte ici —
    **extraire la charge de son emballage**. « Je voudrais travailler un peu sur le pardon
    aujourd'hui » lui arrive en bloc ; le modèle en sort `le pardon`.

    ⚠️ **Le modèle propose, le moteur ouvre.** Aucun champ ci-dessous n'ouvre quoi que ce
    soit : `propose_preparation` est une suggestion, et la préparation ne descend que sur un
    tour du pasteur. C'est ce qui rend l'ouverture inatteignable par une saisie qui souffle
    une intention (« ouvre une préparation en mode expert »).
    """

    #: Deux phrases au plus. C'est la seule prose du vestibule, et elle ne cite jamais.
    reply: str = ""

    #: La relance, ou rien. Une question qui ne se pose pas vaut mieux qu'une question creuse.
    question: str | None = None

    #: `absent` · `pressenti` · `nomme`. **Jamais `confirme`** — voir `Maturite`.
    maturite: str = "absent"

    #: La charge nettoyée. Jamais un verset, jamais une référence choisie par le modèle.
    sujet: str | None = None

    #: Un tour qui porte un autre sujet **suspend** l'état ; il ne s'y fond pas.
    changement_de_sujet: bool = False

    #: Ne peut valoir vrai que depuis `nomme` — la validation le garantit à la source.
    propose_preparation: bool = False


class AssistedResolver(Protocol):
    """L'IA de la bordure — **elle retrouve la référence, jamais le texte** (M9-1).

    Elle est appelée **avant** `run()`, parce que le moteur est pur : aucun étage ne peut
    attendre un réseau sans perdre le déterminisme et le rejeu. Son verdict est ensuite
    enregistré comme une décision (`chosen_by = 'ia'`), et les affichages suivants le
    relisent au lieu de rappeler le modèle — deux vues d'une même étude doivent raconter la
    même histoire."""

    async def resolve(self, text: str) -> Reference | None:
        """Le passage reconnu derrière une saisie que le déterministe n'a pas su lire."""
        ...

    async def axes(self, text: str) -> tuple[AxisGloss, ...]:
        """Les loci qu'une intention touche — **annotation, jamais filtre**.

        Le port jumeau `ConvictionReader` prévoyait déjà cette lecture, mais il est synchrone
        parce que le moteur l'est, et rien ne pouvait donc l'y brancher : les dix loci
        sortaient tous avec la même phrase creuse. La lecture se fait ici, à la bordure, et
        redescend par `StudyState.suggested_axes`."""
        ...

    async def passages(self, text: str) -> tuple[PassageSuggestion, ...]:
        """Les passages qui **traitent** le sujet — plusieurs, jamais un.

        Ce que `resolve` a l'interdiction de faire, mais rendu inoffensif par la pluralité :
        plusieurs références deviennent des options, et le pasteur tranche. Une seule serait
        une résolution déguisée, qui refermerait la question avant qu'elle ne s'ouvre."""
        ...

    async def lever(self, text: str) -> tuple[str, ...]:
        """Les drapeaux de risque d'une intention — **l'effet, jamais l'état de l'auteur**."""
        ...

    async def squelette(
        self, *, reference: str, texte: str, axe: str, forme: str
    ) -> SquelettePropose | None:
        """Un titre, trois ou quatre points, et les versets qui les portent.

        La septième lecture, et la plus engageante : c'est la seule où le modèle propose une
        **structure** plutôt qu'une annotation. Ce qui la rend acceptable est le même chemin
        que l'articulation — elle vit à côté du plan, et n'entre dans un document que si le
        pasteur la reprend.

        `None` sur panne : le pasteur écrit son plan comme il l'a toujours fait."""
        ...

    async def vestibule(
        self, text: str, *, sujet_en_cours: str | None = None
    ) -> LectureVestibule | None:
        """Le tour d'un pasteur qui n'a **pas encore** de préparation ouverte.

        La sixième lecture du port, et la première à conduire plutôt qu'à annoter. Elle ne
        vaut qu'avant le consentement : dès qu'une préparation descend, la liaison reprend la
        main et le modèle redevient un recours.

        `sujet_en_cours` sert au seul changement de sujet : sans lui, le modèle ne peut pas
        dire qu'un tour s'écarte de ce qui était en train de mûrir.

        `None` sur panne — et le filet déterministe reprend, comme partout ailleurs."""
        ...

    async def aiguiller(self, text: str) -> str | None:
        """Le tour du pasteur → **une intention**, d'un vocabulaire fermé, ou rien.

        La cinquième lecture du port, et la seule qui ne serve pas l'ouverture : elle n'existe
        qu'à partir du deuxième tour, quand le pasteur écrit une phrase libre au milieu de sa
        préparation. Le détecteur d'entrée fait mieux qu'elle à l'ouverture, et la liaison fait
        mieux qu'elle sur tout ce qui désigne l'écran — elle ne reçoit que le reste.

        `None` n'est pas un échec silencieux : c'est un tour qu'on ne sait pas lire. Deviner
        serait pire, parce que les répondeurs sont déterministes — une intention mal aiguillée
        donne une réponse **hors sujet, jamais fausse**."""
        ...


class NullVerseResolver:
    """Aucun modèle branché — **un état de production, pas un mode dégradé**.

    Architecture v2 §10 veut Urim utilisable hors ligne sur le domaine public : tablette,
    connexion irrégulière, plafond atteint. Le résolveur déterministe travaille alors seul, et
    le pasteur ne voit pas la différence. L'objet nul vit avec le **port**, pas avec
    l'adaptateur : c'est le contrat qui définit ce que « rien » veut dire."""

    async def resolve(self, text: str) -> Reference | None:
        return None

    async def articuler(
        self, *, point: str, reference: str, texte: str, suivant: str, appuis: str = ""
    ) -> PlanSuggestion | None:
        """Sans modèle, le pasteur écrit son point — ce qu'il faisait de toute façon."""
        return None

    async def axes(self, text: str) -> tuple[AxisGloss, ...]:
        return ()

    async def passages(self, text: str) -> tuple[PassageSuggestion, ...]:
        return ()

    async def lever(self, text: str) -> tuple[str, ...]:
        return ()

    async def squelette(
        self, *, reference: str, texte: str, axe: str, forme: str
    ) -> SquelettePropose | None:
        """Sans modèle, aucune proposition — et le pasteur écrit son plan, ce qu'il faisait
        de toute façon."""
        return None

    async def vestibule(
        self, text: str, *, sujet_en_cours: str | None = None
    ) -> LectureVestibule | None:
        """Sans modèle, le vestibule retombe sur son filet déterministe.

        **Rendre `None` plutôt qu'une lecture vide** : une maturité `absent` fabriquée ici
        serait indiscernable d'une vraie, et le fil croirait que le modèle a jugé."""
        return None

    async def aiguiller(self, text: str) -> str | None:
        """Sans modèle, aucun tour ne se classe — et l'appelant le **dit** plutôt que de le
        faire passer pour un message indéchiffrable. Voir `repondre_sans_lecture`."""
        return None


@dataclass(frozen=True, slots=True)
class CitationTrouvee:
    """Une citation retrouvée **dans une version que l'index ne porte pas**.

    `version` voyage avec la référence, et ce n'est pas décoratif : sur 1 Corinthiens 13:8,
    Darby dit « l'amour » là où Segond dit « la charité ». Savoir *dans quelle Bible* la phrase
    du pasteur a été reconnue, c'est savoir laquelle il a sous la main."""

    reference: Reference
    version: str
    #: L'identifiant, à côté du libellé : le libellé se lit, l'identifiant se range dans
    #: `version_detected` — la colonne prévue pour ce fait depuis la migration d'origine,
    #: et restée vide jusqu'ici faute d'avoir quoi que ce soit à y mettre.
    version_id: UUID
    score: float


class CitationAilleursReader(Protocol):
    """Chercher la saisie dans les autres versions détenues — **la seconde passe**.

    L'index ne charge que la version de repli : une phrase citée d'une autre traduction n'y
    est simplement pas. Ce port va la chercher en base, et **avant le modèle** — une citation
    que le corpus possède n'a pas à être devinée."""

    async def retrouver(self, mots: Sequence[str]) -> CitationTrouvee | None: ...


class NullCitationAilleurs:
    """Aucune seconde passe — l'index seul, comme avant. État de production légitime."""

    async def retrouver(self, mots: Sequence[str]) -> CitationTrouvee | None:
        return None


@dataclass(slots=True)
class PlanSuggestion:
    """Ce que le modèle propose pour **un point du plan** — dans l'atelier, jamais imprimé.

    ⚠️ **C'est la seule sortie en prose de tout Urim, et elle est enfermée ici.** Le livrable
    n'imprime que `preparation_element.body` ; cette proposition ne l'atteint que si le pasteur
    la reprend, c'est-à-dire s'il l'a lue et adoptée. Le patron est celui du dépôt entier :
    *l'IA propose, l'homme dispose* — et côté Sermon, *rien de non approuvé n'atteint le
    membre*."""

    #: Le développement proposé pour ce point — quelques phrases, jamais un sermon.
    body: str
    #: La phrase qui mène au point suivant. Vide s'il n'y a pas de suivant.
    transition: str = ""
    #: Le modèle qui l'a écrite — l'équivalent de `corpus_snapshot`, pour la même raison.
    model: str = ""


class PlanAssistant(Protocol):
    """L'articulation d'un point, demandée explicitement.

    **Model-optional comme tout le reste** : sans clé, l'adaptateur nul rend `None` et l'atelier
    fonctionne — le pasteur écrit son point lui-même, ce qu'il faisait de toute façon."""

    async def articuler(
        self, *, point: str, reference: str, texte: str, suivant: str, appuis: str = ""
    ) -> PlanSuggestion | None:
        """⚠️ **Le modèle reçoit le point, le passage, son texte, et les textes que le point
        cite lui-même — rien d'autre.**

        `appuis` a été ajouté après le premier appel réel : sur un point qui citait Hébreux 9
        alors qu'on servait Actes 1, le modèle a **complété de mémoire** (« dans le lieu très
        saint »). Exact, et hors du texte fourni — donc invérifiable pour le pasteur. Lui
        donner les textes qu'il cite supprime le besoin de combler.

        Pas les pesées (elles sont curées, il les redirait mal), pas les mises en garde (elles
        s'adressent au prédicateur), pas l'archive. Une invite qui reçoit tout produit une
        synthèse de tout, et le pasteur ne saurait plus ce qui vient de lui."""
        ...


@dataclass(slots=True)
class PreachedRecord:
    """Une prédication **qui a eu lieu** — l'archive, propriété de son auteur.

    Ce n'est ni la préparation (ce que j'avais prévu), ni le transcript (ce que j'ai dit) :
    c'est un **fait daté**. `preparation_id` est nullable — on peut prêcher sans avoir
    préparé, et importer un sermon d'avant Dorea.

    ⚠️ **Rien ne s'archive parce qu'une date est passée.** Le Pasteur X a préparé autour de six
    passages proposés et prêché le Psaume 125, qui n'était dans aucun des six. Une archive
    remplie par le calendrier aurait menti dès la première semaine — seul celui qui était en
    chaire sait ce qui a eu lieu."""

    id: UUID
    author_id: UUID
    preached_on: date
    #: NULL = hors église (l'antichambre), comme sur la préparation.
    church_id: UUID | None = None
    preparation_id: UUID | None = None
    pericope_id: UUID | None = None
    book_id: int | None = None
    start_ch: int | None = None
    start_v: int | None = None
    end_ch: int | None = None
    end_v: int | None = None
    #: L'axe **que le pasteur a retenu** — pas le dominant calculé. NULL est un état normal :
    #: hors unité curée, il n'y a aucun axe à retenir, et le rayon « non rangé » le dit.
    axis_code: str | None = None
    theme: str | None = None
    capture_kind: str | None = None


@dataclass(slots=True)
class BookCoverage:
    """Un livre, et ce que ce prédicateur y a fait.

    ⚠️ **Deux nombres qui ne se confondent pas** : `passages` compte des **lieux distincts**
    (prêcher deux fois le même texte n'élargit pas un canon), `preachings` compte des
    **événements**. Un seul nombre mentirait dans un sens ou dans l'autre."""

    book_id: int
    passages: int
    preachings: int
    last_preached_on: date


@dataclass(slots=True)
class AxisTally:
    """Un rayon du rangement doctrinal. `axis_code` à NULL = **non rangé**, et ce rayon
    s'affiche : hors des unités curées il n'y a pas d'axe à retenir, et le cacher ferait
    croire à une distribution complète."""

    axis_code: str | None
    preachings: int
    last_preached_on: date


class ArchiveRepository(Protocol):
    """L'archive de l'auteur. **Clée sur `author_id`**, jamais sur l'église : elle le suit
    s'il change d'assemblée, et survit à la résiliation."""

    async def add(self, record: PreachedRecord) -> None: ...

    async def list_for(self, author_id: UUID, *, limit: int) -> list[PreachedRecord]: ...

    async def coverage(self, author_id: UUID) -> list[BookCoverage]:
        """Où ce prédicateur est allé dans l'Écriture — par **passages distincts**."""
        ...

    async def distribution(self, author_id: UUID) -> list[AxisTally]:
        """Sous quels loci son travail se range — par **prédications**, pas par passages."""
        ...


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


class UnlimitedTierPort(Protocol):
    """La **sortie** du plafond personnel — payer, ou appartenir à une église qui a payé.

    ⚠️ **Elle n'existe pas encore, et c'est écrit ici plutôt que supposé ailleurs.**
    `business_accounts` enregistre une carte prépayée ; il n'y a aucun cycle de facturation,
    aucun prélèvement mensuel. Et l'abonnement d'église est une note de design — le module
    `subscription` que `Tenant.operates_annexes` prétend servir n'a jamais été écrit.

    Le port est donc branché sur `AucuneSortie`, qui répond « non ». Tant qu'il en est ainsi,
    le plafond personnel doit rester haut : un plafond sans sortie n'est pas un plafond, c'est
    un cul-de-sac."""

    async def is_unlimited(self, account_id: UUID) -> bool: ...


class AucuneSortie:
    """La sortie qui n'existe pas encore. **Un état de production, pas une doublure de test.**

    Le jour où la facturation existe, on remplace cette classe par un adaptateur et le plafond
    descend en changeant un nombre. D'ici là, elle dit la vérité."""

    async def is_unlimited(self, account_id: UUID) -> bool:
        return False


class ReservationPort(Protocol):
    """La réservation d'étude (§6) — ce qui empêche de facturer deux fois le même travail."""

    async def reserve(
        self, *, church_id: UUID | None, author_id: UUID, pericope_key: str, at: datetime
    ) -> UUID:
        """Réserve sous une clé **provisoire** — celle de la saisie, faute de mieux."""
        ...

    async def rekey_for(
        self,
        *,
        church_id: UUID | None,
        author_id: UUID,
        provisional_key: str,
        pericope_key: str,
        at: datetime,
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

    async def usage(
        self, church_id: UUID | None, author_id: UUID, at: datetime
    ) -> UsageSnapshot:
        """Le sujet du comptage se **déduit** : l'église s'il y en a une, sinon le compte.

        Les deux arguments plutôt qu'un « sujet » construit par l'appelant : le service
        connaît toujours les deux, et le laisser choisir lequel compte aurait mis la règle
        dans quatre endroits au lieu d'un."""
        ...
