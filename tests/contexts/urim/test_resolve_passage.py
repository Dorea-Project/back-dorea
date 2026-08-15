"""**Étage 1 — la résolution.** Identifier le passage, jamais la version.

Trois règles se répondent dans ce fichier, et chacune vient d'une simulation à blanc :

- **S19 · un fait n'interrompt pas.** Livre inconnu, chapitre hors du livre, verset hors du
  chapitre : le candidat est écarté **avec son motif**, et le moteur continue s'il en reste un.
- **S2 · un candidat faible reste un candidat.** On ne refuse que l'ensemble **vide**. Confondre
  « vide » et « médiocre » ferait perdre le plus beau mécanisme de la spec.
- **S16 · la citation vérifie, elle ne conclut pas.** Elle ne parle que si elle contredit.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.contexts.urim.calendar.domain.ports import NullEcclesialContext
from app.contexts.urim.engine import (
    CitationCandidate,
    EngineDeps,
    EntryMode,
    Outcome,
    Reference,
    ReferenceCheck,
    ResolvePassage,
    StudyState,
)
from app.contexts.urim.engine.errors import StagePrerequisiteError
from app.contexts.urim.engine.stages.resolve_passage import (
    ECART_NET,
    ORIGINE_CORRECTION,
    ORIGINE_LETTRE,
    ORIGINE_SENS,
    PAS_UNE_CITATION,
)

ROM_8_1 = Reference(book="Romains", chapter=8, verse_start=1)
ROM_8_34 = Reference(book="Romains", chapter=8, verse_start=34)
UN_ROIS = Reference(book="1 Rois")
DEUX_ROIS = Reference(book="2 Rois")
COR_5_17 = Reference(book="1 Corinthiens", chapter=5, verse_start=17)


class _Corpus:
    def __init__(self, *, candidats=(), inexistants=None, citations=()):
        self._candidats = tuple(candidats)
        self._inexistants = inexistants or {}
        self._citations = tuple(citations)

    def snapshot(self) -> str:
        return "corpus-2026-08"

    def parse_reference_candidates(self, mots):
        return self._candidats

    def check_reference(self, reference):
        motif = self._inexistants.get(reference)
        return ReferenceCheck(exists=motif is None, rationale=motif or "")

    def resolve_citation(self, mots):
        return self._citations

    # Non sollicités par cet étage, présents pour satisfaire le port.
    def find_reference_span(self, mots):
        return None

    def scripture_affinity(self, mots):
        return 0.0

    def known_words(self, mots):
        return len(mots)


class _Rien:
    def ceiling_reached(self) -> bool:
        return False

    def axes(self):
        """Aucun axe curé — le chemin inversé s'arrête proprement au lieu d'exploser.

        C'est aussi le comportement réel d'un corpus dont la curation n'a pas commencé."""
        return ()


def _deps(corpus):
    return EngineDeps(
        corpus=corpus, doctrine=_Rien(), homiletics=_Rien(),
        context=NullEcclesialContext(), versions=_Rien(),
        clock=lambda: datetime(2026, 8, 6, tzinfo=UTC),
    )


def _state(mode, texte):
    return StudyState(
        session_id=uuid4(), church_id=uuid4(), author_id=uuid4(),
        corpus_snapshot="corpus-2026-08", entry_mode=mode, raw_input=texte,
    )


def _executer(state, corpus):
    return ResolvePassage().execute(state, _deps(corpus))


def _codes(resultat):
    return [option.code for option in resultat.options]


# --- La conviction ne passe pas par ici --------------------------------------------------------


def test_la_conviction_saute_cet_etage():
    """Chemin inversé (§7) : elle rejoint le pipeline à l'étage 2, sans passer par la résolution."""
    etage = ResolvePassage()

    assert not etage.applies(_state(EntryMode.CONVICTION, "l amour fraternel a disparu"))
    assert etage.applies(_state(EntryMode.REFERENCE, "Romains 8"))


def test_forcer_l_etage_sur_une_conviction_est_un_bug_pas_une_issue_metier():
    """`StagePrerequisiteError` — un étage ne travaille jamais sur un état incomplet."""
    with pytest.raises(StagePrerequisiteError):
        _executer(_state(EntryMode.CONVICTION, "l eglise est fatiguee"), _Corpus())


def test_un_passage_deja_resolu_n_est_pas_reresolu():
    etage = ResolvePassage()
    deja = _state(EntryMode.REFERENCE, "Romains 8:1").with_(resolved=ROM_8_1)

    assert not etage.applies(deja)


# --- S19 : un fait écarte, il n'interrompt pas -------------------------------------------------


def test_un_verset_hors_du_chapitre_est_ecarte_avec_son_motif_et_le_moteur_continue():
    """« 1 Corinthiens 5 compte 13 versets » apprend quelque chose ; « invalide » ne dit rien.

    Le candidat valide passe, et le motif porte ce qui a été écarté — écarter en silence
    laisserait le pasteur chercher un verset qui n'existe pas."""
    corpus = _Corpus(
        candidats=(COR_5_17, ROM_8_1),
        inexistants={COR_5_17: "1 Corinthiens 5 compte 13 versets"},
    )

    resultat = _executer(_state(EntryMode.REFERENCE, "1 Cor 5:17 ou Rom 8:1"), corpus)

    assert resultat.outcome is Outcome.CONTINUE
    assert resultat.state.resolved == ROM_8_1
    assert "13 versets" in resultat.rationale


def test_aucun_candidat_valide_donne_un_refus_qui_dit_ce_qui_a_ete_ecarte():
    corpus = _Corpus(
        candidats=(COR_5_17,), inexistants={COR_5_17: "1 Corinthiens 5 compte 13 versets"}
    )

    resultat = _executer(_state(EntryMode.REFERENCE, "1 Corinthiens 5:17"), corpus)

    assert resultat.outcome is Outcome.REFUSE
    assert "13 versets" in resultat.rationale


# --- Le fait reste, la correction devient un geste ---------------------------------------------


def test_la_correction_du_modele_est_une_option_et_le_fait_reste_le_motif():
    """🔴 **La bordure posait la trouvaille comme résolue, et le fait disparaissait.**

    `Hébreux 2:29` — une note réelle du Pasteur X, dans un chapitre qui compte 18 versets —
    rendait `Hébreux 2:9` et l'écran du bornage. Le pasteur demandait le verset 29, recevait le
    verset 9, et perdait la seule information utile : celle qu'Urim savait donner depuis le
    premier jour et n'avait jamais pu dire.

    *Le calcul propose, la personne dispose* — la règle de l'étage 0, appliquée ici."""
    corpus = _Corpus(
        candidats=(COR_5_17,), inexistants={COR_5_17: "1 Corinthiens 5 compte 13 versets"}
    )
    etat = _state(EntryMode.REFERENCE, "1 Corinthiens 5:17").with_(
        suggested_reference=ROM_8_1
    )

    resultat = _executer(etat, corpus)

    assert resultat.outcome is Outcome.AWAIT
    assert "13 versets" in resultat.rationale, "le fait a été effacé par la correction"
    assert _codes(resultat) == ["Romains 8:1"]
    assert resultat.state.resolved is None, "une proposition ne résout pas"


def test_la_correction_ne_se_confond_pas_avec_un_texte_sur_le_sujet():
    """⚠️ « Trouvé dans vos mots », « traite votre sujet » et « je crois que vous vouliez écrire
    ceci » ne se valent pas. Confondre la troisième avec `sens` ferait croire au pasteur qu'on
    lui propose un texte sur son thème, alors qu'on lui propose une correction de frappe."""
    corpus = _Corpus(
        candidats=(COR_5_17,), inexistants={COR_5_17: "13 versets"}
    )
    etat = _state(EntryMode.REFERENCE, "1 Corinthiens 5:17").with_(
        suggested_reference=ROM_8_1
    )

    (option,) = _executer(etat, corpus).options

    assert option.origin == ORIGINE_CORRECTION
    assert option.origin not in (ORIGINE_SENS, ORIGINE_LETTRE)


def test_sans_correction_proposee_le_refus_reste_un_refus():
    """La garde ne doit rien changer quand le modèle n'a rien trouvé — ou n'est pas branché."""
    corpus = _Corpus(
        candidats=(COR_5_17,), inexistants={COR_5_17: "1 Corinthiens 5 compte 13 versets"}
    )

    resultat = _executer(_state(EntryMode.REFERENCE, "1 Corinthiens 5:17"), corpus)

    assert resultat.outcome is Outcome.REFUSE
    assert not resultat.options


# --- S24 : plusieurs livres portent le même nom ------------------------------------------------


def test_deux_livres_possibles_rendent_la_main_au_lieu_d_en_choisir_un():
    """S24 — « 1 Roi ou 2 Roi, il s'agit de Jézabel ».

    L'hésitation du pasteur est une **question mal posée, pas fausse** : on lui rend les livres
    possibles plutôt que d'en élire un à sa place."""
    corpus = _Corpus(candidats=(UN_ROIS, DEUX_ROIS))

    resultat = _executer(_state(EntryMode.REFERENCE, "Rois"), corpus)

    assert resultat.outcome is Outcome.AWAIT
    assert _codes(resultat) == ["1 Rois", "2 Rois"]
    assert resultat.state.resolved is None  # rien n'est décidé


# --- S2 : la conflation de mémoire --------------------------------------------------------------


def test_une_citation_reconnue_nettement_passe_sans_rien_demander():
    corpus = _Corpus(
        citations=(
            CitationCandidate(reference=ROM_8_1, score=0.92, rationale="ancre « condamnation »"),
            CitationCandidate(reference=ROM_8_34, score=0.31, rationale="ancre partagée"),
        )
    )

    resultat = _executer(
        _state(EntryMode.CITATION, "il n y a donc maintenant aucune condamnation"), corpus
    )

    assert resultat.outcome is Outcome.CONTINUE
    assert resultat.state.resolved == ROM_8_1


def test_deux_textes_qui_se_valent_disent_ce_que_le_moteur_voit_pas_ce_que_le_pasteur_a_fait():
    """⚠️ **Le motif dit ce que le moteur a trouvé, jamais ce que la mémoire du pasteur a fait.**

    Il disait *« votre mémoire a probablement fusionné plusieurs passages »*. Sur une vraie
    conflation c'est juste et utile — mais rien ici ne distingue une conflation d'un **thème
    écrit en mots bibliques**. « L'amour du prochain » alignait cinq versets, et le pasteur
    s'entendait reprocher un défaut de mémoire qu'il n'avait pas commis pendant que le moteur,
    lui, avait mal lu la saisie."""
    corpus = _Corpus(
        citations=(
            CitationCandidate(reference=ROM_8_1, score=0.52, rationale="première moitié"),
            CitationCandidate(reference=ROM_8_34, score=0.48, rationale="seconde moitié"),
        )
    )

    resultat = _executer(_state(EntryMode.CITATION, "aucune condamnation qui intercede"), corpus)

    assert resultat.outcome is Outcome.AWAIT
    assert "à égalité" in resultat.rationale
    assert "mémoire" not in resultat.rationale
    assert _codes(resultat)[:2] == ["Romains 8:1", "Romains 8:34"]


def test_une_sortie_du_chemin_citation_est_toujours_offerte():
    """**Cinq candidats sans porte de secours enferment celui qui n'a jamais cité.**

    Le pasteur qui tape son sujet en mots bibliques n'avait aucun moyen de le dire : l'étage 0
    voyait un recouvrement fort, l'étage 1 alignait des versets, et le chemin de l'intention
    restait inatteignable. L'option rouvre les dix loci — c'est la seule de la liste qui ne
    prétend pas connaître ce qu'il visait."""
    corpus = _Corpus(
        citations=(
            CitationCandidate(reference=ROM_8_1, score=0.52, rationale="première moitié"),
            CitationCandidate(reference=ROM_8_34, score=0.48, rationale="seconde moitié"),
        )
    )

    resultat = _executer(_state(EntryMode.CITATION, "l amour du prochain"), corpus)

    assert PAS_UNE_CITATION in _codes(resultat)
    # **En dernier, jamais en premier** : elle est la sortie, pas la réponse attendue.
    assert _codes(resultat)[-1] == PAS_UNE_CITATION


def test_seul_l_ensemble_vide_est_un_refus():
    """**S2, la frontière à ne pas rater.** Un candidat faible reste un candidat.

    Le refus ne dit pas « introuvable » : il dit quoi faire ensuite."""
    resultat = _executer(_state(EntryMode.CITATION, "une phrase qui n existe pas"), _Corpus())

    assert resultat.outcome is Outcome.REFUSE
    assert "entrez une référence" in resultat.rationale


def test_l_ecart_qui_departage_est_inclusif():
    """Pile à l'écart, le premier l'emporte — la borne penche vers la réponse, pas vers la
    question."""
    corpus = _Corpus(
        citations=(
            CitationCandidate(reference=ROM_8_1, score=0.60, rationale="ancre nette"),
            CitationCandidate(reference=ROM_8_34, score=0.60 - ECART_NET, rationale="partagée"),
        )
    )

    resultat = _executer(_state(EntryMode.CITATION, "aucune condamnation"), corpus)

    assert resultat.outcome is Outcome.CONTINUE


# --- S16 : la citation vérifie, elle ne conclut pas ---------------------------------------------


def test_la_citation_attrape_une_reference_de_memoire_fausse():
    """**Le cadeau de l'entrée hybride.**

    « vous citez Rm 8:1 mais votre texte est Rm 8:34 » — l'erreur de mémoire la plus fréquente,
    et **seule la double entrée l'attrape** : ni la référence seule, ni la citation seule."""
    corpus = _Corpus(
        candidats=(ROM_8_1,),
        citations=(
            CitationCandidate(
                reference=ROM_8_34, score=0.95, rationale="« qui intercède pour nous »"
            ),
        ),
    )

    resultat = _executer(
        _state(EntryMode.REFERENCE, "Romains 8:1 c est lui qui intercede pour nous"), corpus
    )

    assert resultat.outcome is Outcome.AWAIT
    assert "Romains 8:1" in resultat.rationale
    assert "Romains 8:34" in resultat.rationale


def test_une_citation_qui_concorde_reste_silencieuse():
    """Elle ne parle **que** si elle contredit : une entrée hybride est un cadeau, pas une
    occasion supplémentaire d'interrompre."""
    corpus = _Corpus(
        candidats=(ROM_8_1,),
        citations=(CitationCandidate(reference=ROM_8_1, score=0.95, rationale="concorde"),),
    )

    resultat = _executer(_state(EntryMode.REFERENCE, "Romains 8:1 aucune condamnation"), corpus)

    assert resultat.outcome is Outcome.CONTINUE
    assert resultat.state.resolved == ROM_8_1


def test_une_citation_indecise_ne_contredit_rien():
    """Deux candidats qui se valent ne peuvent contredire personne — on ne fabrique pas une
    divergence à partir d'une hésitation."""
    corpus = _Corpus(
        candidats=(ROM_8_1,),
        citations=(
            CitationCandidate(reference=ROM_8_34, score=0.52, rationale="a"),
            CitationCandidate(reference=ROM_8_1, score=0.50, rationale="b"),
        ),
    )

    resultat = _executer(_state(EntryMode.REFERENCE, "Romains 8:1 quelque chose"), corpus)

    assert resultat.outcome is Outcome.CONTINUE


# --- Ce que le pasteur lit ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("reference", "attendu"),
    [
        (Reference(book="1 Rois"), "1 Rois"),
        (Reference(book="Galates", chapter=5), "Galates 5"),
        (Reference(book="Romains", chapter=8, verse_start=1), "Romains 8:1"),
        (
            Reference(book="Romains", chapter=8, verse_start=10, verse_end=15),
            "Romains 8:10-15",
        ),
    ],
)
def test_la_reference_se_dit_au_degre_de_precision_qu_elle_porte(reference, attendu):
    """S7 et S23 — le livre entier, le chapitre entier, le verset, l'intervalle."""
    from app.contexts.urim.engine.stages.resolve_passage import _dire

    assert _dire(reference) == attendu


def test_le_detecteur_et_la_resolution_s_enchainent():
    """Les deux étages livrés, bout à bout, sur le vrai pipeline."""
    from app.contexts.urim.engine import PIPELINE, UrimEngine

    corpus = _Corpus(candidats=(ROM_8_1,))
    corpus.find_reference_span = lambda mots: None  # aucun livre reconnu par le détecteur
    corpus.known_words = lambda mots: len(mots)

    run = UrimEngine(_deps(corpus), pipeline=PIPELINE).run(
        _state(EntryMode.CONVICTION, "l amour fraternel a disparu")
    )

    # Routé en conviction, puis **l'étage 1 ne s'applique pas** — c'est ce que ce test garde.
    # La conviction est reprise par le chemin inversé (§7), jamais par la résolution de
    # passage : l'une part d'un texte, l'autre y arrive.
    codes = [entree.stage_code for entree in run.state.trace]
    assert codes == ["route_entry", "weigh_conviction"]
    assert "resolve_passage" not in codes
