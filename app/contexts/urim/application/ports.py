"""Ce dont le service d'étude a besoin, et qu'il ne sait pas faire lui-même.

La préparation persistée est **maigre par choix** : elle garde les décisions, pas la
trace. Le moteur étant déterministe à corpus constant, la trace se **rejoue** — la
stocker en dupliquerait la vérité et permettrait aux deux de diverger.

C'est aussi pourquoi `corpus_snapshot` est persisté : rejouer contre un corpus qui a
bougé doit se **voir**, pas se deviner.
"""

from __future__ import annotations

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
from app.contexts.urim.engine.state import AxisGloss, PassageSuggestion, Reference


@dataclass(slots=True)
class PreparationRecord:
    """La préparation telle que la base la garde — **les décisions, pas le raisonnement**."""

    id: UUID
    church_id: UUID
    author_id: UUID
    raw_input: str
    entry_mode: str | None = None
    entry_origin: str | None = None
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
    service_date: date | None = None
    service_timezone: str = "Africa/Abidjan"
    status: str = "ouverte"
    opened_at: datetime | None = None
    closed_at: datetime | None = None


@dataclass(slots=True)
class ElementRecord:
    """Un champ du squelette homilétique — libre, jamais imposé."""

    element_code: str
    ordinal: int
    body: str | None = None


@dataclass(slots=True)
class UsageSnapshot:
    """L'état du plafond d'une église à l'instant de la demande.

    `ceiling_reached` est la seule chose que le moteur en voit : il ne connaît ni le
    décompte ni le quota, il sait seulement s'il doit se replier sur le domaine public."""

    window_id: UUID | None = None
    metered_units: int = 0
    ceiling: int = 0
    ceiling_reached: bool = False


@dataclass(slots=True)
class VerseServed:
    """Un verset **rendu au pasteur** — la chose pour laquelle Urim existe.

    Elle manquait : `serve_corpus` annonçait « texte servi depuis une version du domaine
    public », posait `version_id`, et la réponse ne portait que cet identifiant. Le pasteur
    recevait une référence et un UUID à la place de soixante-trois caractères."""

    reference: str
    text: str


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


@dataclass(slots=True)
class StudyDTO:
    """Ce que le pasteur voit — la trace **rejouée**, pas relue."""

    record: PreparationRecord
    outcome: str
    rationale: str
    trace: tuple[tuple[str, str], ...] = ()
    #: `(code, label, rationale, origin)` — la provenance voyage avec l'option, sinon le
    #: client la devine depuis la forme du motif, ce qui marche jusqu'au jour où non.
    options: tuple[tuple[str, str, str, str], ...] = ()
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
    #: Le mode **retenu par l'étage 0** — distinct de la colonne, qui ne porte qu'une
    #: correction du pasteur.
    entry_mode: str | None = None
    #: Vrai quand le corpus a bougé depuis l'ouverture — la trace affichée n'est plus
    #: celle qui a été produite ce jour-là, et le pasteur doit le savoir.
    corpus_drifted: bool = False


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
    original: tuple[tuple[str, int, str, str, str, str], ...] = ()


class StudyRepository(Protocol):
    async def add(self, record: PreparationRecord) -> None: ...

    async def get(self, study_id: UUID) -> PreparationRecord | None: ...

    async def save(self, record: PreparationRecord) -> None: ...

    async def record_attempt(
        self,
        *,
        study_id: UUID,
        input_hash: str,
        candidates: list[str],
        chosen_ref: str | None,
        chosen_by: str | None,
        at: datetime,
    ) -> None:
        """Trace d'une résolution — `chosen_by` dit **qui** a tranché, moteur ou pasteur.

        Ce n'est pas de la journalisation : c'est la provenance. Une référence choisie par
        le moteur et une référence choisie par le pasteur n'ont pas la même autorité, et
        rien d'autre dans le schéma ne les distingue."""
        ...

    async def set_elements(self, study_id: UUID, elements: list[ElementRecord]) -> None: ...

    async def list_elements(self, study_id: UUID) -> list[ElementRecord]: ...

    async def recently_preached_axes(self, author_id: UUID, since: date) -> list[str]: ...


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


class NullVerseResolver:
    """Aucun modèle branché — **un état de production, pas un mode dégradé**.

    Architecture v2 §10 veut Urim utilisable hors ligne sur le domaine public : tablette,
    connexion irrégulière, plafond atteint. Le résolveur déterministe travaille alors seul, et
    le pasteur ne voit pas la différence. L'objet nul vit avec le **port**, pas avec
    l'adaptateur : c'est le contrat qui définit ce que « rien » veut dire."""

    async def resolve(self, text: str) -> Reference | None:
        return None

    async def axes(self, text: str) -> tuple[AxisGloss, ...]:
        return ()

    async def passages(self, text: str) -> tuple[PassageSuggestion, ...]:
        return ()

    async def lever(self, text: str) -> tuple[str, ...]:
        return ()


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


class ReservationPort(Protocol):
    """La réservation d'étude (§6) — ce qui empêche de facturer deux fois le même travail."""

    async def reserve(
        self, *, church_id: UUID, author_id: UUID, pericope_key: str, at: datetime
    ) -> UUID:
        """Réserve sous une clé **provisoire** — celle de la saisie, faute de mieux."""
        ...

    async def rekey_for(
        self,
        *,
        church_id: UUID,
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

    async def usage(self, church_id: UUID, at: datetime) -> UsageSnapshot: ...
