"""**Étages 4, 6 et 7** — le contexte, la faisabilité, le thème. Le pipeline ferme ici.

Trois promesses, une par étage :

- **4** — *sourcé, ou absent*. Il n'y a pas de troisième possibilité : un contexte historique
  inventé est le genre d'erreur qu'un pasteur répète en chaire avec assurance, parce qu'elle
  avait l'air documentée ;
- **6** — *un refus motivé, jamais un plan fabriqué*. `Romains 8:9-17` ne porte aucun personnage,
  donc `x biographique` refuse au lieu d'inventer un personnage pour satisfaire une case ;
- **7** — *le calendrier ecclésial ne rentre pas*. « Un baptême dimanche, c'est légitime »
  vaudrait demain pour « douze malades ce mois-ci ».
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.contexts.urim.calendar.domain.ports import NullEcclesialContext
from app.contexts.urim.engine import (
    Bounds,
    ContextNote,
    EngineDeps,
    EntryMode,
    Feasibility,
    LoadContext,
    Outcome,
    PericopeView,
    ProposeTheme,
    Reference,
    ShapeHomiletic,
    StudyState,
)
from app.contexts.urim.engine.errors import StagePrerequisiteError
from app.contexts.urim.engine.stages.shape_homiletic import RISQUES

ROM_8 = Reference(book="Romains", chapter=8, verse_start=9, verse_end=17)
BORNES = Bounds(start=ROM_8, end=ROM_8)
PERICOPE = uuid4()

#: Une unité curée qui **couvrait** le passage — de quoi distinguer un choix du pasteur d'un
#: trou du corpus, au seul étage qui doit encore les nommer autrement (`propose_theme`).
_UNITE = PericopeView(
    id=PERICOPE,
    bounds=BORNES,
    label="Vivre par l'Esprit",
    rationale="L'unité tient du v.9 au v.17.",
)

EXPOSITIF = Feasibility(
    plan_source="expositif", subject_matter="doctrinal", feasible=True,
    refusal_reason="", proof_text_risk="faible",
)
BIOGRAPHIQUE = Feasibility(
    plan_source="textuel", subject_matter="biographique", feasible=False,
    refusal_reason="ce passage ne porte aucun personnage", proof_text_risk="faible",
)
THEMATIQUE = Feasibility(
    plan_source="thematique", subject_matter="ethique", feasible=True,
    refusal_reason="", proof_text_risk="eleve",
)


class _Corpus:
    def __init__(self, notes=(), unites=()):
        self._notes = tuple(notes)
        #: Ce que le corpus **avait à proposer** sur le passage. Vide par défaut, comme les
        #: 99,77 % de l'Écriture qui ne sont pas encore curés.
        self._unites = tuple(unites)

    def snapshot(self) -> str:
        return "corpus-2026-08"

    def context_for(self, pericope_id):
        return self._notes

    def pericopes_for(self, reference):
        return self._unites


class _Homiletique:
    def __init__(self, couples=(), deja=()):
        self._couples, self._deja = tuple(couples), tuple(deja)

    def couples_for(self, pericope_id):
        return self._couples

    def recently_preached_axes(self, author_id):
        return self._deja


class _Rien:
    def ceiling_reached(self) -> bool:
        return False


def _deps(*, corpus=None, homiletics=None):
    return EngineDeps(
        corpus=corpus or _Corpus(), doctrine=_Rien(),
        homiletics=homiletics or _Homiletique(),
        context=NullEcclesialContext(), versions=_Rien(),
        clock=lambda: datetime(2026, 8, 6, tzinfo=UTC),
    )


def _state(**kw):
    base = {
        "session_id": uuid4(), "church_id": uuid4(), "author_id": uuid4(),
        "corpus_snapshot": "corpus-2026-08", "entry_mode": EntryMode.REFERENCE,
        "raw_input": "Romains 8:9-17", "resolved": ROM_8, "bounds": BORNES,
        "pericope_id": PERICOPE, "axis": "soteriologie",
    }
    return StudyState(**{**base, **kw})


# =================================================================================================
# Étage 4 — sourcé, ou absent
# =================================================================================================


def test_le_contexte_relu_s_affiche_avec_sa_nature_et_sa_source():
    """S40 — la nature est dite **avant** la note : l'historique situe, le littéraire explique la
    construction, et le pasteur ne les lit pas au même moment."""
    corpus = _Corpus(
        [
            ContextNote(
                kind="historique",
                body="lettre écrite avant le voyage",
                source_ref="Bruce, p.12",
            )
        ]
    )

    resultat = LoadContext().execute(_state(), _deps(corpus=corpus))

    assert resultat.outcome is Outcome.CONTINUE
    assert "historique — lettre écrite avant le voyage" in resultat.rationale
    assert "Bruce, p.12" in resultat.rationale


def test_sans_note_relue_l_etage_n_invente_rien():
    """**Rien plutôt qu'une vraisemblance.** Le vide est un état normal."""
    resultat = LoadContext().execute(_state(), _deps())

    assert resultat.outcome is Outcome.CONTINUE
    assert "Aucun contexte relu" in resultat.rationale


def test_le_contexte_n_interrompt_jamais():
    """Il informe, il n'arbitre rien — aucun `AWAIT`, aucun `REFUSE`."""
    assert not LoadContext().execute(_state(), _deps()).halts
    assert not LoadContext().execute(_state(pericope_id=None), _deps()).halts


# =================================================================================================
# Étage 6 — un refus motivé, jamais un plan fabriqué
# =================================================================================================


def test_les_couples_impossibles_sont_signales_avec_les_possibles():
    """*Une combinaison impossible est signalée, jamais fabriquée.*

    Les cacher laisserait le pasteur croire qu'on n'y a pas pensé."""
    homiletique = _Homiletique([EXPOSITIF, BIOGRAPHIQUE])

    resultat = ShapeHomiletic().execute(_state(), _deps(homiletics=homiletique))

    assert resultat.outcome is Outcome.AWAIT
    assert [o.code for o in resultat.options] == ["expositif:doctrinal"]
    assert "aucun personnage" in resultat.rationale


def test_un_couple_refuse_produit_un_refus_qui_dit_pourquoi():
    """`refus_motive` en base interdit `feasible = false` sans motif — l'étage s'appuie dessus."""
    homiletique = _Homiletique([EXPOSITIF, BIOGRAPHIQUE])
    state = _state(plan_source="textuel", subject_matter=None)

    resultat = ShapeHomiletic().execute(state, _deps(homiletics=homiletique))

    assert resultat.outcome is Outcome.REFUSE
    assert resultat.rationale == "ce passage ne porte aucun personnage"


def test_aucun_couple_faisable_refuse_au_lieu_de_proposer_le_vide():
    homiletique = _Homiletique([BIOGRAPHIQUE])

    resultat = ShapeHomiletic().execute(_state(), _deps(homiletics=homiletique))

    assert resultat.outcome is Outcome.REFUSE
    assert "aucun personnage" in resultat.rationale


def test_le_risque_est_porte_par_le_couple_pas_par_le_texte():
    """La faisabilité est celle d'un **triplet** : le thématique est structurellement plus risqué,
    parce que les textes y sont convoqués pour confirmer."""
    homiletique = _Homiletique([THEMATIQUE])
    state = _state(plan_source="thematique", subject_matter="ethique")

    resultat = ShapeHomiletic().execute(state, _deps(homiletics=homiletique))

    assert resultat.outcome is Outcome.CONTINUE
    assert "eleve" in resultat.rationale


def test_une_intention_declaree_releve_le_risque_d_un_cran():
    """**S26 et S37, au même endroit.** « Je veux motiver » n'ajoute aucun axe — ça change le
    risque. Et le motif nomme **l'effet**, jamais l'état de celui qui écrit."""
    homiletique = _Homiletique([EXPOSITIF])
    state = _state(
        plan_source="expositif", subject_matter="doctrinal", risk_flags=("intention_declaree",)
    )

    resultat = ShapeHomiletic().execute(state, _deps(homiletics=homiletique))

    assert "moyen" in resultat.rationale  # relevé depuis « faible »
    assert "textes qui résistent" in resultat.rationale
    for diagnostic in ("plainte", "détresse", "colère", "vous êtes"):
        assert diagnostic not in resultat.rationale.lower()


def test_le_risque_ne_depasse_jamais_le_dernier_cran():
    """L'échelle est fermée : trois valeurs, pas un score qui grimpe."""
    homiletique = _Homiletique([THEMATIQUE])
    state = _state(
        plan_source="thematique", subject_matter="ethique", risk_flags=("a", "b", "c")
    )

    resultat = ShapeHomiletic().execute(state, _deps(homiletics=homiletique))

    assert RISQUES[-1] in resultat.rationale


def test_hors_unite_curee_on_degrade_jamais_on_ne_refuse():
    """**S22** — on ne punit pas une liberté qu'on a accordée."""
    resultat = ShapeHomiletic().execute(_state(pericope_id=None), _deps())

    assert resultat.outcome is Outcome.DEGRADE
    assert not resultat.halts


def test_la_forme_se_decide_apres_le_fond():
    etage = ShapeHomiletic()

    assert not etage.applies(_state(axis=None))
    assert etage.applies(_state())

    with pytest.raises(StagePrerequisiteError):
        etage.execute(_state(axis=None), _deps())


# =================================================================================================
# Étage 7 — le thème, et ce qu'il refuse de regarder
# =================================================================================================


def test_le_theme_se_derive_de_l_axe_retenu():
    state = _state(plan_source="expositif", subject_matter="doctrinal")

    resultat = ProposeTheme().execute(state, _deps())

    assert resultat.outcome is Outcome.CONTINUE
    assert resultat.state.theme == "soteriologie, en expositif doctrinal"


def test_l_archive_informe_et_n_interdit_rien():
    """Prêcher deux fois le même axe est un choix légitime, et le pasteur est le seul à savoir
    pourquoi. L'historique le dit ; il ne bloque pas."""
    homiletique = _Homiletique(deja=("soteriologie",))

    resultat = ProposeTheme().execute(_state(), _deps(homiletics=homiletique))

    assert resultat.outcome is Outcome.CONTINUE
    assert "déjà prêché" in resultat.rationale


def test_un_trou_du_corpus_ne_se_dit_pas_comme_un_forcage_du_pasteur():
    """⚠️ **Le motif dit ce qui manque au moteur, jamais ce qui manque au pasteur.**

    `bounds_overridden` est vrai pour deux raisons opposées, et l'étage disait « Bornes forcées »
    dans les deux. À 0,23 % de couverture curée, c'était l'ordinaire : presque chaque préparation
    s'entendait reprocher un forçage qui n'avait pas eu lieu — `jn 2:3` le premier."""
    resultat = ProposeTheme().execute(_state(bounds_overridden=True), _deps())

    assert "Hors unité curée" in resultat.rationale
    assert "forcées" not in resultat.rationale


def test_des_bornes_que_le_pasteur_a_conservees_sont_dites_comme_les_siennes():
    """L'autre moitié : une unité **existait**, et il a préféré les siennes. On le lui rappelle —
    sans reproche, parce que c'était une option offerte et qu'elle disait son coût."""
    corpus = _Corpus(unites=(_UNITE,))

    resultat = ProposeTheme().execute(_state(bounds_overridden=True), _deps(corpus=corpus))

    assert "Bornes que vous avez conservées" in resultat.rationale


def test_le_gabarit_du_theme_est_deterministe():
    """Aucun modèle : même état, même phrase. Cent fois."""
    state = _state(plan_source="expositif", subject_matter="doctrinal")

    themes = {ProposeTheme().execute(state, _deps()).state.theme for _ in range(100)}

    assert len(themes) == 1


# =================================================================================================
# Le pipeline, fermé
# =================================================================================================


def test_les_huit_etages_sont_branches_dans_l_ordre():
    """E2 — les huit étages de la spec, plus le chemin inversé à sa place.

    `WeighConviction` n'est pas un neuvième palier : c'est l'**alternative** à l'étage 1, et
    il se lit ici juste avant lui. Les deux se rejoignent au bornage, et aucun étage aval ne
    sait par où la préparation est entrée."""
    from app.contexts.urim.engine import PIPELINE

    assert [type(etage).__name__ for etage in PIPELINE] == [
        "RouteEntry", "WeighConviction", "ResolvePassage", "BoundPericope", "ServeCorpus",
        "LoadContext", "BearAxes", "ShapeHomiletic", "ProposeTheme",
    ]


def test_aucun_des_huit_etages_ne_lit_le_contexte_ecclesial():
    """**Le test le plus important du dépôt, désormais sur huit étages réels.**

    E1 : le thème ne croise que l'axe retenu et l'historique. Une exception étroite pour l'étage 7
    aurait rendu le mur négociable — « un baptême dimanche c'est légitime » vaudrait demain pour
    « douze malades ce mois-ci »."""
    from app.contexts.urim.engine import PIPELINE
    from app.contexts.urim.engine import EngineDeps as _Deps
    from tests.contexts.urim.test_engine_architecture import attribute_names_read

    for etage in PIPELINE:
        lus = attribute_names_read(type(etage).execute)
        for interdit in _Deps.FORBIDDEN_FOR_STAGES:
            assert interdit not in lus, f"{type(etage).__name__} lit deps.{interdit}"
