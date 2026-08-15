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
        CheckConstraint(
            "text_family IN ('texte_recu','critique','eclectique','massoretique')",
            name="version_text_family",
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

    #: 🔴 **L'édition que ce témoin suit — un FAIT sur la version, jamais un calcul du produit.**
    #:
    #: Deux traductions qui divergent sur un mot ne disent pas pourquoi elles divergent. La
    #: seule chose qui se sache d'avance, c'est de quelle édition chacune part : Darby suit un
    #: texte critique, Martin et Ostervald le Texte Reçu, la Segond 1910 est **éclectique** —
    #: mesuré, et contraire à ce qu'on croyait : elle omet la clause de Rm 8:1 et le *comma
    #: johanneum* comme Darby, et lit « celui qui » en 1 Tm 3:16 là où les trois autres lisent
    #: « Dieu ».
    #:
    #: ⚠️ **Le produit n'en tire aucune conclusion, et c'est délibéré.** Cette colonne
    #: s'**affiche** à côté de chaque témoin ; elle n'alimente aucun classement, aucun score,
    #: aucun « ceci pourrait être une variante ». Le pasteur lit qui suit quoi et conclut
    #: lui-même. *Le signal informe l'homme, l'homme commande la machine.*
    #:
    #: `massoretique` existe pour l'Ancien Testament, où les quatre témoins partent du même
    #: texte : la question des éditions **ne s'y pose pas**, et c'est la raison pour laquelle
    #: « Darby seul contre les trois autres » n'y voulait rien dire.
    text_family: Mapped[str] = mapped_column(String, default="eclectique")


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
    #: Le sens, **en français** — traduit d'une source publiée, jamais inventé (L1).
    gloss: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: ⚠️ **L'entrée d'origine, mot pour mot.** C'est elle qui rend la traduction
    #: vérifiable — sans elle, la glose française devient à son tour une source, et
    #: personne ne relit une définition grecque avant de la redire en chaire.
    gloss_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: D'où elle vient — `TBESG` (STEPBible, CC BY 4.0). La licence l'exige, et le
    #: pasteur a le droit de savoir qui définit le mot qu'il va prêcher.
    gloss_source_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    #: Qui a traduit. L'équivalent de `corpus_snapshot` : un alias de modèle bouge.
    gloss_model: Mapped[str | None] = mapped_column(String, nullable=True)


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


class CorpusCollisionModel(Base):
    """**Là où deux traducteurs sérieux n'ont pas lu la même chose** — et rien de plus.

    ⚠️⚠️ **Une collision N'EST PAS une variante textuelle, et ne doit jamais être présentée
    comme telle.** La table d'à côté, `urim_corpus_textual_variant`, dit ce que les manuscrits
    portent ; elle se remplit depuis un apparat critique, par un humain qui signe. Celle-ci ne
    dit qu'une chose : *quatre traducteurs de bonne foi ont rendu ce mot différemment.* On
    n'affirme pas qu'un manuscrit porte ceci — on montre que deux hommes ont lu autrement, et le
    pasteur vérifie des deux yeux.

    **Ce n'est pas une prudence de rédaction, c'est une propriété mesurée.** Ce à quoi une
    variante ressemble chez ces quatre témoins, c'est une *proposition entière* présente ou
    absente — la clause de Rm 8:1, la doxologie de Mt 6:13, le *comma johanneum* — donc une
    reformulation, précisément ce que `SUBSTITUTION_MAXIMUM` existe pour rejeter ; ou un verset
    entièrement absent (Mt 23:14, Ac 8:37 chez Darby), qui n'est pas une divergence mais un
    silence. **Le détecteur est structurellement incapable de voir une variante.** Il voit une
    substitution d'un mot par un autre, ce qui est un autre objet : un choix de traducteur.

    ## Ce que la table porte, et ce qu'elle refuse de porter

    Elle porte **la forme du désaccord** — qui lit avec la Segond, qui lit autrement, qui ne se
    prononce pas — et rien sur la *cause*. Il a existé ici un champ « la séparation suit la ligne
    des éditions » ; il est tombé sur la mesure : la ligne ne passe pas où on la croyait (elle
    sépare {Segond, Darby} de {Ostervald, Martin}, pas Darby des trois autres), et sur un texte
    éclectique elle ne se laisse de toute façon pas trancher. Ce qui reste, c'est
    `version.text_family`, affichée à côté de chaque témoin — un fait que le pasteur lit.

    ## Une projection, donc une empreinte

    Cette table est **calculée**, pas curée : elle ne porte pas de `reviewed_by`, personne ne l'a
    signée. Une collision dépend des versions semées — en ajouter une change le résultat — d'où
    `corpus_fingerprint`, même patron que `corpus_snapshot`, `input_hash` et
    `judged_fingerprint` : *une décision ne vaut que sur l'objet qu'elle a regardé.*"""

    __tablename__ = "urim_corpus_collision"

    __table_args__ = (
        # `segond_seule` dit qu'AUCUN témoin qui s'est prononcé ne lit ce mot. Les trois formes
        # décrivent une répartition ; aucune ne nomme une cause.
        CheckConstraint(
            "form IN ('temoin_isole','partage','segond_seule')", name="collision_form_close"
        ),
        CheckConstraint("weight > 0", name="collision_poids_positif"),
        UniqueConstraint("book_id", "chapter", "verse", "word", name="collision_unique"),
        Index("ix_urim_collision_ref", "book_id", "chapter", "verse"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    book_id: Mapped[int] = mapped_column(SmallInteger, ForeignKey("urim_corpus_book.id"))
    chapter: Mapped[int] = mapped_column(SmallInteger)
    verse: Mapped[int] = mapped_column(SmallInteger)

    #: Le mot **de la Segond**, normalisé. Un seul par collision : le plus lourd de l'écart.
    #: Nommer les deux côtés supposerait un appariement positionnel que le texte ne donne pas —
    #: c'est ce qui faisait dire au prototype que Martin lisait « donc » à la place d'un nom
    #: propre.
    word: Mapped[str] = mapped_column(String)
    #: Le poids IDF du mot. Sert au tri et à la relecture du seuil, jamais à l'affichage : un
    #: chiffre à côté d'un verset se lit comme une note, et rien ici n'est noté.
    weight: Mapped[float] = mapped_column(Float)
    form: Mapped[str] = mapped_column(String)

    #: Ce que le détecteur a lu, et donc ce qui périme cette ligne.
    corpus_fingerprint: Mapped[str] = mapped_column(String(32))
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CorpusCollisionWitnessModel(Base):
    """Un témoin devant un mot — **et son verset entier, tel qu'il l'écrit**.

    Le texte est recopié ici plutôt que relu dans `urim_corpus_verse`, pour deux raisons qui
    vont dans le même sens. **L'index ne charge pas les 31 000 versets des autres traductions**
    (`Temoin` ne porte que leur numérotation, délibérément) ; les servir demanderait de payer
    d'avance une décision qui n'est pas prise. Et surtout : *une ligne calculée doit porter ce
    qu'elle a regardé.* Ces quatre textes sont la pièce à conviction — c'est sur eux que le
    pasteur vérifie des deux yeux, et c'est eux que l'empreinte protège.

    ⚠️ **`agrees=False` ne veut pas dire « ce témoin omet le mot ».** Il veut dire : *ce mot-là,
    ni aucune de ses graphies proches, ne se trouve dans son verset.* Ce qu'il écrit à la place
    n'est nommé (`reading`) que lorsque l'écart est **un mot pour un mot** ; sinon la colonne
    reste vide et le verset parle tout seul. Prétendre nommer un remplaçant qu'on n'a pas su
    apparier est la seule façon de rendre cette table menteuse."""

    __tablename__ = "urim_corpus_collision_witness"

    __table_args__ = (
        # 🔴 Le silence est une valeur, pas une absence de ligne. Un témoin qui reformule le
        # verset ou ne le tient pas **s'abstient** — et l'ignorer le ferait compter pour un
        # accord, ce qui est le contraire de ce qu'il a fait.
        CheckConstraint(
            "stance IN ('accorde','diverge','muet')", name="collision_witness_stance"
        ),
        CheckConstraint(
            "stance = 'diverge' OR reading IS NULL", name="collision_lecture_bornee"
        ),
    )

    collision_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("urim_corpus_collision.id"), primary_key=True
    )
    version_code: Mapped[str] = mapped_column(String, primary_key=True)
    stance: Mapped[str] = mapped_column(String)
    #: Le mot qu'il écrit à la place — **seulement quand l'appariement est propre**.
    reading: Mapped[str | None] = mapped_column(String, nullable=True)
    #: Son verset, tel quel. Vide si ce témoin ne tient pas ce verset du tout.
    body: Mapped[str] = mapped_column(Text)


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


class CorpusExaminationModel(Base):
    """**L'examen sans trouvaille** — « on a regardé, et il n'y avait rien à dire ».

    🔴 Le lot des mises en garde a curé 4 396 unités ; 2 525 n'en appelaient aucune, ce qui est
    la bonne réponse. Mais rien ne l'enregistrait : **une unité examinée sans trouvaille était
    indiscernable d'une unité jamais examinée.** Trois conséquences, toutes découvertes après
    coup — la couverture annonçait 41 % pour ~96 % de travail réel ; le lot n'était pas
    reprenable, rattraper 106 unités sautées en aurait refait 2 631 ; et un second passage
    aurait produit d'autres résultats sur des unités déjà jugées vides, sans qu'on sache
    lesquelles croire.

    C'est **exactement** la distinction que les pesées tiennent déjà avec `absent` (S38) —
    *personne n'a regardé* contre *quelqu'un a regardé et le texte n'en dit rien*. Elle y vit
    dans la table de contenu parce qu'`absent` est une information que le pasteur lit, locus par
    locus. Ici elle n'en est pas une : « aucune mise en garde » se dit déjà par une liste vide.
    C'est de la trace de curation, et elle a donc sa propre table.

    Générique par dimension, parce que les notes de contexte — à 0,1 % elles aussi — poseront la
    même question au lot suivant, et qu'une colonne par dimension sur la péricope se paierait
    d'une migration à chaque fois.
    """

    __tablename__ = "urim_corpus_examination"

    __table_args__ = (
        CheckConstraint(
            "dimension IN ('caveat','context_note')", name="examination_dimension_close"
        ),
        CheckConstraint("found >= 0", name="examination_found_positif"),
    )

    pericope_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("urim_corpus_pericope.id"), primary_key=True
    )
    dimension: Mapped[str] = mapped_column(String, primary_key=True)
    #: Ce que **cet** examen a produit — de l'histoire, pas un total vivant. Le compte courant
    #: se lit dans la table de contenu ; celui-ci dit ce que le curateur avait trouvé ce jour-là,
    #: et reste juste même si un relecteur ajoute une ligne demain.
    found: Mapped[int] = mapped_column(Integer)
    examined_by: Mapped[str] = mapped_column(String)
    examined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


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


class CorpusReviewerModel(Base):
    """**Le registre des relecteurs** — ce qui fait qu'une signature n'est plus une chaîne libre.

    🔴 `verifier_verdict()` faisait déjà tout ce qu'un validateur peut faire sur du texte : il
    refuse le vide, les noms de semis, `ia-mistral`. Il n'a jamais pu refuser le nom **de
    quelqu'un d'autre** — et c'est arrivé : un verdict d'essai posé au nom du propriétaire du
    dépôt, qu'il a fallu retirer. Le défaut n'était pas dans le garde, il était en amont : *tant
    que le nom est une donnée d'entrée, aucune vérification ne le sauve.*

    Cette table le sort de l'entrée. Le porteur prouve un secret, la surface **rend** le nom
    correspondant, et aucune route ne lit plus de `reviewed_by` dans un corps de requête.

    ⚠️ **Ce que ça garantit, et ce que ça ne garantit pas.** Pas « c'est bien Untel » — il n'y a
    pas d'identité authentifiée dans ce produit avant la console d'administration Dorea
    (`docs/Dorea_Platform_Admin.md`, comptes staff nominatifs + OTP). Ça garantit qu'on ne signe
    que d'un nom **dont on détient le secret**, et que ce nom se **révoque**. C'est un cran, pas
    la fin ; le jour où la console existe, c'est la source de la dépendance qui change, pas les
    routes.

    `display_name` est unique parce que c'est **lui** qui atterrit dans `reviewed_by` : deux
    relecteurs homonymes rendraient la trace illisible là où elle sert, sous les yeux du pasteur.

    Le secret est haché en SHA-256 **sans dérivation lente, et c'est délibéré** : il n'est pas
    choisi par un humain mais tiré au sort sur 32 octets par `scripts/urim_relecteur.py`. Un
    argon2 protège d'une attaque par dictionnaire ; il n'y a pas de dictionnaire des tirages
    aléatoires. Le jour où un relecteur choisirait son secret, cette ligne devient fausse."""

    __tablename__ = "urim_reviewer"

    __table_args__ = (
        # La machine ne s'enrôle pas. Le `CHECK` de `urim_corpus_review` interdit sa signature
        # sur un verdict ; celui-ci lui interdit d'exister comme signataire possible.
        CheckConstraint(
            "identifiant <> 'ia-mistral' AND display_name <> 'ia-mistral'",
            name="reviewer_jamais_la_machine",
        ),
        UniqueConstraint("display_name", name="reviewer_nom_unique"),
    )

    identifiant: Mapped[str] = mapped_column(String(60), primary_key=True)
    #: Le nom écrit dans `reviewed_by`, et lu par le pasteur.
    display_name: Mapped[str] = mapped_column(String(120))
    secret_hash: Mapped[str] = mapped_column(String(64))
    #: La révocation ne supprime pas la ligne : les verdicts déjà signés doivent continuer de
    #: désigner quelqu'un. On retire le pouvoir de signer, pas la trace d'avoir signé.
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    enrolled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class CorpusSignalModel(Base):
    """**La file d'attente, matérialisée** — ce que les détecteurs ont trouvé au dernier balayage.

    Elle est écrite par `scripts/urim_ecarts.py --materialiser`, jamais par une route. La raison
    est mécanique avant d'être doctrinale : D2 mesure la fréquence d'une tournure sur **tout** le
    corpus, et rien de global ne se recalcule dans le temps d'une requête HTTP. Mais elle est
    doctrinale aussi — *les détecteurs signalent, ils ne jugent pas* : la surface lit cette table,
    elle ne la produit pas, et elle ne la trie pas autrement que par gravité.

    ⚠️ **C'est une photographie, pas un journal.** Chaque balayage remplace le contenu en bloc :
    un signalement qu'un détecteur ne retrouve plus n'a pas à survivre à sa propre disparition.
    D'où `scanned_at`, que la surface expose : *une file dont on ne sait pas l'âge ment.*

    `scan_fingerprint` dit sur quelle curation le signalement a été calculé. Comparée à
    l'empreinte courante, elle distingue un signalement encore vrai d'un signalement qui parle
    d'une ligne réécrite depuis — même patron que `judged_fingerprint`, pour la même raison."""

    __tablename__ = "urim_corpus_signal"

    __table_args__ = (
        CheckConstraint("severity BETWEEN 1 AND 3", name="signal_gravite_bornee"),
        Index("ix_urim_signal_pericope", "pericope_id"),
        Index("ix_urim_signal_gravite", "severity"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    pericope_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("urim_corpus_pericope.id"))
    #: `D1`…`D5` — le code seul, sans le libellé du détecteur : c'est lui que la portée d'un
    #: verdict désigne, et un libellé qui change ne doit pas périmer les verdicts posés.
    detector: Mapped[str] = mapped_column(String(8))
    label: Mapped[str] = mapped_column(String(120))
    severity: Mapped[int] = mapped_column(SmallInteger)
    detail: Mapped[str] = mapped_column(Text)
    #: La ligne de curation entière, quand le détecteur en cite une. Un fragment d'expression
    #: régulière ne se juge pas — c'est ce qui a failli faire refuser huit bonnes mises en garde.
    body: Mapped[str] = mapped_column(Text, default="")
    scan_fingerprint: Mapped[str] = mapped_column(String(32))
    scanned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


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
