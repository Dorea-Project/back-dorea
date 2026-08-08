"""Le travail du pasteur — **tenant + auteur**, quand le corpus n'appartient à personne.

Trois groupes, et la boucle qu'ils forment :

```
préparer  ─────────────►  prêcher  ─────────────►  revoir
preparation, resolution   capture, transcript      reflection
deliverable, reservation  cited_verse              (étapes 2-4 verrouillées)
```

---

## Ce que ce fichier ne fait pas, et pourquoi

**Aucune clé étrangère vers `urim_corpus`** (§3.9). `pericope_id`, `version_id`, `axis_code`,
`book_id`, `plan_source`, `subject_matter` sont des colonnes nues. Le corpus est destiné à migrer
vers une base de lecture séparée dès que les index trigrammes gêneront le transactionnel, et une
FK inter-bases n'existe pas. Intégrité applicative, comme entre contextes.

**Aucune clé étrangère vers un autre contexte.** `church_id` et `author_id` sont des `uuid` nus.

**Les FK internes à `urim` restent** là où la spec les déclare, parce qu'elles portent un
`ON DELETE CASCADE` — un comportement, pas seulement une garantie. Les tables de la capture font
exception : leur propre spécification a choisi l'intégrité applicative partout. L'écart est
délibéré des deux côtés ; il n'est pas un oubli.

---

## Un écart de forme assumé

`preparation.bounds_override` était déclaré `int4range`. Un intervalle d'entiers ne peut pas
exprimer un empan **chapitre + verset** : Galates 5:16 → 6:2 n'est pas un intervalle. Les quatre
colonnes `override_start_ch/_v`, `override_end_ch/_v` disent la même chose, et disent la même
chose que `pericope` et `preached` — qui utilisent déjà quatre colonnes dans la même spec.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
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
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# ============================================================================ 1. PRÉPARER


class UrimPreparationModel(Base):
    """Le travail en cours. `service_timezone` parce qu'**un dimanche est local, pas UTC**."""

    __tablename__ = "urim_preparation"

    __table_args__ = (
        CheckConstraint(
            "entry_mode IN ('reference','citation','conviction')", name="prep_entry_mode"
        ),
        CheckConstraint(
            "status IN ('ouverte','close','abandonnee')", name="prep_status"
        ),
        Index("ix_urim_prep_auteur", "author_id", "opened_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    church_id: Mapped[UUID] = mapped_column(Uuid)
    author_id: Mapped[UUID] = mapped_column(Uuid)  # propriétaire réel
    entry_mode: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_input: Mapped[str] = mapped_column(Text)
    #: Ce que le détecteur d'entrée a cru voir, conservé à côté de ce qu'il a fait. Une entrée
    #: dictée par un micro ouvert ne se corrige pas comme une faute de frappe (S36).
    entry_origin: Mapped[str | None] = mapped_column(String, nullable=True)

    #: L'empreinte du corpus contre lequel cette préparation a été menée.
    #:
    #: Le moteur est déterministe *à corpus constant* : rejouer une préparation après un
    #: enrichissement du corpus produirait une trace différente. Sans cette colonne, la
    #: dérive serait silencieuse — on croirait relire, on recalculerait. Nullable, parce
    #: que les préparations antérieures n'en ont pas et que le prétendre serait faux.
    corpus_snapshot: Mapped[str | None] = mapped_column(String(64), nullable=True)

    #: Colonnes nues — jamais de FK vers le corpus (§3.9).
    pericope_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    version_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    axis_code: Mapped[str | None] = mapped_column(String, nullable=True)
    plan_source: Mapped[str | None] = mapped_column(String, nullable=True)
    subject_matter: Mapped[str | None] = mapped_column(String, nullable=True)

    #: NULL sur les quatre = le bornage proposé a été accepté tel quel.
    override_start_ch: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    override_start_v: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    override_end_ch: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    override_end_v: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    theme: Mapped[str | None] = mapped_column(Text, nullable=True)
    service_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    service_timezone: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class UrimPreparationElementModel(Base):
    """Squelette Braga — dix éléments, **tous facultatifs**.

    Le moteur n'en remplit aucun d'office : un plan qui arrive complet n'est pas un plan que
    quelqu'un a préparé."""

    __tablename__ = "urim_preparation_element"

    preparation_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("urim_preparation.id", ondelete="CASCADE"), primary_key=True
    )
    element_code: Mapped[str] = mapped_column(String, primary_key=True)
    ordinal: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)


class UrimResolutionAttemptModel(Base):
    """**Jamais de résolution silencieuse** : les candidats écartés sont conservés.

    `chosen_by` distingue ce que le moteur a tranché de ce que le pasteur a choisi. C'est la seule
    donnée qui dira, plus tard, si le moteur tranche trop souvent tout seul — et `version_detected`
    à NULL n'est pas un échec, c'est un fait : la version n'a pas été identifiée."""

    __tablename__ = "urim_resolution_attempt"

    __table_args__ = (
        CheckConstraint("chosen_by IN ('moteur','pasteur','ia')", name="attempt_chosen_by"),
        Index("ix_urim_attempt_prep", "preparation_id", "attempted_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    preparation_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("urim_preparation.id", ondelete="CASCADE")
    )
    input_hash: Mapped[str] = mapped_column(String)
    candidates: Mapped[list] = mapped_column(JSON)  # [{ref, score, motif}]
    chosen_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    chosen_by: Mapped[str | None] = mapped_column(String, nullable=True)
    version_detected: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


# ============================================================================ 2. ARCHIVE


class UrimPreachedModel(Base):
    """L'archive — **propriété de l'auteur**.

    `exportable_until NULL` par défaut : l'archive **survit à la résiliation**. Le travail du
    pasteur ne peut pas être pris en otage par le non-renouvellement de son église.

    Les deux index portent les deux vues de l'écran Archive : couverture du canon, et distribution
    doctrinale. C'est aussi ce que lit `recently_preached_axes` — l'étage du thème croise l'axe et
    **l'historique de l'auteur**, jamais le calendrier ecclésial."""

    __tablename__ = "urim_preached"

    __table_args__ = (
        CheckConstraint(
            "capture_kind IN ('dictee','saisie','import')", name="preached_capture_kind"
        ),
        Index("ix_urim_preached_passage", "author_id", "book_id", "start_ch"),
        Index("ix_urim_preached_axe", "author_id", "axis_code", "preached_on"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    preparation_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("urim_preparation.id"), nullable=True
    )  # NULL si importée
    church_id: Mapped[UUID] = mapped_column(Uuid)
    author_id: Mapped[UUID] = mapped_column(Uuid)
    preached_on: Mapped[date] = mapped_column(Date)
    book_id: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    start_ch: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    start_v: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    end_ch: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    end_v: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    axis_code: Mapped[str | None] = mapped_column(String, nullable=True)
    theme: Mapped[str | None] = mapped_column(Text, nullable=True)
    capture_kind: Mapped[str | None] = mapped_column(String, nullable=True)
    exportable_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # NULL = indéfiniment


# ============================================================================ 3. LIVRABLE


class UrimDeliverableModel(Base):
    __tablename__ = "urim_deliverable"

    __table_args__ = (
        CheckConstraint("kind IN ('pptx','pdf')", name="deliverable_kind"),
        CheckConstraint(
            "validation IN ('conforme','rejete')", name="deliverable_validation"
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    preparation_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("urim_preparation.id"))
    kind: Mapped[str] = mapped_column(String)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    validation: Mapped[str | None] = mapped_column(String, nullable=True)


class UrimCitationCheckModel(Base):
    """Un verset inventé sur écran est fatal — et **détectable par programme**.

    `verdict` plutôt qu'un booléen : un booléen confond deux choses opposées. Une **troncature**
    (le pasteur coupe la fin du verset pour l'écran — légitime et universel) n'est pas une
    **altération** (un mot changé). Rejeter les deux au même titre ferait contourner la
    validation, donc mourir le garde-fou.

    Règle : le texte projeté doit être une **sous-chaîne contiguë** du corpus, après normalisation
    des apostrophes et des espaces ; « … » autorise plusieurs fragments contigus, dans l'ordre,
    sans chevauchement. Tout le reste est `altere`."""

    __tablename__ = "urim_citation_check"

    __table_args__ = (
        CheckConstraint(
            "verdict IN ('exact','extrait','altere')", name="citation_verdict"
        ),
    )

    deliverable_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("urim_deliverable.id", ondelete="CASCADE"), primary_key=True
    )
    slide_no: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    reference: Mapped[str] = mapped_column(String)
    projected_text: Mapped[str] = mapped_column(Text)
    version_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    verdict: Mapped[str] = mapped_column(String)


# ============================================================================ 4. PLAFOND


class UrimUsageWindowModel(Base):
    """Mutualisé par église, **jamais par siège**.

    L'incrément est atomique — il règle la course de deux pasteurs à `ceiling - 1` :

    ```sql
    UPDATE urim_usage_window SET metered_units = metered_units + 1
     WHERE id = :window AND metered_units < ceiling RETURNING metered_units;
    ```

    `0 ligne` → plafond atteint → `DEGRADE` (repli LSG 1910), rien n'est incrémenté, aucun mur."""

    __tablename__ = "urim_usage_window"

    __table_args__ = (
        UniqueConstraint("church_id", "period_start", name="usage_window_periode"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    church_id: Mapped[UUID] = mapped_column(Uuid)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    metered_units: Mapped[int] = mapped_column(Integer, default=0)
    ceiling: Mapped[int] = mapped_column(Integer)


class UrimStudyReservationModel(Base):
    """Rouvrir la même péricope dans la fenêtre ne consomme rien.

    **`pericope_key` est provisoire à l'ouverture, puis re-clée sur la péricope résolue** par
    l'étage 2 — un `UPDATE` de cette ligne, jamais un `INSERT`. Calculée sur l'entrée brute, elle
    cassait l'idempotence : le geste normal du pasteur — ouvrir large puis resserrer — changeait
    la clé et créait une seconde réservation. L'index partiel unique ne voyait rien, puisque les
    clés diffèrent.

    **`metered_at` : réserver n'est pas consommer.** À l'ouverture on ne sait pas encore si la
    préparation touchera une ressource facturée. Il reste NULL tant que rien de facturé n'a été
    servi, et se pose au premier service `metered` — une seule fois. Une fois posé, le droit est
    **acquis pour la durée de la réservation**, même si le plafond tombe entre-temps à cause d'un
    autre pasteur : une préparation commencée va jusqu'au bout."""

    __tablename__ = "urim_study_reservation"

    __table_args__ = (
        # L'index partiel unique rend la reprise idempotente. Coupure réseau, rechargement,
        # retentative : même clé, même unité. Sur une connexion irrégulière, un compteur naïf
        # doublerait tout.
        Index(
            "ix_urim_reservation_idempotente",
            "church_id",
            "author_id",
            "pericope_key",
            unique=True,
            postgresql_where=text("released_at IS NULL"),
            sqlite_where=text("released_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    church_id: Mapped[UUID] = mapped_column(Uuid)
    author_id: Mapped[UUID] = mapped_column(Uuid)
    pericope_key: Mapped[str] = mapped_column(String)
    window_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("urim_usage_window.id"), nullable=True
    )
    reserved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # +72h
    released_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    metered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # NULL = cette préparation n'a rien coûté


# ============================================================ 5. INSTANTANÉS D'INTERCONNEXION


class UrimEcclesialEventSnapshotModel(Base):
    """La liste blanche des huit types, **dans la base**.

    Tout type ajouté plus tard au calendrier est invisible **par défaut** — *fail closed*. C'est
    ainsi que `EVANGELISM` a manqué (S15) : le bon comportement, mais il fallait le décider.
    Codes en anglais comme les sept autres ; seul l'affichage est traduit."""

    __tablename__ = "urim_ecclesial_event_snapshot"

    __table_args__ = (
        CheckConstraint(
            "kind IN ('WEDDING','BAPTISM','SPECIAL_SERVICE','WORSHIP_NIGHT',"
            "'FAST','MEMORIAL_SERVICE','CONVENTION','EVANGELISM')",
            name="event_snapshot_liste_blanche",
        ),
        Index("ix_urim_event_snapshot", "church_id", "occurs_on"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    church_id: Mapped[UUID] = mapped_column(Uuid)
    kind: Mapped[str] = mapped_column(String)
    occurs_on: Mapped[date] = mapped_column(Date)
    label: Mapped[str | None] = mapped_column(String, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class UrimAggregateSignalSnapshotModel(Base):
    """**Aucune colonne d'identifiant de personne.** Le seuil de cinq est une contrainte `CHECK` :
    il tient même si un développeur se trompe dans l'adaptateur.

    Ces instantanés alimentent **l'affichage seul**. Aucun chemin de code ne les passe à un
    modèle — un test l'interdit par inspection du bytecode."""

    __tablename__ = "urim_aggregate_signal_snapshot"

    __table_args__ = (
        CheckConstraint("headcount >= 5", name="seuil_confidentialite"),
        Index("ix_urim_aggregate_snapshot", "church_id", "fetched_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    church_id: Mapped[UUID] = mapped_column(Uuid)
    topic: Mapped[str] = mapped_column(String)
    headcount: Mapped[int] = mapped_column(Integer)
    window_days: Mapped[int] = mapped_column(SmallInteger)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


# ============================================================ 6. PRÊCHER — la capture


class UrimCaptureModel(Base):
    """Un culte enregistré. **La capture n'est jamais refusée.**

    Plafond atteint, l'enregistrement a lieu quand même et l'audio est conservé ; c'est la
    *transcription* qui est différée. Ce qui n'est pas capté dimanche est perdu pour toujours ;
    un transcript peut attendre lundi.

    `audio_purged_at` est daté plutôt que booléen : sur une donnée qu'on détruit pour tenir une
    promesse de confidentialité, savoir **quand** elle a disparu est ce qu'on voudra prouver."""

    __tablename__ = "urim_capture"

    __table_args__ = (
        CheckConstraint(
            "state IN ('captée','transcrite','partielle','échouée')", name="capture_state"
        ),
        Index("ix_urim_capture_auteur", "author_id", "preached_on"),
        Index("ix_urim_capture_a_purger", "audio_purge_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    church_id: Mapped[UUID] = mapped_column(Uuid)
    author_id: Mapped[UUID] = mapped_column(Uuid)  # le prédicateur ; l'archive le suit
    #: « On peut prêcher sans avoir préparé » — une capture sans préparation reste utile.
    preparation_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    preached_on: Mapped[date] = mapped_column(Date)
    service_timezone: Mapped[str] = mapped_column(String)

    #: Stockés **par transcript** : sans eux, impossible de savoir plus tard pourquoi certains
    #: dimanches sont mauvais. Le fournisseur changera — la question des langues locales
    #: (dioula, baoulé, nouchi) n'est pas instruite.
    provider: Mapped[str | None] = mapped_column(String, nullable=True)
    model_ref: Mapped[str | None] = mapped_column(String, nullable=True)

    audio_purge_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    audio_purged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    state: Mapped[str] = mapped_column(String)
    transcription_deferred: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class UrimCaptureJobModel(Base):
    """La file de travaux — **aucune infrastructure nouvelle**, elle vit en table Postgres.

    Prise de travail par `FOR UPDATE SKIP LOCKED`, reprise exponentielle, abandon après cinq
    tentatives **avec `last_error` conservé** : un échec silencieux est indiscernable d'un
    dimanche où personne n'a prêché."""

    __tablename__ = "urim_capture_job"

    __table_args__ = (
        CheckConstraint(
            "kind IN ('transcrire','extraire_versets','aligner','purger_audio')",
            name="job_kind",
        ),
        CheckConstraint(
            "state IN ('en_attente','en_cours','fait','echoue','abandonne')", name="job_state"
        ),
        Index("ix_urim_job_a_prendre", "state", "not_before"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    capture_id: Mapped[UUID] = mapped_column(Uuid)  # intégrité applicative
    kind: Mapped[str] = mapped_column(String)
    state: Mapped[str] = mapped_column(String)
    attempts: Mapped[int] = mapped_column(SmallInteger, default=0)
    not_before: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String, unique=True)


class UrimTranscriptSegmentModel(Base):
    """Ce qui a été dit. `ordinal` porte l'ordre du flux — les `segment_refs` pointent dessus.

    `confidence` porte le contrôle de **couverture** : plus de 30 % des segments sous le seuil, et
    aucune synthèse n'est produite. Sans cette colonne, ce garde-fou est inécrivable — et c'est le
    seul des quatre qui protège contre un transcript **globalement** mauvais plutôt que contre une
    phrase isolée."""

    __tablename__ = "urim_transcript_segment"

    __table_args__ = (
        CheckConstraint("ended_ms >= started_ms", name="segment_borne"),
    )

    capture_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    ordinal: Mapped[int] = mapped_column(Integer, primary_key=True)
    body: Mapped[str] = mapped_column(Text)
    started_ms: Mapped[int] = mapped_column(Integer)
    ended_ms: Mapped[int] = mapped_column(Integer)
    confidence: Mapped[float] = mapped_column(Float)


class UrimCitedVerseModel(Base):
    """Les versets **réellement convoqués**.

    Deux détecteurs aux propriétés opposées : la référence énoncée est **précise**, la citation
    reconnue apporte le **rappel**. Une même citation vue par les deux est consolidée, et
    `detected_by` reste tracé — il dira laquelle des deux voies se dégrade quand les mesures
    arriveront.

    **`was_prepared` est le signal intéressant** : les textes convoqués sans avoir été prévus.
    Calculé par différence déterministe avec la préparation, **jamais par le modèle**. NULL quand
    il n'y avait pas de préparation : on ne compare pas à rien.

    ⚠️ **Ce qui n'atteint pas le seuil n'entre pas.** Filtrer *avant* d'écrire, jamais stocker
    puis filtrer : un verset faussement attribué corrompt la couverture du canon, qui est l'usage
    final. Mieux vaut manquer une citation que d'en inventer une."""

    __tablename__ = "urim_cited_verse"

    __table_args__ = (
        CheckConstraint(
            "detected_by IN ('enoncee','reconnue','fusionnee')", name="cited_verse_detected_by"
        ),
        Index("ix_urim_cited_verse_capture", "capture_id", "segment_ordinal"),
        Index("ix_urim_cited_verse_passage", "book_id", "chapter"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    capture_id: Mapped[UUID] = mapped_column(Uuid)
    book_id: Mapped[int] = mapped_column(SmallInteger)  # vers le corpus : entier nu
    chapter: Mapped[int] = mapped_column(SmallInteger)
    verse_start: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    verse_end: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    detected_by: Mapped[str] = mapped_column(String)
    confidence: Mapped[float] = mapped_column(Float)
    segment_ordinal: Mapped[int] = mapped_column(Integer)
    was_prepared: Mapped[bool | None] = mapped_column(Boolean, nullable=True)


class UrimReflectionModel(Base):
    """Le **Retour** — un par culte.

    Les quatre compteurs ne sont **jamais** calculés par le modèle : différence déterministe sur
    des données factuelles — versets cités, horodatages, ancres repérées.

    `synthesis` reste NULL tant que l'étape 4 n'a pas tourné, et elle ne tournera pas avant la
    mesure du taux d'erreur dans trois églises réelles : *une synthèse bâtie sur une transcription
    non mesurée est une invention présentée comme un souvenir.*

    **`synthese_validee_signee` n'est pas dans la spec — elle est ajoutée.** La synthèse est une
    *proposition* ; après validation elle devient la parole de son auteur, et il a pu la corriger.
    Une synthèse `validee` sans `validated_by` serait exactement le contraire : une parole
    attribuée à quelqu'un que personne n'a signée. Même raisonnement que `reviewed_by NOT NULL`
    côté corpus."""

    __tablename__ = "urim_reflection"

    __table_args__ = (
        CheckConstraint(
            "synthesis_state IN ('proposee','validee','rejetee')", name="reflection_state"
        ),
        CheckConstraint(
            "synthesis_state IS DISTINCT FROM 'validee'"
            " OR (validated_by IS NOT NULL AND validated_at IS NOT NULL)",
            name="synthese_validee_signee",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    capture_id: Mapped[UUID] = mapped_column(Uuid, unique=True)  # un Retour par culte
    author_id: Mapped[UUID] = mapped_column(Uuid)

    prepared_verses: Mapped[int] = mapped_column(Integer, default=0)
    cited_verses: Mapped[int] = mapped_column(Integer, default=0)
    unprepared: Mapped[int] = mapped_column(Integer, default=0)  # convoqués sans être prévus
    unspoken: Mapped[int] = mapped_column(Integer, default=0)  # prévus et jamais cités

    synthesis: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    synthesis_state: Mapped[str | None] = mapped_column(String, nullable=True)
    validated_by: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    validated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
