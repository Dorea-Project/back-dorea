"""Le **corpus** — global, immuable, non tenant-scopé.

Ces tables ne portent aucun `church_id`. Le texte de Romains 8 est le même à Abidjan et à Bouaké,
et une église qui ferme n'emporte pas la Bible avec elle.

---

## Les deux règles que ce fichier écrit dans la base

**« Rien ne s'affiche qui n'ait été relu. »** `reviewed_by` / `reviewed_at` sont `NOT NULL` sur
**toute table dont le contenu atteint le pasteur** — péricopes, variantes textuelles, pesées
doctrinales, mises en garde, notes de contexte, faisabilités. Le compte n'est plus donné : il a été
faux deux fois. La règle porte sur une propriété — *ce contenu est-il montré à quelqu'un ?* — pas
sur une liste qu'il faut penser à tenir à jour.

**« Ce qui ne coûte rien à servir n'est jamais plafonné. »** `licence_coherente` interdit par
construction qu'une version du domaine public soit comptée dans le plafond. C'est ce qui rend le
repli LSG 1910 increvable : il n'existe aucun état de la base où le filet serait lui-même bloqué.

---

## Deux écarts assumés par rapport au DDL de la spec

**Les préfixes remplacent le schéma Postgres** (D-A). Le dépôt n'utilise aucun schéma : quatorze
contextes vivent dans `public`. L'argument n'est pas l'uniformité mais la **collision** —
`version`, `language`, `book`, `verse`, `token`, `lemma`, `idf` sont précisément les noms qu'un
autre contexte réclamera.

**Les index trigrammes et plein-texte ne sont pas ici.** `verse_trgm` (`gin_trgm_ops`) et
`verse_fts` (`to_tsvector`) exigent l'extension `pg_trgm` et une expression que SQLite ne sait pas
lire — or la base de test se construit depuis ces modèles. Ils appartiennent au chargement du
corpus, avec les millions de lignes qui les justifient : un index GIN sur une table vide ne sert
personne, et `CREATE EXTENSION` est une décision de déploiement.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    ARRAY,
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

#: `text[]` en Postgres, JSON en SQLite (tests). La sémantique de liste est la même ; seules les
#: opérations ensemblistes côté serveur diffèrent, et aucune requête n'en dépend aujourd'hui.
#:
#: ⚠️ **`none_as_null=True` n'est pas un détail de sérialisation.** Par défaut, le type `JSON`
#: écrit un `None` Python en chaîne JSON `null` — qui, pour SQL, **n'est pas NULL**. La contrainte
#: `confessionnel_borne` (« un caveat confessionnel sans tradition est refusé ») mordait en
#: Postgres et passait en SQLite, où la base de test se construit. Un test l'a montré en
#: refusant de voir l'erreur : exactement le mode de panne que ce dépôt a déjà payé une fois —
#: une garde qui n'existe que là où personne ne la vérifie.
_TEXT_ARRAY = ARRAY(Text).with_variant(JSON(none_as_null=True), "sqlite")

#: `bigserial` en Postgres, `INTEGER PRIMARY KEY` en SQLite — monotone dans les deux cas.
_BIGSERIAL = BigInteger().with_variant(Integer, "sqlite")


# --------------------------------------------------------------------- Langues, livres, versions


class CorpusLanguageModel(Base):
    __tablename__ = "urim_corpus_language"

    code: Mapped[str] = mapped_column(String, primary_key=True)  # 'fra','eng','grc','hbo'
    label: Mapped[str] = mapped_column(String)
    direction: Mapped[str] = mapped_column(String, default="ltr")


class CorpusBookModel(Base):
    __tablename__ = "urim_corpus_book"

    __table_args__ = (
        CheckConstraint("testament IN ('AT','NT','DC')", name="book_testament"),
    )

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)  # 1..66 + deutérocanoniques
    osis_code: Mapped[str] = mapped_column(String, unique=True)  # 'Rom', 'Luke'
    testament: Mapped[str] = mapped_column(String)
    canon_order: Mapped[int] = mapped_column(SmallInteger)


class CorpusBookNameModel(Base):
    """**Aucune abréviation de livre en dur.** Une table, jamais une regex.

    C'est ce que lit `CorpusReader.find_reference_span` : le détecteur d'entrée reconnaît un nom
    de livre parce qu'il est *écrit ici*, dans la langue de l'utilisateur — pas parce qu'un
    développeur francophone a pensé à `Rm`."""

    __tablename__ = "urim_corpus_book_name"

    book_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("urim_corpus_book.id"), primary_key=True
    )
    language: Mapped[str] = mapped_column(
        String, ForeignKey("urim_corpus_language.code"), primary_key=True
    )
    label: Mapped[str] = mapped_column(String)  # 'Romains'
    abbreviations: Mapped[list[str]] = mapped_column(_TEXT_ARRAY)  # {'Rom','Rm','Ro'}


class CorpusVersionModel(Base):
    """Une traduction. `licence_coherente` est une **règle produit écrite dans un `CHECK`**."""

    __tablename__ = "urim_corpus_version"

    __table_args__ = (
        CheckConstraint(
            "translation_kind IN ('formelle','dynamique','original')",
            name="version_translation_kind",
        ),
        CheckConstraint(
            "license_kind IN ('domaine_public','sous_licence')", name="version_license_kind"
        ),
        # Ce qui ne coûte rien à servir n'est jamais plafonné — et le repli ne peut pas céder.
        CheckConstraint(
            "(license_kind = 'domaine_public' AND offline_allowed AND NOT metered)"
            " OR license_kind = 'sous_licence'",
            name="licence_coherente",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    code: Mapped[str] = mapped_column(String, unique=True)  # 'LSG1910','DARBY','SBLGNT'
    language: Mapped[str] = mapped_column(String, ForeignKey("urim_corpus_language.code"))
    label: Mapped[str] = mapped_column(String)
    translation_kind: Mapped[str] = mapped_column(String)
    license_kind: Mapped[str] = mapped_column(String)
    provider: Mapped[str | None] = mapped_column(String, nullable=True)  # NULL si domaine public
    offline_allowed: Mapped[bool] = mapped_column(Boolean)
    metered: Mapped[bool] = mapped_column(Boolean)  # déclenche le plafond
    versification: Mapped[str] = mapped_column(String, default="standard")


class CorpusVerseModel(Base):
    """Le texte. `body_norm` porte la normalisation partagée — sans accents, ponctuation, casse."""

    __tablename__ = "urim_corpus_verse"

    __table_args__ = (
        UniqueConstraint(
            "version_id", "book_id", "chapter", "verse", name="verse_unique_ref"
        ),
        Index("ix_urim_verse_ref", "version_id", "book_id", "chapter", "verse"),
    )

    id: Mapped[int] = mapped_column(_BIGSERIAL, primary_key=True, autoincrement=True)
    version_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("urim_corpus_version.id"))
    book_id: Mapped[int] = mapped_column(SmallInteger, ForeignKey("urim_corpus_book.id"))
    chapter: Mapped[int] = mapped_column(SmallInteger)
    verse: Mapped[int] = mapped_column(SmallInteger)
    body: Mapped[str] = mapped_column(Text)
    body_norm: Mapped[str] = mapped_column(Text)


class CorpusVersificationMapModel(Base):
    """Les traductions ne numérotent pas pareil — titres de psaumes, découpages.

    Lue par la validation de sortie : la comparaison porte sur la référence **traduite**, jamais
    sur la brute. Sans elle, « Psaume 51:12 » est rejeté à tort — ou pire, validé sur le mauvais
    verset."""

    __tablename__ = "urim_corpus_versification_map"

    from_scheme: Mapped[str] = mapped_column(String, primary_key=True)
    to_scheme: Mapped[str] = mapped_column(String, primary_key=True)
    book_id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    from_ch: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    from_v: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    to_ch: Mapped[int] = mapped_column(SmallInteger)
    to_v: Mapped[int] = mapped_column(SmallInteger)


class CorpusIdfModel(Base):
    """Ancres rares : les mots fréquents ne discriminent rien.

    ⚠️ Lexique **biblique**, et c'est pourquoi `known_words` ne le lit pas (S34) : le vocabulaire
    d'une conviction sur l'église d'aujourd'hui — *voiture*, *chômage*, *quartier* — est
    précisément celui qui n'y figure pas."""

    __tablename__ = "urim_corpus_idf"

    language: Mapped[str] = mapped_column(String, primary_key=True)
    token: Mapped[str] = mapped_column(String, primary_key=True)
    idf: Mapped[float] = mapped_column(Float)


class CorpusLemmaModel(Base):
    __tablename__ = "urim_corpus_lemma"

    id: Mapped[int] = mapped_column(_BIGSERIAL, primary_key=True, autoincrement=True)
    language: Mapped[str | None] = mapped_column(String, nullable=True)  # 'grc' | 'hbo'
    lemma: Mapped[str] = mapped_column(String)  # υἱοθεσία
    strong_code: Mapped[str | None] = mapped_column(String, nullable=True)  # G5206
    gloss: Mapped[str | None] = mapped_column(Text, nullable=True)


class CorpusTokenModel(Base):
    __tablename__ = "urim_corpus_token"

    verse_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("urim_corpus_verse.id"),
        primary_key=True,
    )
    position: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    surface: Mapped[str] = mapped_column(String)
    lemma_id: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("urim_corpus_lemma.id"),
        nullable=True,
    )
    morph_code: Mapped[str | None] = mapped_column(String, nullable=True)


# ------------------------------------------------------------------------ Unités littéraires


class CorpusPericopeModel(Base):
    """L'unité littéraire curée — base du bornage (étage 2).

    `rationale NOT NULL` n'est pas une note interne : c'est la phrase que le pasteur lit pour
    comprendre *pourquoi ces bornes-là*. L'étage s'appuie dessus pour motiver chaque option, et
    une péricope sans motif ne devrait pas exister."""

    __tablename__ = "urim_corpus_pericope"

    __table_args__ = (Index("ix_urim_pericope_book", "book_id", "start_ch", "start_v"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    book_id: Mapped[int] = mapped_column(SmallInteger, ForeignKey("urim_corpus_book.id"))
    start_ch: Mapped[int] = mapped_column(SmallInteger)
    start_v: Mapped[int] = mapped_column(SmallInteger)
    end_ch: Mapped[int] = mapped_column(SmallInteger)
    end_v: Mapped[int] = mapped_column(SmallInteger)
    label: Mapped[str | None] = mapped_column(String, nullable=True)
    rationale: Mapped[str] = mapped_column(Text)  # le motif affiché au pasteur
    source_ref: Mapped[str] = mapped_column(Text)
    reviewed_by: Mapped[str] = mapped_column(String)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CorpusTextualVariantModel(Base):
    """Ce que le texte **est** — distinct de ce qu'il veut dire, et de ce dont on débat.

    Cas d'école, Rm 8:1. Le Texte Reçu ajoute « qui ne marchent point selon la chair, mais selon
    l'esprit » ; les textes critiques l'omettent. Sans la clause, « aucune condamnation » est
    **inconditionnel** ; avec elle, c'est une **condition morale**. Deux sermons opposés sur la
    même référence — la version détectée n'est donc pas une information cosmétique.

    `doctrinal_weight` fait le tri de l'affichage : on n'assomme pas le pasteur avec chaque καί
    manquant. Seul `majeur` (et `notable` sur demande) s'affiche ; `nul` jamais."""

    __tablename__ = "urim_corpus_textual_variant"

    __table_args__ = (
        CheckConstraint(
            "doctrinal_weight IN ('nul','notable','majeur')", name="variant_weight"
        ),
        Index("ix_urim_variant_ref", "book_id", "chapter", "verse"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    book_id: Mapped[int] = mapped_column(SmallInteger, ForeignKey("urim_corpus_book.id"))
    chapter: Mapped[int] = mapped_column(SmallInteger)
    verse: Mapped[int] = mapped_column(SmallInteger)
    body: Mapped[str] = mapped_column(Text)  # la portion en question
    families_with: Mapped[list[str]] = mapped_column(_TEXT_ARRAY)  # {'texte_recu'}
    families_without: Mapped[list[str]] = mapped_column(_TEXT_ARRAY)  # {'critique'}
    doctrinal_weight: Mapped[str] = mapped_column(String)
    note: Mapped[str] = mapped_column(Text)  # ce que la variante change, en une phrase
    source_ref: Mapped[str] = mapped_column(Text)  # apparat critique
    reviewed_by: Mapped[str] = mapped_column(String)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


# ------------------------------------------------------------------------------------ Doctrine


class CorpusDoctrinalAxisModel(Base):
    """Les dix **loci** de la théologie systématique — données, jamais un enum de code.

    `ordinal` porte leur ordre traditionnel (Dieu → Christ → Esprit → homme → péché → salut →
    Église → anges → démons → fin), qui est aussi celui d'un plan de catéchèse : l'écran trie par
    force **ou** par ordre canonique, sans le coder en dur."""

    __tablename__ = "urim_corpus_doctrinal_axis"

    code: Mapped[str] = mapped_column(String, primary_key=True)
    label: Mapped[str] = mapped_column(String)
    ordinal: Mapped[int] = mapped_column(SmallInteger, unique=True)


class CorpusDoctrinalBearingModel(Base):
    """Ce qu'une péricope **porte** d'un axe — et ce à quoi elle **résiste**.

    `absent` et `resiste` sont **opposés**, pas voisins : ne rien dire n'est pas résister. C'est
    la valeur qui manquait au schéma d'origine, et sans elle le mode conviction est
    inconstructible — c'est elle qui distingue Urim d'un moteur de proof-texting."""

    __tablename__ = "urim_corpus_doctrinal_bearing"

    __table_args__ = (
        CheckConstraint(
            "strength IN ('dominant','porte','resiste','absent')", name="bearing_strength"
        ),
    )

    pericope_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("urim_corpus_pericope.id"), primary_key=True
    )
    axis_code: Mapped[str] = mapped_column(
        String, ForeignKey("urim_corpus_doctrinal_axis.code"), primary_key=True
    )
    strength: Mapped[str] = mapped_column(String)
    rationale: Mapped[str] = mapped_column(Text)
    source_ref: Mapped[str] = mapped_column(Text)
    reviewed_by: Mapped[str] = mapped_column(String)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CorpusDoctrinalCaveatModel(Base):
    """« Ce que le texte ne dit pas. » Exégétique, ou confessionnel.

    `confessionnel_borne` interdit un caveat confessionnel sans tradition : il ne fuit pas hors de
    la sienne. Il s'affiche pourtant **toujours**, y compris quand la tradition de l'église est
    inconnue (D-F) — la formulation le rend possible : « ici les traditions divergent », jamais
    « votre tradition dit X »."""

    __tablename__ = "urim_corpus_doctrinal_caveat"

    __table_args__ = (
        CheckConstraint(
            "caveat_kind IN ('exegetique','confessionnel')", name="caveat_kind_clos"
        ),
        CheckConstraint(
            "caveat_kind = 'exegetique' OR tradition_scope IS NOT NULL",
            name="confessionnel_borne",
        ),
        Index("ix_urim_caveat_pericope", "pericope_id", "axis_code"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    pericope_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("urim_corpus_pericope.id"))
    axis_code: Mapped[str] = mapped_column(
        String, ForeignKey("urim_corpus_doctrinal_axis.code")
    )
    body: Mapped[str] = mapped_column(Text)
    caveat_kind: Mapped[str] = mapped_column(String)
    tradition_scope: Mapped[list[str] | None] = mapped_column(
        _TEXT_ARRAY, nullable=True
    )  # NULL = toutes traditions
    source_ref: Mapped[str] = mapped_column(Text)
    reviewed_by: Mapped[str] = mapped_column(String)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CorpusReviewModel(Base):
    """Le **registre de relecture** — ce qu'un humain a jugé, et qui ne se rejuge pas.

    Le détecteur d'écarts signale ; il ne décide de rien. Sans cette table, sa file recalcule
    les mêmes unités à chaque passage : un relecteur qui en traite cinquante retrouve les mêmes
    le lendemain, et **une file qui ne décroît pas n'est pas une file, c'est un reproche
    permanent**. Apocalypse 5 porte réellement huit loci ; il faut pouvoir le dire une fois.

    ⚠️ **`judged_fingerprint` périme le verdict quand ce qu'il jugeait change.** Accepter les
    pesées d'Apocalypse 5 juge *celles-là* ; une régénération les réécrit, et l'accord ne vaut
    plus. Sans empreinte, un verdict posé une fois protégerait indéfiniment une curation qu'il
    n'a jamais vue. Même patron que `corpus_snapshot` et que `input_hash` sur les suggestions —
    *une décision ne vaut que sur l'objet qu'elle a regardé*.

    **Son second usage vaut plus que le premier.** Ce module promet que les pesées et les mises
    en garde « restent à quelqu'un qui répond de ce qu'il affirme » ; 45 557 d'entre elles sont
    signées `ia-mistral`. Cette table est la seule chose qui saura dire quelle part du corpus un
    humain a réellement relue — et donc de combien la promesse est en retard sur le fait.
    """

    __tablename__ = "urim_corpus_review"

    __table_args__ = (
        CheckConstraint(
            "verdict IN ('accepte','corrige','a_reprendre')", name="review_verdict_clos"
        ),
        # Le cœur du dispositif : une machine ne vide pas la file qu'elle a remplie.
        CheckConstraint("reviewed_by <> 'ia-mistral'", name="review_signature_humaine"),
        Index("ix_urim_review_verdict", "verdict", "reviewed_at"),
    )

    pericope_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("urim_corpus_pericope.id"), primary_key=True
    )
    #: Le détecteur jugé (`D1`…`D5`), ou `ensemble` pour une relecture de l'unité entière.
    #: Explicite plutôt que NULL : sous PostgreSQL deux NULL ne s'égalent pas, et la clé
    #: primaire aurait laissé passer autant de doublons qu'on en aurait écrit.
    scope: Mapped[str] = mapped_column(String, primary_key=True)
    verdict: Mapped[str] = mapped_column(String)
    judged_fingerprint: Mapped[str] = mapped_column(String(32))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[str] = mapped_column(String)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CorpusContextNoteModel(Base):
    """**Sourcé, ou absent.** Il n'y a pas de troisième possibilité (S40).

    Ni contexte reconstitué, ni « on suppose que ». Un contexte historique inventé est le genre
    d'erreur qu'un pasteur répète en chaire avec assurance, parce qu'elle avait l'air documentée.

    `ordinal` : l'ordre de lecture appartient au curateur, pas à un tri par identifiant."""

    __tablename__ = "urim_corpus_context_note"

    __table_args__ = (
        CheckConstraint(
            "context_kind IN ('historique','litteraire')", name="context_note_kind"
        ),
        UniqueConstraint(
            "pericope_id", "context_kind", "ordinal", name="context_note_ordre"
        ),
        Index("ix_urim_context_note_pericope", "pericope_id", "ordinal"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    #: Intégrité applicative (§3.9) — jamais de FK : le corpus est destiné à migrer vers une base
    #: de lecture séparée, et cette table a été écrite après cette décision.
    pericope_id: Mapped[UUID] = mapped_column(Uuid)
    context_kind: Mapped[str] = mapped_column(String)
    body: Mapped[str] = mapped_column(Text)
    ordinal: Mapped[int] = mapped_column(SmallInteger)
    source_ref: Mapped[str] = mapped_column(Text)
    reviewed_by: Mapped[str] = mapped_column(String)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


# -------------------------------------------------------------- Homilétique — deux axes


class CorpusPlanSourceModel(Base):
    """'textuel', 'expositif', 'thematique' — d'où le plan tire sa structure."""

    __tablename__ = "urim_corpus_plan_source"

    code: Mapped[str] = mapped_column(String, primary_key=True)


class CorpusSubjectMatterModel(Base):
    """'biographique','doctrinal','ethique','historique','typologique','prophetique'."""

    __tablename__ = "urim_corpus_subject_matter"

    code: Mapped[str] = mapped_column(String, primary_key=True)


class CorpusHomileticFeasibilityModel(Base):
    """Un couple impossible produit un **refus motivé**, jamais un plan fabriqué.

    La faisabilité n'est pas une propriété du texte mais d'un **triplet** : `Romains 8:9-17` ne
    porte aucun personnage, donc `x biographique` ne produit pas un plan.

    **C'est la seule table curée dont le contenu oppose un refus à quelqu'un** — et c'était la
    seule sans signature (S39). Un « ce passage ne porte aucun personnage » qui ne répond de
    personne est une décision anonyme prise contre le travail d'un pasteur. `proof_text_risk`
    aussi : c'est un jugement sur le risque de ce travail."""

    __tablename__ = "urim_corpus_homiletic_feasibility"

    __table_args__ = (
        CheckConstraint(
            "proof_text_risk IN ('faible','moyen','eleve')", name="feasibility_risk"
        ),
        CheckConstraint(
            "feasible OR refusal_reason IS NOT NULL", name="refus_motive"
        ),
    )

    pericope_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("urim_corpus_pericope.id"), primary_key=True
    )
    plan_source: Mapped[str] = mapped_column(
        String, ForeignKey("urim_corpus_plan_source.code"), primary_key=True
    )
    subject_matter: Mapped[str] = mapped_column(
        String, ForeignKey("urim_corpus_subject_matter.code"), primary_key=True
    )
    feasible: Mapped[bool] = mapped_column(Boolean)
    refusal_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    proof_text_risk: Mapped[str | None] = mapped_column(String, nullable=True)
    reviewed_by: Mapped[str] = mapped_column(String)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
