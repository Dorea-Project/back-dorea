"""**Le détecteur d'entrée** (S33 · S34 · S35 · S36) — l'étage 0 ne fait plus confiance à l'onglet.

Les entrées de ces tests ne sont pas inventées : ce sont celles que les simulations à blanc ont
produites. « l'histoire de Jézabel » saisi en *référence*, « nexiiste », `Rom 8:1` accompagné de
sa citation — et surtout la **porte 16**, qui a cassé trois hypothèses de la première version :

    « Ma voiture 406, a besoin de reparation , jefgf Paradis »

Un micro resté ouvert. Elle a sa section à la fin, parce qu'elle vaut à elle seule trois constats.

Deux règles gouvernent tout le fichier, et elles se répondent :

- **le calcul propose, la personne dispose** — un signal qui contredit l'onglet rend la main,
  jamais ne reclasse en silence ;
- **en cas de doute, on route vers la conviction** — dire à un pasteur que sa phrase est
  incompréhensible alors qu'elle ne l'est pas est la pire erreur possible à la porte d'entrée.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.contexts.urim.calendar.domain.ports import NullEcclesialContext
from app.contexts.urim.engine import (
    EngineDeps,
    EntryMode,
    EntryOrigin,
    Outcome,
    ReferenceSpan,
    RouteEntry,
    StudyState,
    TraceEntry,
    UrimEngine,
)
from app.contexts.urim.engine.normalizer import tokens
from app.contexts.urim.engine.stages.route_entry import (
    CITATION_AFFINITY,
    MOTS_RECONNUS_MINIMUM,
    REFORMULER,
)

PORTE_16 = "Ma voiture 406, a besoin de reparation , jefgf Paradis"


class _Corpus:
    """Le corpus, réduit aux trois questions de fait que le détecteur lui pose.

    `livre` est le mot que le corpus reconnaît comme nom de livre — l'empan est calculé sur la
    position réelle du mot, pour que les tests portent sur la **contiguïté** et non sur un index
    écrit à la main."""

    def __init__(self, *, livre=None, code="Xxx", affinite=0.0, connus=None):
        self._livre, self._code, self._affinite = livre, code, affinite
        self._connus = connus

    def snapshot(self) -> str:
        return "corpus-2026-08"

    def find_reference_span(self, mots):
        if self._livre is None or self._livre not in mots:
            return None
        debut = list(mots).index(self._livre)
        return ReferenceSpan(book=self._code, start=debut, stop=debut + 1)

    def scripture_affinity(self, mots):
        return self._affinite

    def known_words(self, mots):
        if self._connus is None:
            return len(mots)  # tout est du français, par défaut
        return sum(1 for mot in mots if mot in self._connus)


class _Rien:
    def ceiling_reached(self) -> bool:
        return False


def _deps(corpus: _Corpus) -> EngineDeps:
    return EngineDeps(
        corpus=corpus,
        doctrine=_Rien(),
        homiletics=_Rien(),
        context=NullEcclesialContext(),
        versions=_Rien(),
        clock=lambda: datetime(2026, 8, 6, tzinfo=UTC),
    )


def _state(texte, *, saisi=None, origine=EntryOrigin.TYPED, trace=()) -> StudyState:
    """⚠️ `saisi` vaut **None** par défaut, et c'est tout le sujet de ces tests.

    Il n'y a plus d'onglet : rien n'est coché, donc le détecteur travaille seul. Passer un
    mode ici ne simule plus « ce que le client a envoyé » — cela simule **une correction du
    pasteur**, la seule écriture qui subsiste."""
    return StudyState(
        session_id=uuid4(),
        church_id=uuid4(),
        author_id=uuid4(),
        corpus_snapshot="corpus-2026-08",
        entry_mode=saisi,
        raw_input=texte,
        entry_origin=origine,
        trace=trace,
    )


def _executer(state, corpus):
    return RouteEntry().execute(state, _deps(corpus))


def _codes(resultat):
    return [option.code for option in resultat.options]


# --- Le signal confirme l'onglet : on ne dérange personne ------------------------------------


def test_une_reference_saisie_comme_reference_passe_sans_rien_demander():
    """*On ne fatigue pas quelqu'un qui a visé juste* — la règle du bornage, appliquée en amont."""
    resultat = _executer(
        _state("Romains 8 10 15"), _Corpus(livre="romains", code="Rom")
    )

    assert resultat.outcome is Outcome.CONTINUE
    assert resultat.state.entry_mode is EntryMode.REFERENCE
    assert "Rom" in resultat.rationale


def test_un_nom_de_livre_seul_couvre_toute_la_saisie_donc_c_est_une_reference():
    """S23 — « 1 Rois » n'est pas une saisie incomplète, c'est le livre entier.

    Aucun chiffre n'est exigé quand le nom **couvre toute la saisie** : c'est la seconde forme
    acceptée du bloc de référence."""
    resultat = _executer(_state("Rois"), _Corpus(livre="rois", code="1Kgs"))

    assert resultat.outcome is Outcome.CONTINUE
    assert resultat.state.entry_mode is EntryMode.REFERENCE


# --- S35 : un nom de livre ne suffit pas ------------------------------------------------------


@pytest.mark.parametrize(
    ("saisie", "livre"),
    [
        ("mon job me prend tout mon temps", "job"),
        ("il y a trop de juges dans cette assemblee", "juges"),
        ("les nombres ne mentent pas", "nombres"),
        ("les actes de la semaine derniere", "actes"),
    ],
)
def test_un_mot_francais_qui_est_aussi_un_livre_ne_fait_pas_une_reference(saisie, livre):
    """**S35** — `Job`, `Juges`, `Nombres`, `Actes` sont des mots courants.

    « il y a trop de juges dans cette assemblée » est même, pour couronner le tout, l'accusation
    de S20 — la conviction la plus délicate du produit routée vers le livre des Juges."""
    resultat = _executer(
        _state(saisie), _Corpus(livre=livre, code="XXX")
    )

    assert resultat.outcome is Outcome.CONTINUE
    assert resultat.state.entry_mode is EntryMode.CONVICTION


def test_le_meme_mot_suivi_d_un_chiffre_contigu_redevient_une_reference():
    """La contiguïté est le seul juge : « Job 38 » est un bloc, « mon job » n'en est pas un."""
    resultat = _executer(
        _state("Job 38"), _Corpus(livre="job", code="Job")
    )

    assert resultat.outcome is Outcome.CONTINUE
    assert resultat.state.entry_mode is EntryMode.REFERENCE


def test_un_chiffre_eloigne_du_nom_ne_fabrique_pas_un_bloc():
    """**Le piège que la porte 16 a révélé** : exiger un chiffre ne suffisait pas.

    « Ma voiture 406 » en contient un — mais entre « ma » et « 406 » il y a « voiture »."""
    resultat = _executer(
        _state("ma voiture 406 est en panne"),
        _Corpus(livre="ma", code="Mal"),
    )

    assert resultat.outcome is Outcome.CONTINUE
    assert resultat.state.entry_mode is EntryMode.CONVICTION


# --- Le signal contredit l'onglet : on rend la main ------------------------------------------


def test_une_conviction_passe_sans_qu_on_demande_rien():
    """**Le cas qui a motivé la suppression du mode.**

    Avant, un défaut `reference` comblait le silence et l'étage posait une question de
    désaccord à quelqu'un qui n'avait rien dit. Deux saisies sur trois étaient interrompues
    avant que le moteur n'ait rien fait d'utile — et la première impression d'Urim était une
    question administrative."""
    resultat = _executer(_state("l amour fraternel n existe plus dans l eglise"), _Corpus())

    assert resultat.outcome is Outcome.CONTINUE
    assert resultat.state.entry_mode is EntryMode.CONVICTION
    assert resultat.rationale.startswith("Lu comme une intention")


def test_une_lecture_tranchee_par_le_pasteur_n_est_jamais_recontestee():
    """⚠️ **Le seul sens que `entry_mode` peut encore avoir.**

    Il a disparu du corps HTTP : la seule écriture qui subsiste est la correction « ce n'est
    pas ça ». Le recontester reposerait éternellement la même question — le défaut déjà commis
    sur le bornage, une décision enregistrée et invisible pour l'étage qui la relit."""
    resultat = _executer(
        _state("l amour fraternel a disparu", saisi=EntryMode.REFERENCE), _Corpus()
    )

    assert resultat.outcome is Outcome.CONTINUE
    assert resultat.state.entry_mode is EntryMode.REFERENCE
    assert "retenue par vous" in resultat.rationale


def test_la_sortie_est_offerte_avant_la_lecture_sur_une_dictee():
    """L'ordre n'est pas cosmétique. Sur une dictée, la première option est **la sortie** :
    quelqu'un dont le micro s'est ouvert cherche à refermer, pas à choisir une lecture.

    Il n'y a plus qu'**une** lecture proposée — la seconde disait « ce que vous aviez
    indiqué », et le pasteur n'indique plus rien."""
    resultat = _executer(
        _state("l amour fraternel a disparu", origine=EntryOrigin.DICTATED), _Corpus()
    )

    assert _codes(resultat) == [REFORMULER, "conviction"]


def test_le_pasteur_tranche_et_le_moteur_ne_redemande_jamais():
    """🔴 **Le garde anti-boucle, éprouvé sur le vrai chemin.**

    L'ancienne version rejouait avec la trace de la première exécution, donc l'étage ne
    s'appliquait plus. Elle ne prouvait rien : **le service ne persiste pas la trace**. Elle
    repart vide à chaque rejeu, l'étage se ré-exécute toujours, et un pasteur qui maintenait
    sa lecture contre le détecteur recevait la même question indéfiniment.

    On rejoue donc ici comme le service le fait réellement — trace vide, trois fois."""
    moteur = UrimEngine(_deps(_Corpus()), pipeline=(RouteEntry(),))

    depart = moteur.run(_state("l amour fraternel a disparu"))
    assert depart.state.entry_mode is EntryMode.CONVICTION  # détecté, rien n'était indiqué

    tranche = _state("l amour fraternel a disparu", saisi=EntryMode.REFERENCE)
    for _ in range(3):
        reprise = moteur.run(tranche)
        assert reprise.results[-1].outcome is Outcome.CONTINUE, "le moteur redemande"
        assert reprise.state.entry_mode is EntryMode.REFERENCE


# --- L'entrée hybride : un cadeau, pas un conflit ---------------------------------------------


def test_une_reference_avec_sa_citation_ne_rend_jamais_la_main():
    """S16 — **c'est ici que l'entrée hybride se résout.**

    Deux sources qui se corroborent ne sont pas un conflit. On résout sur la référence ; la
    citation servira à vérifier, et c'est elle qui attrape « vous citez Rm 8:1 mais votre texte
    est Rm 8:34 »."""
    resultat = _executer(
        _state("Romains 8 1 il n y a donc maintenant aucune condamnation"),
        _Corpus(livre="romains", code="Rom", affinite=0.9),
    )

    assert resultat.outcome is Outcome.CONTINUE
    assert resultat.state.entry_mode is EntryMode.REFERENCE
    assert "vérifier" in resultat.rationale


# --- S34 : un décompte, pas une proportion ----------------------------------------------------


def test_un_seul_mot_reconnu_suffit_a_ouvrir_la_conviction():
    """**S34** — la question n'est pas « quelle proportion est du français ? » mais « y a-t-il
    quelque chose de reconnaissable ? ».

    C'est ce qui empêche un token pourri sur neuf de faire basculer une phrase entière."""
    resultat = _executer(
        _state("azkkq paradis mlfjz qqz"),
        _Corpus(connus={"paradis"}),
    )

    assert MOTS_RECONNUS_MINIMUM == 1
    assert resultat.outcome is Outcome.CONTINUE
    assert resultat.state.entry_mode is EntryMode.CONVICTION


def test_seul_ce_qui_n_a_rien_de_reconnaissable_est_refuse():
    """Le motif **attire à la correction** et ne renvoie jamais le verdict du corpus.

    « Aucune péricope ne porte cet axe » accuserait le corpus d'un clavier."""
    resultat = _executer(
        _state("azkkq mlfjz qqz"), _Corpus(connus=set())
    )

    assert resultat.outcome is Outcome.REFUSE
    assert "peut-être" in resultat.rationale
    assert "péricope" not in resultat.rationale


@pytest.mark.parametrize("vide", ["", "   ", "\n\t", "!!! ??? ...", "'''"])
def test_une_saisie_sans_un_seul_mot_est_refusee(vide: str):
    """Ponctuation seule, apostrophes seules, espaces : il n'y a rien à router."""
    assert _executer(_state(vide), _Corpus()).outcome is Outcome.REFUSE


def test_le_seuil_de_citation_est_inclusif():
    """Pile au seuil, on lit une citation — la borne penche vers l'interprétation la plus riche."""
    resultat = _executer(
        _state("aucune condamnation pour ceux qui sont en Jesus Christ"),
        _Corpus(affinite=CITATION_AFFINITY),
    )

    assert resultat.outcome is Outcome.CONTINUE
    assert resultat.state.entry_mode is EntryMode.CITATION


# --- S36 : la provenance, et le micro resté ouvert --------------------------------------------


def test_une_dictee_qui_donne_une_intention_se_fait_toujours_confirmer():
    """**S36 — le vrai correctif de la porte 16.**

    Le doute ne porte pas sur la lecture : il porte sur le fait que le pasteur ait voulu saisir
    quoi que ce soit. Le moteur lui rend ce qu'il a entendu, et attend."""
    resultat = _executer(
        _state(PORTE_16, origine=EntryOrigin.DICTATED), _Corpus()
    )

    assert resultat.outcome is Outcome.AWAIT
    assert "J'ai entendu" in resultat.rationale
    assert PORTE_16 in resultat.rationale
    assert _codes(resultat) == [REFORMULER, "conviction"]


def test_la_meme_saisie_tapee_ne_demande_rien():
    """La provenance est la **seule** différence — et c'est tout l'intérêt de S36.

    Quelqu'un qui tape ces mots les a voulus ; quelqu'un dont le micro s'est ouvert, non."""
    resultat = _executer(
        _state(PORTE_16, origine=EntryOrigin.TYPED), _Corpus()
    )

    assert resultat.outcome is Outcome.CONTINUE
    assert resultat.state.entry_mode is EntryMode.CONVICTION


def test_une_dictee_univoque_passe_sans_confirmation():
    """On ne fait pas confirmer une dictée nette : « Romains 8 » sorti d'un micro reste
    « Romains 8 ». La friction est réservée au doute."""
    resultat = _executer(
        _state("Romains 8", origine=EntryOrigin.DICTATED),
        _Corpus(livre="romains", code="Rom"),
    )

    assert resultat.outcome is Outcome.CONTINUE


def test_un_charabia_dicte_dit_que_le_micro_a_pu_se_declencher_seul():
    """Le motif change avec la provenance : accuser quelqu'un d'avoir mal tapé alors que son
    téléphone l'a trahi, c'est le laisser chercher au mauvais endroit."""
    resultat = _executer(
        _state("azkkq mlfjz", origine=EntryOrigin.DICTATED),
        _Corpus(connus=set()),
    )

    assert resultat.outcome is Outcome.REFUSE
    assert "micro" in resultat.rationale


# --- La porte 16, jouée en entier -------------------------------------------------------------


def test_porte_16_le_micro_ouvert_de_pasteur_cedric():
    """**Le cas d'école du détecteur, joué avec un corpus honnête.**

        « Ma voiture 406, a besoin de reparation , jefgf Paradis »

    Trois pièges dans une seule phrase : « ma » que le corpus peut reconnaître comme Malachie,
    « 406 » qui ressemble à un chapitre, et « jefgf » qui n'est pas une faute de frappe mais une
    **mauvaise transcription**. Aucun des trois ne fait dérailler le moteur — et la seule chose
    qui compte vraiment, c'est que la dictée soit confirmée avant d'aller plus loin."""
    mots = tokens(PORTE_16)
    assert mots == (
        "ma", "voiture", "406", "a", "besoin", "de", "reparation", "jefgf", "paradis",
    )

    resultat = _executer(
        _state(PORTE_16, origine=EntryOrigin.DICTATED),
        # « ma » reconnu comme Malachie, et un seul mot du lexique : le pire cas plausible.
        _Corpus(livre="ma", code="Mal", connus={"paradis"}),
    )

    assert resultat.outcome is Outcome.AWAIT
    assert "J'ai entendu" in resultat.rationale
    assert REFORMULER in _codes(resultat)


# --- Le contrat du moteur, sur un étage réel --------------------------------------------------


def test_l_etage_ne_s_applique_qu_une_fois():
    etage = RouteEntry()
    vierge = _state("Romains 8")

    assert etage.applies(vierge)
    assert not etage.applies(vierge.with_(trace=(TraceEntry("route_entry", "déjà routé"),)))


def test_le_detecteur_est_deterministe():
    """Même saisie, même corpus ⇒ même sortie. Cent fois."""
    corpus = _Corpus()
    state = _state("l amour fraternel a disparu")

    sorties = {
        (r.outcome, r.rationale, tuple(_codes(r)))
        for r in (_executer(state, corpus) for _ in range(100))
    }

    assert len(sorties) == 1


# --- L'accueil (terrain, 2026-08-22) ---------------------------------------------------------
#
# 🔴 Sur un téléphone, en conditions réelles : « bonjour Urim » a ouvert une préparation, et le
# moteur a rendu 1 Corinthiens. Le corpus **reconnaît** `salut`, `merci` et `urim` (Exode 28:30) :
# `MOTS_RECONNUS_MINIMUM = 1` ne pouvait pas les séparer d'une intention.
#
# Les corpus de ces tests reconnaissent donc **tout** (`connus=None`), comme le vrai : c'est le
# seul réglage où le défaut se reproduit.


def test_bonjour_urim_n_ouvre_aucune_preparation():
    """Le défaut du 22/08, dans sa forme exacte : le nom du produit est dans l'Écriture."""
    resultat = _executer(_state("bonjour Urim"), _Corpus())

    assert resultat.outcome is Outcome.REFUSE
    assert resultat.state.entry_mode is None, "aucune lecture ne se pose sur un salut"


def test_l_accueil_dit_ce_qu_il_fait_et_ce_qu_il_ne_fait_pas():
    """Un refus qui ne dit rien serait un mur à la porte — et le pasteur a seulement salué."""
    motif = _executer(_state("bonjour"), _Corpus()).rationale

    assert "prêche pas à votre place" in motif
    assert motif.rstrip().endswith("?"), "l'accueil rend la main par une question ouverte"


@pytest.mark.parametrize("saisie", ["salut", "merci Urim", "bonsoir", "ok merci beaucoup"])
def test_les_mots_de_la_politesse_sont_aussi_ceux_de_la_doctrine(saisie):
    """`salut` et `merci` sont dans le corpus. C'est un recouvrement, pas une coïncidence."""
    assert _executer(_state(saisie), _Corpus()).outcome is Outcome.REFUSE


def test_une_politesse_qui_porte_un_sujet_passe_intacte():
    """**La borne haute, et elle compte autant que la règle** (scénario A2).

    Une règle de civilité trop gourmande crée une panne pire que celle qu'elle répare : le
    pasteur salue poliment, et son travail est jeté."""
    resultat = _executer(
        _state("Bonjour, je veux prêcher sur le pardon dimanche"), _Corpus()
    )

    assert resultat.outcome is not Outcome.REFUSE
    assert resultat.state.entry_mode is EntryMode.CONVICTION


def test_un_seul_mot_hors_liste_rend_la_main_au_corpus():
    """Le vocabulaire est fermé : ce qu'il ne connaît pas, il ne le juge pas."""
    resultat = _executer(_state("bonjour Romains 8"), _Corpus(livre="romains", code="Rom"))

    assert resultat.outcome is not Outcome.REFUSE
    assert resultat.state.entry_mode is EntryMode.REFERENCE
