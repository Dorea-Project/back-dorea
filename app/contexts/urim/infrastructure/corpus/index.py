"""L'index du corpus — **chargé une fois, servi à froid**.

Les cinq ports de `EngineDeps` sont **synchrones** (`def`, pas `async def`), et c'est
délibéré : `UrimEngine.run` est pure, elle ne doit ni attendre ni ouvrir de connexion.
Une lecture SQL au milieu d'un étage rendrait le moteur non déterministe et
non rejouable.

La sortie n'est donc pas « rendre les ports async », mais **charger avant** :

    chargeur async  →  CorpusIndex (gelé)  →  lecteurs purs  →  run()

Ce que cela suppose est vrai par construction : le corpus est **immuable** (versions,
texte, original) et la curation est **petite** parce qu'elle est relue à la main. Un index
se charge une fois par processus et se sert ensuite sans toucher la base — c'est aussi ce
qui donne enfin un sens à `snapshot()`, qui devient l'empreinte de ce qui a réellement été
lu.

Ce qui **ne** peut pas être préchargé — les axes récemment prêchés d'un auteur, le
plafond d'usage d'une église — n'est pas du corpus : cela vit dans `RequestScope`, chargé
par requête.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.urim.engine.deps import (
    AxisBearing,
    BearingSite,
    ContextNote,
    DoctrinalAxis,
    Feasibility,
)
from app.contexts.urim.engine.state import Bounds, Reference
from app.contexts.urim.infrastructure.persistence.corpus_models import (
    CorpusBookModel,
    CorpusBookNameModel,
    CorpusContextNoteModel,
    CorpusDoctrinalAxisModel,
    CorpusDoctrinalBearingModel,
    CorpusDoctrinalCaveatModel,
    CorpusHomileticFeasibilityModel,
    CorpusIdfModel,
    CorpusLemmaModel,
    CorpusPericopeModel,
    CorpusTextualVariantModel,
    CorpusTokenModel,
    CorpusVerseModel,
    CorpusVersificationMapModel,
    CorpusVersionModel,
)

#: Le schéma dans lequel le pasteur écrit ses références, et que tout le produit tient.
#: Les tables de correspondance partent toutes de lui (`from_scheme`).
SCHEMA_DE_REFERENCE = "LSG"

#: Part maximale du corpus qu'un mot peut couvrir pour rester dans l'index inverse.
#: Au-dela, il ne designe plus rien — « et », « de », « le » sont dans un verset sur deux.
_PART_MAX_POSTINGS = 0.05


@dataclass(frozen=True, slots=True)
class VerseRow:
    """Un verset, avec ses tokens déjà normalisés — la forme sur laquelle on compare."""

    book_id: int
    chapter: int
    verse: int
    body: str
    tokens: frozenset[str]

    #: Les mêmes mots **dans l'ordre** — l'ensemble ne peut pas répondre à la contiguïté.
    #:
    #: Un sac de mots dit qu'une saisie *emploie* le vocabulaire d'un verset ; il ne peut pas
    #: dire qu'elle le **cite**. Avec 31 000 versets, presque toute phrase religieuse trouve un
    #: verset qui partage ses mots — c'est ce qui a fait lire « l'amour fraternel n'existe plus
    #: dans l'église » comme une citation possible. La séquence tranche : citer, c'est
    #: reprendre des mots **qui se suivent**.
    sequence: tuple[str, ...] = ()

    #: Poids total du verset (somme des idf de ses tokens) — ce qu'il « pèse » entier.
    #:
    #: Sans lui, on ne peut mesurer que *« combien de la saisie est dans ce verset »*, et
    #: un verset long l'emporte toujours : Matthieu 26:75 contient « Jésus » et « pleura »
    #: au milieu de vingt autres mots, et battait Jean 11:35 qui **est** « Jésus pleura ».
    weight: float = 0.0


@dataclass(frozen=True, slots=True)
class VariantRow:
    """Une variante textuelle — **ce que le texte EST**, pas ce qu'on en pense.

    S17 : le Texte Reçu ajoute à Romains 8:1 « qui ne marchent pas selon la chair », et la
    non-condamnation devient conditionnelle. *Sans la clause elle est inconditionnelle ; avec
    elle c'est une condition morale — deux sermons opposés.* La table existait depuis le début
    et **aucun étage ne la lisait** : l'information n'atteignait jamais le pasteur.

    Elle n'a pas à entrer dans le raisonnement d'un étage. Une variante ne se décide pas, elle
    **se montre** — à côté du texte, au moment où il est servi."""

    book_id: int
    chapter: int
    verse: int
    body: str
    families_with: tuple[str, ...]
    families_without: tuple[str, ...]
    doctrinal_weight: str
    note: str
    source_ref: str


@dataclass(frozen=True, slots=True)
class PericopeRow:
    """Une unité littéraire curée. `rationale` n'est jamais vide — la base l'interdit."""

    id: UUID
    book_id: int
    start_ch: int
    start_v: int
    end_ch: int
    end_v: int
    label: str
    rationale: str
    #: ⚠️ **Qui a signé** — et il faut que ça remonte jusqu'au pasteur.
    #:
    #: `reviewed_by NOT NULL` n'a jamais exigé un humain : il exige une signature, et les huit
    #: unités de démonstration portaient `semis-demo`. Le découpage produit par le modèle porte
    #: `ia-mistral`, ce qui est plus honnête — à une condition, que la distinction soit
    #: **visible**. Un pasteur qui ne peut pas distinguer une structure générée d'une structure
    #: relue a perdu exactement l'information que cette colonne existe pour porter.
    reviewed_by: str = ""


@dataclass(frozen=True, slots=True)
class OriginalWord:
    """Un mot de l'original, tel que le pasteur le voit en cliquant sur un verset.

    ⚠️ `parsing` est le **code brut** de MorphGNT ; c'est `morphology.decrire` qui le rend
    lisible, et le décodage vit à la présentation. Garder le code ici permet de changer la
    façon de le dire sans retoucher au corpus — et de vérifier une traduction contestée contre
    la source."""

    position: int
    surface: str
    lemma: str
    pos: str
    parsing: str

    #: ⚠️ **La langue décide du décodeur**, et les deux formats n'ont rien en commun : le grec
    #: range huit dimensions à position fixe, l'hébreu empile des morphèmes séparés par `/`.
    #: Lire l'un avec la grille de l'autre ne lève aucune erreur — ça produit une glose
    #: grammaticale fausse, c'est-à-dire exactement ce qu'un pasteur répète sans le vérifier.
    language: str = "grc"


@dataclass(frozen=True, slots=True)
class Temoin:
    """Un second témoin — **sa numérotation, et pas son texte**.

    Ce qu'il faut savoir d'une autre traduction pour répondre honnêtement à *« où range-t-elle
    cette référence ? »* tient dans deux choses : les correspondances qu'un humain a validées, et
    les versets qu'elle tient réellement. Charger en plus ses 31 000 versets serait payer
    d'avance une décision qui n'est pas prise — **servir** un second texte est une autre affaire
    que savoir où il range ses numéros.
    """

    code: str
    #: `(livre, chapitre) → les numéros de verset réellement tenus`. Pas un intervalle : une
    #: traduction saute des numéros (Darby n'a pas Actes 8:37, le texte critique ne le porte pas).
    tenus: Mapping[tuple[int, int], frozenset[int]]
    #: Référence **du schéma de référence** → `(chapitre, verset)` chez ce témoin.
    correspondances: Mapping[tuple[int, int, int], tuple[int, int]]


@dataclass(frozen=True, slots=True)
class CorpusIndex:
    """Tout ce que les lecteurs ont besoin de savoir — gelé, sans connexion."""

    snapshot: str

    #: Version de repli — domaine public, donc jamais plafonnée (`licence_coherente`).
    fallback_version_id: UUID
    metered_versions: frozenset[UUID]

    #: Formes normalisées d'un nom de livre → les livres qu'elles peuvent désigner.
    #: Plusieurs, **souvent** : « rois » désigne les deux, « jean » en désigne quatre (S24).
    books_by_form: Mapping[tuple[str, ...], tuple[int, ...]]
    #: Les mêmes formes, triées du plus long au plus court — le plus long gagne (S35).
    forms_by_length: tuple[tuple[str, ...], ...]

    label_by_book: Mapping[int, str]
    book_by_label: Mapping[str, int]
    osis_by_book: Mapping[int, str]

    #: Ce que le corpus **tient réellement** — distinct de ce que le canon compte.
    chapters_held: Mapping[int, frozenset[int]]
    max_verse_held: Mapping[tuple[int, int], int]

    idf: Mapping[str, float]
    verses: tuple[VerseRow, ...]

    #: Index inversé : token → indices dans `verses`. **Seulement les mots discriminants.**
    #:
    #: Sur 31 170 versets, comparer la saisie à chacun coûte trop cher pour ce que ça
    #: rapporte : un mot présent dans un verset sur trois ne désigne rien. On n'indexe donc
    #: que les tokens sous `_PART_MAX_POSTINGS`, et ce sont précisément ceux qui portent
    #: l'information — les ancres rares dont `resolve_citation` a besoin. Les mots très
    #: fréquents continuent de **peser dans le score**, ils ne servent plus à **trouver** les
    #: candidats.
    postings: Mapping[str, tuple[int, ...]]

    pericopes: tuple[PericopeRow, ...]
    bearings: Mapping[UUID, tuple[AxisBearing, ...]]
    caveats: Mapping[UUID, tuple[str, ...]]
    notes: Mapping[UUID, tuple[ContextNote, ...]]
    couples: Mapping[UUID, tuple[Feasibility, ...]]
    dominant: Mapping[UUID, str]

    #: Les variantes, clées sur **le verset** — pas sur la péricope : une variante porte sur
    #: un mot du texte, elle existe que le passage soit curé ou non.
    variants: Mapping[tuple[int, int, int], tuple[VariantRow, ...]] = field(
        default_factory=dict
    )

    #: Les dix loci, dans l'ordre canonique — l'écran de base du mode conviction (S12).
    axes: tuple[DoctrinalAxis, ...] = ()
    #: Le chemin **inverse** des pesées : axe → unités qui en disent quelque chose.
    #:
    #: `absent` n'y figure pas : ne rien dire d'un axe n'est pas en être un candidat. En
    #: revanche `resiste` y figure **au même rang** que `porte` — c'est toute la protection
    #: du mode conviction, et elle ne dépend pas de la justesse de l'axe retenu.
    sites_by_axis: Mapping[str, tuple[BearingSite, ...]] = field(default_factory=dict)

    #: Les mots de l'original, par `(book_id, chapitre, verset)` — le grec du NT aujourd'hui,
    #: l'hébreu quand il sera semé. Vide sur l'AT, et c'est un état normal qui se voit.
    originals: Mapping[tuple[int, int, int], tuple[OriginalWord, ...]] = field(
        default_factory=dict
    )

    #: **L'index inverse du lemme** — `ἀγαπάω` → où il paraît, dans l'ordre du canon.
    #:
    #: C'est la concordance, et c'est la seule réponse à *« qu'est-ce que ce mot veut dire ? »*
    #: qui ne puisse rien inventer. `ὑπόδημα` compte dix occurrences : Jean-Baptiste indigne
    #: de délier la sandale — la tâche de l'esclave —, les disciples envoyés sans sandales, et
    #: le père qui fait **chausser** son fils revenu se proposer comme mercenaire. La culture
    #: matérielle du texte s'enseigne par sa récurrence, sans qu'aucune note ait à l'affirmer.
    #:
    #: `(book_id, chapitre, verset, rang du mot dans le verset)`.
    occurrences_by_lemma: Mapping[str, tuple[tuple[int, int, int, int], ...]] = field(
        default_factory=dict
    )

    #: Les autres traductions semées, par code — leur numérotation seule (voir `Temoin`).
    temoins: Mapping[str, Temoin] = field(default_factory=dict)

    # -- comptages : LUS DANS LE TEXTE, jamais ailleurs ---------------------------
    #
    # Il a existé ici un `canon.py` portant 66 comptes de chapitres écrits à la main,
    # parce que le corpus semé était partiel et ne pouvait pas répondre. C'était le
    # symptôme, pas la solution : un corpus partiel ne sait pas dire *« ce verset
    # n'existe pas »*, il sait seulement dire *« je ne l'ai pas »* — et il disait le
    # premier en pensant le second, ce qui accusait la mémoire du pasteur d'une lacune
    # qui était la nôtre. La Bible entière chargée, le fichier a disparu.

    def chapter_count(self, book_id: int) -> int | None:
        tenus = self.chapters_held.get(book_id)
        return max(tenus) if tenus else None

    def verse_count(self, book_id: int, chapter: int) -> int | None:
        """Le dernier verset de ce chapitre, **d'après le texte**.

        `None` quand le corpus ne tient pas le chapitre — et ne pas savoir n'est pas un
        motif d'écarter : le moteur ne rejette que ce qu'il sait faux."""
        return self.max_verse_held.get((book_id, chapter))

    def holds(self, book_id: int, chapter: int) -> bool:
        return chapter in self.chapters_held.get(book_id, frozenset())

    def reference_chez(
        self, code: str, book_id: int, chapter: int, verse: int
    ) -> tuple[int, int] | None:
        """Où ce témoin range la référence — ou `None` s'il ne la tient pas.

        🔴 **`None` est une réponse, et c'est la bonne.** Deux façons de se tromper, que cette
        méthode ferme l'une après l'autre :

            Exode 7:26      existe dans la Segond, pas dans Ostervald qui l'a poussé en 8:1.
                            L'identité seule rendrait un 7:26 qui n'existe pas.
            Ézéchiel 43:27  existe chez Martin, mais y porte DEUX versets fondus dont le 25.
                            L'identité seule rendrait du texte — le mauvais.

        D'où l'ordre : la table propose, **le texte réellement tenu tranche**, et le silence
        conclut. Rendre le mauvais verset sous la bonne référence est la seule faute que ce
        corpus refuse ; ne rien rendre se voit, se dit, et n'enseigne rien de faux.

        La table et l'identité sont vérifiées **de la même façon** : une correspondance qui
        pointerait sur un verset absent ne vaut pas mieux qu'une identité qui le fait.
        """
        temoin = self.temoins.get(code)
        if temoin is None:
            return None
        cible = temoin.correspondances.get((book_id, chapter, verse), (chapter, verse))
        if cible[1] in temoin.tenus.get((book_id, cible[0]), frozenset()):
            return cible
        return None


async def load_corpus_index(session: AsyncSession) -> CorpusIndex:
    """Lit tout le corpus curé en une passe et le gèle."""
    versions = (await session.execute(select(CorpusVersionModel))).scalars().all()
    if not versions:
        raise CorpusVideError(
            "Le corpus Urim est vide. Semer avec : python scripts/seed_urim_corpus.py"
        )
    # 🔴 **Le repli se nomme, il ne se tire pas au sort.** `next(...)` sur un `select` sans
    # `order_by` rendait la première ligne **physique**. Tant qu'une seule version était en
    # domaine public le résultat était juste par construction ; elles sont quatre, et c'était
    # donc l'ordre d'insertion qui décidait ce que le produit sert. Un `--purge` de la Segond,
    # un `VACUUM FULL`, et le pasteur lisait Martin sans que rien ne le dise.
    repli = next((v for v in versions if v.code == SCHEMA_DE_REFERENCE), None) or next(
        (
            v
            for v in sorted(versions, key=lambda v: v.code)
            if v.license_kind == "domaine_public"
        ),
        None,
    )
    if repli is None:
        raise CorpusVideError(
            f"Aucune version de repli : ni « {SCHEMA_DE_REFERENCE} », ni domaine public. "
            "Semer avec : python scripts/seed_urim_corpus.py"
        )

    books = (await session.execute(select(CorpusBookModel))).scalars().all()
    noms = (
        await session.execute(
            select(CorpusBookNameModel).where(CorpusBookNameModel.language == "fr")
        )
    ).scalars().all()

    label_by_book = {n.book_id: n.label for n in noms}
    osis_by_book = {b.id: b.osis_code for b in books}
    book_by_label = {label: book_id for book_id, label in label_by_book.items()}

    # --- les formes d'appel d'un livre ------------------------------------------
    #
    # Deux passes. La première enregistre les formes telles qu'elles sont curées. La
    # seconde enregistre les formes **dénudées de leur chiffre** : « 1rois » donne aussi
    # « rois », qui désigne alors les deux livres. C'est ce qui fait que « Roi » seul
    # ouvre sur 1 et 2 Rois au lieu de ne rien trouver (S24) — l'ambiguïté est **produite
    # exprès**, elle n'est pas un accident de recherche.
    formes: dict[tuple[str, ...], set[int]] = defaultdict(set)
    for n in noms:
        for brute in n.abbreviations:
            tok = tuple(brute.split())
            if not tok:
                continue
            formes[tok].add(n.book_id)
            nu = tok[1:] if tok[0].isdigit() else (tok[0].lstrip("0123456789"), *tok[1:])
            nu = tuple(t for t in nu if t)
            if nu and nu != tok and len("".join(nu)) >= 2:
                formes[nu].add(n.book_id)

    canon = {b.id: b.canon_order for b in books}
    books_by_form = {
        forme: tuple(sorted(ids, key=lambda i: canon.get(i, 0)))
        for forme, ids in formes.items()
    }
    forms_by_length = tuple(sorted(books_by_form, key=len, reverse=True))

    # --- le texte ----------------------------------------------------------------
    lignes = (
        await session.execute(
            select(CorpusVerseModel).where(CorpusVerseModel.version_id == repli.id)
        )
    ).scalars().all()
    # L'idf se charge **avant** les versets : il faut peser chaque verset entier, et on ne
    # pese pas sans la balance.
    idf = {
        r.token: r.idf
        for r in (
            await session.execute(select(CorpusIdfModel).where(CorpusIdfModel.language == "fr"))
        ).scalars()
    }

    verses = []
    for v in lignes:
        suite = tuple(v.body_norm.split())
        mots = frozenset(suite)
        verses.append(VerseRow(
            v.book_id, v.chapter, v.verse, v.body, mots,
            sequence=suite,
            weight=sum(idf.get(m, 0.0) for m in mots),
        ))
    verses = tuple(verses)

    chapters_held: dict[int, set[int]] = defaultdict(set)
    max_verse_held: dict[tuple[int, int], int] = {}
    brut: dict[str, list[int]] = defaultdict(list)
    for rang, v in enumerate(verses):
        chapters_held[v.book_id].add(v.chapter)
        cle = (v.book_id, v.chapter)
        max_verse_held[cle] = max(max_verse_held.get(cle, 0), v.verse)
        for token in v.tokens:
            brut[token].append(rang)

    plafond = max(1, int(len(verses) * _PART_MAX_POSTINGS))
    postings = {t: tuple(r) for t, r in brut.items() if len(r) <= plafond}

    # --- l'original ---------------------------------------------------------------
    #
    # Le grec du NT (MorphGNT), l'hébreu quand il sera semé. Chargé avec le reste plutôt que
    # lu par requête : les ports du moteur sont synchrones, et l'exploration d'un passage doit
    # répondre sans toucher la base — c'est toute la raison d'être de cet index.
    originaux: dict[tuple[int, int, int], list[OriginalWord]] = defaultdict(list)
    par_lemme: dict[str, list[tuple[int, int, int, int]]] = defaultdict(list)
    lignes_mots = await session.execute(
        select(
            CorpusVerseModel.book_id, CorpusVerseModel.chapter, CorpusVerseModel.verse,
            CorpusTokenModel.position, CorpusTokenModel.surface,
            CorpusLemmaModel.lemma, CorpusTokenModel.morph_code,
            CorpusLemmaModel.language,
        )
        .join(CorpusTokenModel, CorpusTokenModel.verse_id == CorpusVerseModel.id)
        .join(CorpusLemmaModel, CorpusLemmaModel.id == CorpusTokenModel.lemma_id)
        .order_by(CorpusVerseModel.book_id, CorpusVerseModel.chapter,
                  CorpusVerseModel.verse, CorpusTokenModel.position)
    )
    for rang, chapitre, verset, position, surface, lemme, code, langue in lignes_mots:
        # ⚠️ `nature|parsing` est la convention du **grec** — l'hébreu porte son code OSHM
        # entier, sans barre verticale. `partition` rend alors le tout en `nature` et rien en
        # `parsing` ; c'est `language` qui tranche à la présentation, pas la forme du code.
        nature, _, parsing = (code or "|").partition("|")
        cle = (rang, chapitre, verset)
        par_lemme[lemme].append((rang, chapitre, verset, len(originaux[cle])))
        originaux[cle].append(
            OriginalWord(position, surface, lemme, nature, parsing, langue or "grc")
        )
    originals = {cle: tuple(mots) for cle, mots in originaux.items()}
    occurrences_by_lemma = {lemme: tuple(lieux) for lemme, lieux in par_lemme.items()}

    # --- la curation --------------------------------------------------------------
    peri = (await session.execute(select(CorpusPericopeModel))).scalars().all()
    pericopes = tuple(
        PericopeRow(
            p.id, p.book_id, p.start_ch, p.start_v, p.end_ch, p.end_v,
            p.label or "", p.rationale, p.reviewed_by,
        )
        for p in sorted(peri, key=lambda p: (p.book_id, p.start_ch, p.start_v, p.end_ch, p.end_v))
    )

    axes = tuple(
        DoctrinalAxis(a.code, a.label, a.ordinal)
        for a in (
            await session.execute(
                select(CorpusDoctrinalAxisModel).order_by(CorpusDoctrinalAxisModel.ordinal)
            )
        ).scalars()
    )

    par_id = {p.id: p for p in pericopes}
    bearings: dict[UUID, list[AxisBearing]] = defaultdict(list)
    dominant: dict[UUID, str] = {}
    sites: dict[str, list[BearingSite]] = defaultdict(list)
    for b in (await session.execute(select(CorpusDoctrinalBearingModel))).scalars():
        bearings[b.pericope_id].append(
            AxisBearing(b.axis_code, _libelle_axe(b.axis_code), b.strength, b.rationale)
        )
        if b.strength == "dominant":
            dominant[b.pericope_id] = b.axis_code

        # Le chemin inverse. `absent` est écarté — ne rien dire d'un axe n'est pas en être
        # un candidat — mais `resiste` est **retenu** : c'est là que vit la protection.
        unite = par_id.get(b.pericope_id)
        if unite is not None and b.strength != "absent":
            livre = label_by_book.get(unite.book_id, "")
            sites[b.axis_code].append(BearingSite(
                pericope_id=unite.id,
                label=unite.label,
                bounds=Bounds(
                    start=Reference(livre, unite.start_ch, unite.start_v),
                    end=Reference(livre, unite.end_ch, unite.end_v),
                ),
                strength=b.strength,
                rationale=b.rationale,
            ))

    # Trié `dominant` → `porte` → `resiste`, puis par ordre du canon. **Ce n'est pas un
    # enterrement** : les trois forces s'affichent nommées, et l'étage rend la liste
    # entière. Un texte dont l'axe est le sujet sert mieux qu'un texte qui l'effleure ;
    # celui qui résiste reste visible, et c'est tout ce que S10 exige.
    rang = {"dominant": 0, "porte": 1, "resiste": 2}

    def _ordre(s: BearingSite) -> tuple[int, str, int]:
        return (rang.get(s.strength, 9), s.bounds.start.book, s.bounds.start.chapter or 0)

    sites_by_axis = {axe: tuple(sorted(liste, key=_ordre)) for axe, liste in sites.items()}

    caveats: dict[UUID, list[str]] = defaultdict(list)
    for c in (await session.execute(select(CorpusDoctrinalCaveatModel))).scalars():
        caveats[c.pericope_id].append(c.body)

    notes: dict[UUID, list[ContextNote]] = defaultdict(list)
    for note in (
        await session.execute(
            select(CorpusContextNoteModel).order_by(CorpusContextNoteModel.ordinal)
        )
    ).scalars():
        notes[note.pericope_id].append(
            ContextNote(note.context_kind, note.body, note.source_ref)
        )

    couples: dict[UUID, list[Feasibility]] = defaultdict(list)
    for f in (await session.execute(select(CorpusHomileticFeasibilityModel))).scalars():
        couples[f.pericope_id].append(
            Feasibility(
                f.plan_source, f.subject_matter, f.feasible,
                f.refusal_reason or "", f.proof_text_risk or "",
            )
        )

    variants: dict[tuple[int, int, int], list[VariantRow]] = defaultdict(list)
    for v in (await session.execute(select(CorpusTextualVariantModel))).scalars():
        variants[(v.book_id, v.chapter, v.verse)].append(VariantRow(
            book_id=v.book_id, chapter=v.chapter, verse=v.verse, body=v.body,
            families_with=tuple(v.families_with or ()),
            families_without=tuple(v.families_without or ()),
            doctrinal_weight=v.doctrinal_weight, note=v.note, source_ref=v.source_ref,
        ))

    # --- les témoins seconds : leur numérotation, jamais leur texte ---------------
    #
    # Deux tables, et l'une ne suffit pas sans l'autre : les correspondances disent où un
    # verset a bougé, les versets tenus disent s'il existe. Une table de correspondances est
    # forcément partielle — elle ne porte que ce qu'un humain a validé — donc l'identité reste
    # le cas ordinaire, et c'est justement celui qu'il faut vérifier.
    par_id = {v.id: v.code for v in versions}
    tenus: dict[str, dict[tuple[int, int], set[int]]] = defaultdict(
        lambda: defaultdict(set)
    )
    for version_id, livre, chapitre, verset in await session.execute(
        select(
            CorpusVerseModel.version_id, CorpusVerseModel.book_id,
            CorpusVerseModel.chapter, CorpusVerseModel.verse,
        ).where(CorpusVerseModel.version_id != repli.id)
    ):
        tenus[par_id[version_id]][(livre, chapitre)].add(verset)

    correspondances: dict[str, dict[tuple[int, int, int], tuple[int, int]]] = defaultdict(
        dict
    )
    for lien in (
        await session.execute(
            select(CorpusVersificationMapModel).where(
                CorpusVersificationMapModel.from_scheme == SCHEMA_DE_REFERENCE
            )
        )
    ).scalars():
        correspondances[lien.to_scheme][
            (lien.book_id, lien.from_ch, lien.from_v)
        ] = (lien.to_ch, lien.to_v)

    temoins = {
        code: Temoin(
            code=code,
            tenus={cle: frozenset(v) for cle, v in chapitres.items()},
            correspondances=dict(correspondances.get(code, {})),
        )
        for code, chapitres in sorted(tenus.items())
    }

    derniere = await session.scalar(select(func.max(CorpusPericopeModel.reviewed_at)))

    return CorpusIndex(
        snapshot=_empreinte(
            versions=tuple(sorted(v.code for v in versions)),
            n_verses=len(verses),
            n_pericopes=len(pericopes),
            n_bearings=sum(len(v) for v in bearings.values()),
            derniere_relecture=derniere,
        ),
        fallback_version_id=repli.id,
        metered_versions=frozenset(v.id for v in versions if v.metered),
        books_by_form=books_by_form,
        forms_by_length=forms_by_length,
        label_by_book=label_by_book,
        book_by_label=book_by_label,
        osis_by_book=osis_by_book,
        chapters_held={k: frozenset(v) for k, v in chapters_held.items()},
        max_verse_held=max_verse_held,
        idf=idf,
        verses=verses,
        postings=postings,
        pericopes=pericopes,
        bearings={k: tuple(v) for k, v in bearings.items()},
        caveats={k: tuple(v) for k, v in caveats.items()},
        notes={k: tuple(v) for k, v in notes.items()},
        couples={k: tuple(v) for k, v in couples.items()},
        dominant=dominant,
        variants={k: tuple(v) for k, v in variants.items()},
        axes=axes,
        sites_by_axis=sites_by_axis,
        originals=originals,
        occurrences_by_lemma=occurrences_by_lemma,
        temoins=temoins,
    )


class CorpusVideError(RuntimeError):
    """Le corpus n'a pas été semé — un message qui dit quoi faire, pas juste que ça casse."""


#: Les dix loci, tels que la table de référence les nomme. Le libellé est présenté au
#: pasteur ; le code est ce qui circule dans le moteur.
_LIBELLES = {
    "theologie_propre": "Théologie propre (Dieu)",
    "christologie": "Christologie",
    "pneumatologie": "Pneumatologie",
    "anthropologie": "Anthropologie",
    "hamartiologie": "Hamartiologie",
    "soteriologie": "Sotériologie",
    "ecclesiologie": "Ecclésiologie",
    "angelologie": "Angélologie",
    "demonologie": "Démonologie",
    "eschatologie": "Eschatologie",
}


def _libelle_axe(code: str) -> str:
    return _LIBELLES.get(code, code)


def _empreinte(
    *,
    versions: tuple[str, ...],
    n_verses: int,
    n_pericopes: int,
    n_bearings: int,
    derniere_relecture: datetime | None,
) -> str:
    """L'empreinte de ce qui a été lu — deux corpus identiques la partagent.

    Elle entre dans `StudyState.corpus_snapshot` et fait partie de la clé du déterminisme :
    rejouer une préparation contre un corpus modifié doit se voir, pas se deviner."""
    graine = "|".join((
        ",".join(versions),
        str(n_verses), str(n_pericopes), str(n_bearings),
        derniere_relecture.isoformat() if derniere_relecture else "-",
    ))
    return hashlib.sha256(graine.encode()).hexdigest()[:16]


def verses_between(
    index: CorpusIndex, book_id: int, debut: tuple[int, int], fin: tuple[int, int]
) -> tuple[VerseRow, ...]:
    """Les versets d'un intervalle, dans l'ordre — **la présentation, jamais un étage**.

    Aucun étage n'a besoin du texte : ils raisonnent sur des bornes, des axes et des motifs.
    C'est le pasteur qui a besoin des mots, et cette lecture existe pour lui."""
    return tuple(
        v
        for v in index.verses
        if v.book_id == book_id and debut <= (v.chapter, v.verse) <= fin
    )
