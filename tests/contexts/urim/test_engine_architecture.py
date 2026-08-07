"""Les quatre tests qui tiennent l'architecture d'Urim (spec §5).

> « Quatre tests. Ils valent plus que ce document. »

Le deuxième est le plus important du dépôt : il **interdit par programme** que les agrégats de
veille atteignent une proposition de thème. Un texte se choisit sur le texte.

`PIPELINE` est vide tant que les chantiers 1→7 n'ont pas livré les étages : les tests qui
l'itèrent sont donc vrais *par vacuité* aujourd'hui. Pour qu'ils aient de la valeur **maintenant**,
chacun s'accompagne d'une preuve sur un étage-témoin volontairement fautif : c'est le **détecteur**
qui est testé, et il attendra les vrais étages de pied ferme.
"""

from __future__ import annotations

import ast
import dis
from datetime import UTC, datetime
from pathlib import Path
from types import CodeType
from uuid import uuid4

import pytest

from app.contexts.urim.engine import (
    PIPELINE,
    EngineDeps,
    EngineInvariantError,
    EntryMode,
    Option,
    Outcome,
    StageResult,
    StudyState,
    UrimEngine,
)

_URIM_ROOT = Path(__file__).resolve().parents[3] / "app" / "contexts" / "urim"


# --------------------------------------------------------------------------- outils


def attribute_names_read(func) -> set[str]:
    """Tous les attributs lus par une fonction, **y compris** dans ses code objects
    imbriqués (lambdas, comprehensions). C'est la sonde du test n°2."""
    names: set[str] = set()

    def walk(code: CodeType) -> None:
        for instruction in dis.get_instructions(code):
            if instruction.opname in ("LOAD_ATTR", "LOAD_METHOD") and isinstance(
                instruction.argval, str
            ):
                names.add(instruction.argval)
        for const in code.co_consts:
            if isinstance(const, CodeType):
                walk(const)

    walk(func.__code__)
    return names


def _now() -> datetime:
    return datetime(2026, 8, 3, tzinfo=UTC)


def _deps() -> EngineDeps:
    marker = object()  # aucun étage ne doit toucher `context`
    return EngineDeps(
        corpus=marker, doctrine=marker, homiletics=marker,
        context=marker, versions=marker, clock=_now,
    )


def _state(**kw) -> StudyState:
    base = dict(
        session_id=uuid4(), church_id=uuid4(), author_id=uuid4(),
        corpus_snapshot="lsg1910+darby@2026-08-01",
        entry_mode=EntryMode.REFERENCE, raw_input="Romains 8:10-15",
    )
    return StudyState(**(base | kw))


class _CleanStage:
    """Étage conforme : il ne lit que ce qu'il a le droit de lire, et il motive."""

    code = "temoin_propre"

    def applies(self, state: StudyState) -> bool:
        return True

    def execute(self, state: StudyState, deps: EngineDeps) -> StageResult:
        snapshot = state.corpus_snapshot
        return StageResult(
            outcome=Outcome.CONTINUE,
            rationale=f"corpus {snapshot} — passage identifié sans ambiguïté",
            state=state,
        )


class _ContextReadingStage:
    """Étage **fautif** : il lit le contexte ecclésial. Le test n°2 doit l'attraper."""

    code = "temoin_fautif"

    def applies(self, state: StudyState) -> bool:
        return True

    def execute(self, state: StudyState, deps: EngineDeps) -> StageResult:
        _ = deps.context  # ⛔ interdit — c'est exactement ce qu'on veut détecter
        return StageResult(outcome=Outcome.CONTINUE, rationale="…", state=state)


# ------------------------------------------------------------------ 1. la frontière


#: Les points de passage autorisés vers le reste du système (Structure §1).
#:
#: `calendar/adapters/` était le seul tant qu'Urim n'avait pas de surface HTTP. Deux se
#: sont ajoutés le jour où il a fallu l'exposer, et il vaut la peine de dire pourquoi ils
#: ne sont pas un affaiblissement :
#:
#: * `adapters/` — les franchissements **nommés**. Un fichier là-dedans est un endroit où
#:   Urim touche le reste, et le fait exprès. Ils se comptent et se lisent.
#: * `interface/` — le routeur et l'injection de dépendances **sont** le point de
#:   composition : c'est leur métier de connaître l'authentification et de câbler des
#:   adaptateurs. Leur interdire les autres contextes reviendrait à interdire à Urim
#:   d'avoir des routes.
#:
#: Ce que l'élargissement ne touche pas : le **cœur** — `engine/`, `application/`,
#: `domain/`, `infrastructure/` — n'importe toujours rien. C'est là que la règle compte,
#: parce que c'est là que vit le raisonnement. Et les deux murs substantiels (la finance
#: n'entre jamais, rien n'écrit vers la veille) sont tenus par des tests **sans aucune
#: exemption**, y compris sur ces trois répertoires.
_EXEMPTIONS = (
    ("calendar", "adapters"),
    ("adapters",),
    ("interface",),
)

#: S27 — ce que **même la zone d'exemption** ne peut pas importer. Deux murs étaient bâtis
#: sur trois côtés : Finance §2.1 interdit `finance → watch`, Urim §4.3 interdit
#: `watch → moteur`, et **personne n'avait écrit `finance → urim`**. La tentation y est
#: identique — « le projet toiture est à 40 %, proposons un sermon sur la générosité » — et
#: c'est le côté le plus dangereux, parce que le lien paraît innocent et que l'argent est le
#: seul domaine où le bénéfice de la transgression est immédiatement mesurable.
#: **Un pasteur qui prépare son sermon n'a pas à voir le solde du fonds.**
_JAMAIS_MEME_DEPUIS_LES_ADAPTATEURS = ("app.contexts.finance",)

#: S28 — ce que la zone d'exemption peut importer de `watch`, et **rien d'autre** :
#: le read-model **non nominatif**. L'exemption ouvrait tout `watch` — y compris
#: `SignalStore`, `Intake`, les stores de contact. Rien n'empêchait une préparation
#: d'**écrire** un cas, alors que `Structure §2` l'interdit : « urim → watch : aucun
#: retour. Une préparation ne crée ni fait, ni cas, ni signal. » Une **liste blanche**
#: tient mieux qu'une liste noire : ce qui n'est pas nommé ici est refusé par défaut.
_WATCH_AUTORISE_DEPUIS_LES_ADAPTATEURS = ("app.contexts.watch.application.aggregates",)


def test_une_preparation_ne_peut_rien_ecrire_dans_la_veille():
    """S28 — `urim → watch` : aucun retour (Structure §2).

    L'exemption de `calendar/adapters/` autorisait **tout** `watch`. Le lire est permis
    (agrégats non nominatifs) ; y **écrire** ne l'est pas. Une préparation ne crée ni
    fait, ni cas, ni signal — et ce n'était garanti que par la bonne volonté."""
    offenders = [
        f"{path.name} → {module}"
        for path in _URIM_ROOT.rglob("*.py")
        for module in _modules_importes(path)
        if module.startswith("app.contexts.watch")
        and not module.startswith(_WATCH_AUTORISE_DEPUIS_LES_ADAPTATEURS)
    ]
    assert offenders == [], (
        f"Urim touche la veille au-delà du read-model : {offenders}. "
        "Seuls les agrégats non nominatifs sont lisibles ; rien n'est écrit."
    )


def _modules_importes(path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
        elif isinstance(node, ast.Import):
            modules.extend(a.name for a in node.names)
    return modules


def test_la_finance_n_entre_jamais_dans_urim_meme_par_un_adaptateur():
    """S27 — le troisième mur, celui que personne n'avait écrit.

    L'exemption de `calendar/adapters/` autorise un franchissement : rien n'empêchait
    d'y déposer un `finance_adapter.py`. Ce test ferme la porte — la règle est **plus
    stricte que pour la veille** : les agrégats de veille peuvent au moins *s'afficher*
    à côté du texte ; l'état financier ne doit **même pas entrer** dans l'atelier."""
    offenders = [
        f"{path.name} → {module}"
        for path in _URIM_ROOT.rglob("*.py")
        for module in _modules_importes(path)
        if module.startswith(_JAMAIS_MEME_DEPUIS_LES_ADAPTATEURS)
    ]
    assert offenders == [], (
        f"la finance entre dans Urim : {offenders}. Le sermon deviendrait un instrument "
        "de collecte piloté par un tableau de bord."
    )


def test_urim_n_importe_rien_hors_de_lui_meme():
    """Un seul point de contact avec le reste du système (Structure §1).

    « Ce test est le verrou réel. Le reste du document est une intention ; lui seul
    survit à six mois de développement par quelqu'un qui n'aura pas lu ces pages. »"""
    offenders: list[str] = []
    for path in _URIM_ROOT.rglob("*.py"):
        parts = path.relative_to(_URIM_ROOT).parts
        if any(parts[: len(e)] == e for e in _EXEMPTIONS):  # adapters/ et interface/
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            module = (
                node.module
                if isinstance(node, ast.ImportFrom) and node.module
                else next((a.name for a in node.names), "")
                if isinstance(node, ast.Import)
                else ""
            )
            if module.startswith("app.contexts.") and not module.startswith(
                "app.contexts.urim"
            ):
                offenders.append(f"{path.name} → {module}")
    assert offenders == [], f"frontière franchie hors adapters/ : {offenders}"


# ---------------------------------------------- 2. AFFICHAGE SEUL (le plus important)


def test_aucun_etage_ne_lit_le_contexte_ecclesial():
    """AFFICHAGE SEUL : recherche oui, génération non.

    Aucun `Stage` n'accède à `deps.context` — vérifié par inspection du bytecode."""
    for stage in PIPELINE:
        lus = attribute_names_read(type(stage).execute)
        for interdit in EngineDeps.FORBIDDEN_FOR_STAGES:
            assert interdit not in lus, (
                f"l'étage {stage.code} lit deps.{interdit} — "
                "la veille ne doit jamais atteindre une proposition de thème"
            )


def test_la_sonde_attrape_bien_un_etage_fautif():
    """Le détecteur ci-dessus n'est pas décoratif : la preuve, sur un étage-témoin."""
    assert "context" in attribute_names_read(_ContextReadingStage.execute)
    assert "context" not in attribute_names_read(_CleanStage.execute)


def test_le_moteur_n_impose_pas_le_contexte_aux_etages():
    """Un étage propre s'exécute sans jamais toucher `deps.context`."""
    run = UrimEngine(_deps(), pipeline=(_CleanStage(),)).run(_state())
    assert run.results[0].outcome is Outcome.CONTINUE


def test_le_seuil_de_confidentialite_tient_dans_le_domaine():
    """Aucun agrégat sous cinq personnes ne traverse la frontière (Structure §3.8)."""
    from app.contexts.urim.calendar.domain.models import AggregateSignal

    with pytest.raises(ValueError, match="seuil de confidentialité"):
        AggregateSignal(topic="deuil", headcount=4, window_days=30)
    assert AggregateSignal(topic="deuil", headcount=5, window_days=30).headcount == 5


def test_l_adaptateur_nul_est_le_defaut_et_ne_fuit_rien():
    """Urim fonctionne entièrement sans le reste du système (Architecture §4.6)."""
    from datetime import date

    from app.contexts.urim.calendar.domain.ports import NullEcclesialContext

    null = NullEcclesialContext()
    church = uuid4()
    assert null.events_between(church, date(2026, 8, 1), date(2026, 8, 31)) == ()
    assert null.aggregate_signals(church) == ()


def test_la_liste_blanche_des_evenements_est_close():
    """Huit types, pas un de plus — tout type ajouté ailleurs est invisible par défaut.

    Ce test **doit** casser quand quelqu'un élargit la liste : c'est une décision produit,
    pas un ajout de routine (S15)."""
    from app.contexts.urim.calendar.domain.models import EcclesialEventKind

    assert {k.value for k in EcclesialEventKind} == {
        "WEDDING", "BAPTISM", "SPECIAL_SERVICE", "WORSHIP_NIGHT",
        "FAST", "MEMORIAL_SERVICE", "CONVENTION", "EVANGELISM",
    }


def test_un_refus_voyage_dans_l_etat_sans_refuser_le_texte():
    """S18 — « mais je ne veux pas d'une créature en Christ ».

    Une contrainte **négative** ne refuse pas le texte : elle voyage dans l'état pour que
    le bornage (étage 2) ordonne ses options. Le pasteur garde son passage ; ce sont les
    **bornes** qui bougent."""
    state = _state(refused_axes=("nouvelle_creation",))
    assert state.refused_axes == ("nouvelle_creation",)
    # L'absence de contrainte est le cas normal, et elle est vide — pas None.
    assert _state().refused_axes == ()
    # L'état reste immuable : poser un refus produit un nouvel état.
    enrichi = _state().with_(refused_axes=("nouvelle_creation",))
    assert enrichi.refused_axes and _state().refused_axes == ()


def test_une_reference_se_precise_par_degres():
    """S7 et S23 — le pasteur entre à n'importe quel degré de précision.

    « Galates 5 » (chapitre, sans verset) et « 1 Rois » (livre seul, quand il cherche
    l'histoire de Jézabel) sont des entrées réelles. Le type les refusait toutes deux."""
    from app.contexts.urim.engine import Reference

    livre = Reference(book="1 Rois")  # S23 — « il s'agit de Jézabel »
    assert livre.is_whole_book
    assert not livre.is_whole_chapter  # un livre n'est pas « un chapitre entier »

    chapitre = Reference(book="Gal", chapter=5)  # S7
    assert chapitre.is_whole_chapter
    assert not chapitre.is_whole_book

    verset = Reference(book="Col", chapter=1, verse_start=27)
    assert not verset.is_whole_chapter and not verset.is_whole_book

    peri = Reference(book="Col", chapter=1, verse_start=24, verse_end=29)
    assert peri.verse_end == 29


# ------------------------------------------------------------------ 3. déterminisme


def test_determinisme():
    """Même entrée + même `corpus_snapshot` ⇒ même sortie, 100 fois."""
    engine = UrimEngine(_deps(), pipeline=(_CleanStage(), _CleanStage()))
    state = _state()
    reference = engine.run(state)
    for _ in range(100):
        run = engine.run(state)
        assert run.state == reference.state
        assert run.results == reference.results


def test_l_etat_est_immuable_le_moteur_n_altere_pas_son_entree():
    state = _state()
    UrimEngine(_deps(), pipeline=(_CleanStage(),)).run(state)
    assert state.trace == ()  # l'entrée n'a pas bougé


# ------------------------------------------------------------------ 4. le motif


def test_tout_resultat_porte_un_motif():
    """Sur un corpus de cas, aucun `StageResult` sans `rationale`."""
    engine = UrimEngine(_deps(), pipeline=(_CleanStage(), _CleanStage()))
    run = engine.run(_state())
    assert run.results, "le pipeline-témoin doit produire des résultats"
    for result in run.results:
        assert result.rationale.strip()
    for entry in run.state.trace:
        assert entry.rationale.strip()


@pytest.mark.parametrize("vide", ["", "   ", "\n\t"])
def test_un_resultat_sans_motif_est_refuse(vide: str):
    with pytest.raises(EngineInvariantError):
        StageResult(outcome=Outcome.CONTINUE, rationale=vide, state=_state())


def test_await_sans_options_est_refuse():
    """`AWAIT` est une issue normale — mais on ne rend pas la main les mains vides."""
    with pytest.raises(EngineInvariantError):
        StageResult(outcome=Outcome.AWAIT, rationale="ambiguïté", state=_state())


# -------------------------------------------------- la main revient au pasteur


def test_le_moteur_s_arrete_quand_il_rend_la_main():
    """`AWAIT` et `REFUSE` arrêtent le pipeline ; `DEGRADE` ne coupe jamais."""

    class _Await:
        code = "await"

        def applies(self, state):
            return True

        def execute(self, state, deps):
            return StageResult(
                outcome=Outcome.AWAIT,
                rationale="deux péricopes possibles",
                state=state,
                options=(Option("a", "Rom 8.9-17", "unité littéraire"),),
            )

    class _Jamais:
        code = "jamais"

        def applies(self, state):
            raise AssertionError("le pipeline aurait dû s'arrêter avant")

        def execute(self, state, deps):  # pragma: no cover
            raise AssertionError

    run = UrimEngine(_deps(), pipeline=(_Await(), _Jamais())).run(_state())
    assert run.halted
    assert len(run.results) == 1


def test_degrade_ne_coupe_jamais_le_pipeline():
    """Aucun mur un vendredi soir."""

    class _Degrade:
        code = "degrade"

        def applies(self, state):
            return True

        def execute(self, state, deps):
            return StageResult(
                outcome=Outcome.DEGRADE,
                rationale="version sous licence indisponible — texte servi en LSG 1910",
                state=state,
            )

    run = UrimEngine(_deps(), pipeline=(_Degrade(), _CleanStage())).run(_state())
    assert not run.halted
    assert len(run.results) == 2  # la préparation continue
