"""**Étage 2 — le bornage.** L'unité littéraire, et pourquoi elle déborde parfois la demande.

Toute la règle tient dans une seule question, posée à chaque fois : **y a-t-il quelque chose à
arbitrer ?** (D-E, S8). Trois relations, trois réponses — et deux cas d'école qui reviennent :

- `Rom 1:16` **coupe** `Rom 1.16-17`, parce que le *γάρ* du v.17 **fonde** le v.16. Prêcher « je
  n'ai point honte de l'Évangile » sans « car en lui est révélée la justice de Dieu », c'est
  prêcher la moitié d'une phrase ;
- `Galates 5` **englobe** trois unités — 5:1-12 · 5:13-15 · 5:16-26.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.contexts.urim.calendar.domain.ports import NullEcclesialContext
from app.contexts.urim.engine import (
    BoundPericope,
    Bounds,
    EngineDeps,
    EntryMode,
    Outcome,
    PericopeView,
    Reference,
    StudyState,
)
from app.contexts.urim.engine.errors import StagePrerequisiteError
from app.contexts.urim.engine.stages.bound_pericope import EN_UN_SEUL, TEL_QUEL

ROM_1_16 = Reference(book="Romains", chapter=1, verse_start=16)
ROM_1_16_17 = Reference(book="Romains", chapter=1, verse_start=16, verse_end=17)
GALATES_5 = Reference(book="Galates", chapter=5)


def _unite(label, debut, fin, *, motif="unité curée", identifiant=None) -> PericopeView:
    return PericopeView(
        id=identifiant or uuid4(),
        bounds=Bounds(
            start=Reference(book="X", chapter=debut[0], verse_start=debut[1]),
            end=Reference(book="X", chapter=fin[0], verse_start=fin[1]),
        ),
        label=label,
        rationale=motif,
    )


GAL_5_1_12 = _unite("Galates 5:1-12", (5, 1), (5, 12), motif="l'appel à la liberté")
GAL_5_13_15 = _unite("Galates 5:13-15", (5, 13), (5, 15), motif="la liberté et le prochain")
GAL_5_16_26 = _unite("Galates 5:16-26", (5, 16), (5, 26), motif="marcher par l'Esprit")


class _Corpus:
    def __init__(self, unites=()):
        self._unites = tuple(unites)

    def snapshot(self) -> str:
        return "corpus-2026-08"

    def pericopes_for(self, reference):
        return self._unites

    # Non sollicités ici.
    def find_reference_span(self, mots):
        return None

    def scripture_affinity(self, mots):
        return 0.0

    def known_words(self, mots):
        return len(mots)

    def parse_reference_candidates(self, mots):
        return ()

    def check_reference(self, reference):
        return None

    def resolve_citation(self, mots):
        return ()


class _Doctrine:
    """Les axes dominants curés — `None` hors corpus, et c'est un état normal."""

    def __init__(self, axes=None):
        self._axes = axes or {}

    def dominant_axis(self, pericope_id: UUID):
        return self._axes.get(pericope_id)


class _Rien:
    def ceiling_reached(self) -> bool:
        return False


def _deps(corpus, doctrine=None):
    return EngineDeps(
        corpus=corpus, doctrine=doctrine or _Doctrine(), homiletics=_Rien(),
        context=NullEcclesialContext(), versions=_Rien(),
        clock=lambda: datetime(2026, 8, 6, tzinfo=UTC),
    )


def _state(resolved, *, refuses=()):
    return StudyState(
        session_id=uuid4(), church_id=uuid4(), author_id=uuid4(),
        corpus_snapshot="corpus-2026-08", entry_mode=EntryMode.REFERENCE,
        raw_input="peu importe", resolved=resolved, refused_axes=refuses,
    )


def _executer(state, corpus, doctrine=None):
    return BoundPericope().execute(state, _deps(corpus, doctrine))


def _codes(resultat):
    return [option.code for option in resultat.options]


# --- Coïncide : on ne fatigue pas quelqu'un qui a visé juste ------------------------------------


def test_des_bornes_conformes_a_l_unite_passent_sans_rien_demander():
    """`Rom 1:16-17` **est** la péricope : il n'y a rien à arbitrer, donc rien à demander.

    C'est la règle qui protège le moteur d'être pénible — n'interrompre que devant un vrai
    choix."""
    unite = _unite("Romains 1:16-17", (1, 16), (1, 17), motif="le γάρ du v.17 fonde le v.16")

    resultat = _executer(_state(ROM_1_16_17), _Corpus([unite]))

    assert resultat.outcome is Outcome.CONTINUE
    assert resultat.state.bounds == unite.bounds
    assert resultat.state.bounds_overridden is False
    assert "γάρ" in resultat.rationale


# --- Coupe : deux options, et la seconde dit ce qu'elle coûte -----------------------------------


def test_une_demande_qui_coupe_l_unite_rend_la_main_avec_deux_lectures():
    """**Le cas d'école de D-E.** `Rom 1:16` seul coupe l'unité.

    On ne corrige pas le pasteur — on lui montre l'unité **motivée** et on lui laisse ses bornes.
    """
    unite = _unite("Romains 1:16-17", (1, 16), (1, 17), motif="le γάρ du v.17 fonde le v.16")

    resultat = _executer(_state(ROM_1_16), _Corpus([unite]))

    assert resultat.outcome is Outcome.AWAIT
    assert _codes(resultat) == [str(unite.id), TEL_QUEL]
    assert resultat.state.bounds is None  # rien n'est décidé


def test_l_option_qui_accorde_la_liberte_dit_ce_qu_elle_coute():
    """**S22, dit au bon moment.**

    `homiletic_feasibility` est clée sur la péricope : hors d'elle, plus de faisabilité relue ni
    d'alerte de proof-texting. Le pasteur doit l'apprendre **en choisissant**, pas quatre étages
    plus loin quand quelque chose se dégrade sans qu'il sache pourquoi."""
    unite = _unite("Romains 1:16-17", (1, 16), (1, 17))

    resultat = _executer(_state(ROM_1_16), _Corpus([unite]))

    (tel_quel,) = [o for o in resultat.options if o.code == TEL_QUEL]
    assert "proof-texting" in tel_quel.rationale


# --- Englobe : N + 1 options ---------------------------------------------------------------------


def test_une_demande_qui_couvre_trois_unites_en_propose_quatre():
    """`Galates 5` = trois unités littéraires. La quatrième option est **le tout en un sermon** —
    un choix légitime, pas un repli."""
    corpus = _Corpus([GAL_5_1_12, GAL_5_13_15, GAL_5_16_26])

    resultat = _executer(_state(GALATES_5), corpus)

    assert resultat.outcome is Outcome.AWAIT
    assert len(resultat.options) == 4
    assert _codes(resultat)[-1] == EN_UN_SEUL
    assert "3 unités" in resultat.rationale


def test_chaque_unite_proposee_porte_son_motif():
    """`pericope.rationale` est `NOT NULL` en base — l'écran n'a donc jamais d'option muette."""
    corpus = _Corpus([GAL_5_1_12, GAL_5_13_15, GAL_5_16_26])

    resultat = _executer(_state(GALATES_5), corpus)

    assert all(option.rationale for option in resultat.options)
    assert "marcher par l'Esprit" in [o.rationale for o in resultat.options]


# --- S18 : la contrainte négative ordonne, elle ne refuse pas ------------------------------------


def test_l_unite_qui_porte_l_axe_refuse_passe_en_dernier_sans_disparaitre():
    """**S18** — « mais je ne veux pas d'une créature en Christ ».

    Refuser le texte, c'est décider à sa place ; l'ignorer, c'est lui donner le sermon dont il ne
    veut pas. La bonne issue est de **borner ailleurs dans la même péricope** — donc de montrer
    d'abord ce qui ne porte pas l'axe refusé, sans jamais retirer le reste."""
    doctrine = _Doctrine({GAL_5_1_12.id: "soteriologie", GAL_5_16_26.id: "pneumatologie"})
    corpus = _Corpus([GAL_5_1_12, GAL_5_13_15, GAL_5_16_26])

    resultat = _executer(_state(GALATES_5, refuses=("soteriologie",)), corpus, doctrine)

    codes = _codes(resultat)
    assert codes.index(str(GAL_5_1_12.id)) > codes.index(str(GAL_5_16_26.id))
    assert str(GAL_5_1_12.id) in codes  # écartée de la tête, jamais de la liste


def test_hors_pericopes_curees_aucun_ordre_et_jamais_d_erreur():
    """**La dégradation silencieuse de S18.**

    `dominant_axis` rend `None` : tout garde sa place, dans l'ordre du canon. Un refus qui ne
    peut pas s'appliquer ne doit surtout pas devenir une exception."""
    corpus = _Corpus([GAL_5_1_12, GAL_5_13_15, GAL_5_16_26])

    resultat = _executer(_state(GALATES_5, refuses=("soteriologie",)), corpus, _Doctrine())

    assert _codes(resultat)[:3] == [
        str(GAL_5_1_12.id), str(GAL_5_13_15.id), str(GAL_5_16_26.id)
    ]


def test_le_tri_est_stable_donc_deterministe():
    """À rang égal, l'ordre du canon est conservé — cent fois de suite.

    Deux unités qui se valent ne doivent pas changer de place d'une exécution à l'autre : le
    déterminisme du moteur en dépend."""
    doctrine = _Doctrine({GAL_5_1_12.id: "soteriologie"})
    corpus = _Corpus([GAL_5_1_12, GAL_5_13_15, GAL_5_16_26])
    state = _state(GALATES_5, refuses=("soteriologie",))

    ordres = {tuple(_codes(_executer(state, corpus, doctrine))) for _ in range(100)}

    assert len(ordres) == 1


# --- Hors corpus curé : on dégrade, on ne refuse jamais ------------------------------------------


def test_un_passage_sans_unite_curee_degrade_et_la_preparation_continue():
    """**Aucun mur un vendredi soir.** Le pasteur garde ses bornes et travaille.

    Mais le motif dit ce qui manque : c'est là que la suite du pipeline perdra la faisabilité."""
    resultat = _executer(_state(ROM_1_16), _Corpus())

    assert resultat.outcome is Outcome.DEGRADE
    assert resultat.state.bounds == Bounds(start=ROM_1_16, end=ROM_1_16)
    assert resultat.state.bounds_overridden is True
    assert "proof-texting" in resultat.rationale


def test_degrade_ne_coupe_pas_le_pipeline():
    """L'issue est un repli, pas un arrêt — `halts` reste faux."""
    assert not _executer(_state(ROM_1_16), _Corpus()).halts


# --- Le contrat de l'étage -----------------------------------------------------------------------


def test_l_etage_exige_un_passage_resolu():
    etage = BoundPericope()

    assert not etage.applies(_state(None))
    assert etage.applies(_state(ROM_1_16))


def test_un_passage_deja_borne_n_est_pas_reborne():
    etage = BoundPericope()
    borne = _state(ROM_1_16).with_(bounds=Bounds(start=ROM_1_16, end=ROM_1_16))

    assert not etage.applies(borne)


def test_forcer_l_etage_sans_passage_est_un_bug_pas_une_issue_metier():
    with pytest.raises(StagePrerequisiteError):
        _executer(_state(None), _Corpus())


def test_l_unite_retenue_pose_son_identite_avec_les_bornes():
    """Sans elle, les étages 4 à 6 n'auraient rien de curé à lire.

    La composition du pipeline, elle, est vérifiée une seule fois — dans
    `test_bear_axes.py`, avec le dernier étage livré."""
    unite = _unite("Romains 1:16-17", (1, 16), (1, 17))

    resultat = _executer(_state(ROM_1_16_17), _Corpus([unite]))

    assert resultat.state.pericope_id == unite.id
