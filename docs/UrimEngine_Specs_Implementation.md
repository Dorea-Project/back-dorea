# UrimEngine — Spécification de mise en place et d'exécution

**2 août 2026** — complète `Dorea_Urim_Architecture_v2.md` et `Dorea_Urim_Structure_et_Schema.md`
**Statut :** spécification prête. Exécution subordonnée au séquencement (§9).

---

## 1. Ce qu'est `UrimEngine`

Un **pipeline déterministe à étages**, sur le modèle du moteur de veille : un état, des étages purs, des effets isolés en bordure.

Trois propriétés non négociables :

**Déterminisme.** Mêmes entrées + même version de corpus ⇒ même sortie, bit pour bit. Le corpus étant immuable, c'est testable — et testé.

**Motif obligatoire.** Aucun étage ne produit un résultat sans énoncer pourquoi. Le type de retour l'impose : `rationale` n'est pas facultatif. C'est la traduction, dans le code, de `reviewed_by NOT NULL` dans la base.

**La décision humaine est un état, pas une erreur.** Une résolution ambiguë, un couple homilétique impossible, un bornage contesté : ce sont des issues normales du moteur, pas des exceptions. Le moteur s'arrête et rend la main.

---

## 2. Le contrat

```python
# contexts/urim/engine/outcomes.py

class Outcome(StrEnum):
    CONTINUE   = "continue"        # l'étage suivant s'exécute
    AWAIT      = "await_decision"  # le pasteur doit trancher
    REFUSE     = "refuse"          # motivé, définitif pour ce couple
    DEGRADE    = "degrade"         # repli, la préparation continue


@dataclass(frozen=True, slots=True)
class StageResult:
    outcome:    Outcome
    rationale:  str                       # JAMAIS vide — invariant vérifié
    state:      "StudyState"
    options:    tuple[Option, ...] = ()   # non vide si AWAIT

    def __post_init__(self) -> None:
        if not self.rationale.strip():
            raise EngineInvariantError("un étage ne rend rien sans motif")
        if self.outcome is Outcome.AWAIT and not self.options:
            raise EngineInvariantError("AWAIT sans options à proposer")
```

```python
# contexts/urim/engine/state.py

@dataclass(frozen=True, slots=True)
class StudyState:
    session_id:      UUID
    church_id:       UUID
    author_id:       UUID
    corpus_snapshot: str              # version du corpus — clé du déterminisme

    entry_mode:      EntryMode        # REFERENCE | CITATION | CONVICTION
    raw_input:       str

    resolved:        Reference | None = None
    bounds:          Bounds    | None = None
    bounds_overridden: bool           = False
    version_id:      UUID     | None  = None
    axis:            str      | None  = None
    plan_source:     str      | None  = None
    subject_matter:  str      | None  = None

    trace:           tuple[TraceEntry, ...] = ()   # motif de chaque étage

    def with_(self, **kw) -> "StudyState":
        return replace(self, **kw)
```

L'état est **immuable**. Chaque étage retourne un nouvel état. La `trace` accumule les motifs : c'est elle qui s'affiche à l'écran, et elle est rejouable.

```python
# contexts/urim/engine/stage.py

class Stage(Protocol):
    code: str

    def applies(self, state: StudyState) -> bool: ...
    def execute(self, state: StudyState, deps: "EngineDeps") -> StageResult: ...
```

### Les étages, dans l'ordre

```python
PIPELINE: Final[tuple[Stage, ...]] = (
    RouteEntry(),        # 0 — référence / citation / conviction
    ResolvePassage(),    # 1 — identifier le passage, pas la version
    BoundPericope(),     # 2 — unité littéraire + motif
    ServeCorpus(),       # 3 — versions, original, concordance
    LoadContext(),       # 4 — sourcé ou absent
    BearAxes(),          # 5 — porté / non porté / mise en garde
    ShapeHomiletic(),    # 6 — couple (source de plan × matière)
    ProposeTheme(),      # 7 — motif affiché
)
```

L'ordre est contraignant, et le moteur le vérifie : un étage dont les prérequis manquent lève `StagePrerequisiteError` plutôt que de travailler sur un état incomplet.

### La boucle

```python
class UrimEngine:
    def __init__(self, deps: EngineDeps, pipeline=PIPELINE) -> None:
        self._deps, self._pipeline = deps, pipeline

    def run(self, state: StudyState) -> EngineRun:
        results: list[StageResult] = []
        for stage in self._pipeline:
            if not stage.applies(state):
                continue
            result = stage.execute(state, self._deps)
            results.append(result)
            state = result.state.with_(
                trace=state.trace + (TraceEntry(stage.code, result.rationale),)
            )
            if result.outcome in (Outcome.AWAIT, Outcome.REFUSE):
                break                      # la main revient au pasteur
        return EngineRun(state=state, results=tuple(results))

    def resume(self, state: StudyState, decision: Decision) -> EngineRun:
        """Reprise après AWAIT. La décision entre dans l'état, le pipeline repart."""
        return self.run(decision.apply_to(state))
```

**`run` est pure.** Aucune écriture en base, aucun appel réseau, aucune horloge. Toute la bordure passe par `deps`.

---

## 3. Les dépendances — la bordure

```python
@dataclass(frozen=True, slots=True)
class EngineDeps:
    corpus:     CorpusReader          # lecture seule, immuable
    doctrine:   DoctrineReader        # caveats curés, portées
    homiletics: HomileticsReader      # faisabilité des couples
    context:    EcclesialContextPort  # ⚠ AFFICHAGE SEUL — §5
    versions:   VersionResolver       # arbitre domaine public / sous licence
    clock:      Clock                 # injectée : le déterminisme l'exige
```

**`EcclesialContextPort` n'est jamais lu par un étage.** Il est déclaré ici pour être passé à la couche de présentation, jamais consommé par le pipeline. Un test le vérifie (§5).

---

## 4. Exécution — le tour d'application

```
POST /urim/studies                 → ouvre : réserve (§6), instancie l'état, run()
GET  /urim/studies/{id}            → état + trace + options en attente
POST /urim/studies/{id}/decisions  → resume() avec la décision du pasteur
POST /urim/studies/{id}/elements   → squelette Braga, champs libres
POST /urim/studies/{id}/deliverable→ diapositives + validation de sortie
POST /urim/preached                → archive (dictée, saisie, import)
```

Tout est **synchrone**. Aucun worker, aucune file — cohérent avec « ni Redis ni RabbitMQ en V1 ». La résolution la plus lourde est une requête indexée sur une table immuable.

### Dégradation, jamais blocage

```python
def serve_version(self, want: UUID, deps: EngineDeps) -> tuple[UUID, str | None]:
    v = deps.versions.get(want)
    if not v.metered:
        return v.id, None
    if deps.versions.ceiling_reached():
        fallback = deps.versions.public_domain_default()
        return fallback.id, (
            f"{v.label} indisponible pour le moment — "
            f"texte servi en {fallback.label}. La préparation continue."
        )
    return v.id, None
```

`DEGRADE` ne coupe jamais le pipeline. **Aucun mur un vendredi soir.**

---

## 5. Les tests qui tiennent l'architecture

Quatre tests. Ils valent plus que ce document.

```python
def test_urim_n_importe_rien_hors_de_lui_meme():
    """Seul calendar/adapters/ franchit la frontière."""

def test_aucun_etage_ne_lit_le_contexte_ecclesial():
    """AFFICHAGE SEUL : recherche oui, génération non.
    Aucun Stage n'accède à deps.context — vérifié par inspection du bytecode."""
    for stage in PIPELINE:
        assert "context" not in noms_lus(stage.execute)

def test_determinisme():
    """Même entrée + même corpus_snapshot ⇒ même sortie, 100 fois."""

def test_tout_resultat_porte_un_motif():
    """Sur un corpus de cas, aucun StageResult sans rationale."""
```

Le deuxième est le plus important du dépôt. Il interdit par programme que les agrégats de veille atteignent une proposition de thème.

---

## 6. Réservation et plafond

Hors moteur, en bordure d'ouverture.

```python
def open_study(cmd: OpenStudy, uow: UnitOfWork) -> StudyState:
    key = pericope_key(cmd)                    # idempotence
    with uow:
        r = uow.reservations.active(cmd.church_id, cmd.author_id, key)
        if r is None:                          # rouvrir ne consomme rien
            r = uow.reservations.reserve(..., expires_at=now + timedelta(hours=72))
        uow.commit()
    return StudyState(...)
```

Vérification **à l'ouverture uniquement**. Une préparation commencée va jusqu'au bout. L'index partiel unique rend la reprise idempotente sur réseau instable.

---

## 7. Ordre des migrations

```
001  schema urim_corpus + extensions (pg_trgm, unaccent)
002  language, book, book_name, version
003  verse (+ index trgm, fts, ref) · versification_map · textual_variant   ← ajoutée 2026-08-03
004  lemma, token, idf
005  pericope, doctrinal_axis, doctrinal_bearing, doctrinal_caveat
006  plan_source, subject_matter, homiletic_feasibility
007  schema urim : preparation, preparation_element, resolution_attempt
008  preached
009  deliverable, citation_check
010  usage_window, study_reservation
011  ecclesial_event_snapshot, aggregate_signal_snapshot (CHECK ≥ 5)
```

Chaque migration touche **un seul schéma**. Aucune clé étrangère ne franchit une frontière de contexte, ni `urim` → `urim_corpus` (§3.9 du schéma).

---

## 8. Chantiers

| # | Chantier | Fini quand |
|---|---|---|
| 0 | Socle : schémas, ports, les 4 tests | Les tests échouent pour la bonne raison |
| 1 | Corpus : LSG 1910, Darby, SBLGNT, Strong, index | Un verset se lit en < 10 ms, index mesurés |
| 2 | **Livrable** : import, diapositives, validation de sortie | Un verset altéré d'un caractère est rejeté |
| 3 | Résolution | Une citation écorchée sort les bons candidats avec motifs |
| 4 | Bornage | Rom 8:10-15 propose 8.9-17 avec les deux motifs |
| 5 | Doctrine : 40 péricopes semées | Un texte non couvert n'affiche rien |
| 6 | `UrimEngine` assemblé | Le test de déterminisme passe 100 fois |
| 7 | Homilétique | Rom 8 × biographique produit un refus motivé |
| 8 | Archive + dictée | Canon et distribution s'affichent |
| 9 | Plafond | Dégradation testée, aucun blocage possible |

### Pourquoi le livrable en 2

**Le chantier 2 ne dépend que du corpus, pas du moteur.** C'est la fonction utilisée chaque semaine, sans risque doctrinal, et elle est livrable seule. Si le reste s'arrête, elle a déjà de la valeur — et elle valide le corpus en conditions réelles avant que quoi que ce soit d'autre s'appuie dessus.

---

## 9. Séquencement — inchangé

**Rien de ce document ne commence avant :**

1. Écran de captation des présences, testé en conditions réelles
2. Émetteur `CasePriority.ABSENCE` activé
3. Corrections du `Moteur_Corrections_et_Regime_Hybride.md` appliquées
4. **Un dimanche réel, dans une église réelle**

R1 — dispersion — reste le risque dominant. Cette spécification existe pour être prête, pas pour être commencée.

---

## 10. À vérifier avant le chantier 0

Où vit aujourd'hui le calendrier des programmes et rencontres ? S'il est déjà hors de `watch`, l'adaptateur d'événements disparaît et seul l'adaptateur d'agrégats subsiste. **Dix minutes dans `back-dorea`.**
