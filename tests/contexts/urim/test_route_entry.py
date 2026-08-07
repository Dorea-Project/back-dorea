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
    Decision,
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


def _state(saisi, texte, *, origine=EntryOrigin.TYPED, trace=()) -> StudyState:
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
        _state(EntryMode.REFERENCE, "Romains 8 10 15"), _Corpus(livre="romains", code="Rom")
    )

    assert resultat.outcome is Outcome.CONTINUE
    assert resultat.state.entry_mode is EntryMode.REFERENCE
    assert "Rom" in resultat.rationale


def test_un_nom_de_livre_seul_couvre_toute_la_saisie_donc_c_est_une_reference():
    """S23 — « 1 Rois » n'est pas une saisie incomplète, c'est le livre entier.

    Aucun chiffre n'est exigé quand le nom **couvre toute la saisie** : c'est la seconde forme
    acceptée du bloc de référence."""
    resultat = _executer(_state(EntryMode.REFERENCE, "Rois"), _Corpus(livre="rois", code="1Kgs"))

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
        _state(EntryMode.CONVICTION, saisie), _Corpus(livre=livre, code="XXX")
    )

    assert resultat.outcome is Outcome.CONTINUE
    assert resultat.state.entry_mode is EntryMode.CONVICTION


def test_le_meme_mot_suivi_d_un_chiffre_contigu_redevient_une_reference():
    """La contiguïté est le seul juge : « Job 38 » est un bloc, « mon job » n'en est pas un."""
    resultat = _executer(
        _state(EntryMode.REFERENCE, "Job 38"), _Corpus(livre="job", code="Job")
    )

    assert resultat.outcome is Outcome.CONTINUE
    assert resultat.state.entry_mode is EntryMode.REFERENCE


def test_un_chiffre_eloigne_du_nom_ne_fabrique_pas_un_bloc():
    """**Le piège que la porte 16 a révélé** : exiger un chiffre ne suffisait pas.

    « Ma voiture 406 » en contient un — mais entre « ma » et « 406 » il y a « voiture »."""
    resultat = _executer(
        _state(EntryMode.CONVICTION, "ma voiture 406 est en panne"),
        _Corpus(livre="ma", code="Mal"),
    )

    assert resultat.outcome is Outcome.CONTINUE
    assert resultat.state.entry_mode is EntryMode.CONVICTION


# --- Le signal contredit l'onglet : on rend la main ------------------------------------------


def test_une_conviction_saisie_dans_reference_rend_la_main_au_lieu_de_fausser_le_calcul():
    """**Le cas qui a motivé tout ce lot.**

    Reclasser en silence donnerait au pasteur le pipeline de la conviction sans qu'il comprenne —
    la machine déciderait à sa place (S10). Continuer comme si c'était une référence fausserait
    tout l'aval."""
    resultat = _executer(
        _state(EntryMode.REFERENCE, "l amour fraternel n existe plus dans l eglise"),
        _Corpus(),
    )

    assert resultat.outcome is Outcome.AWAIT
    assert resultat.state.entry_mode is EntryMode.REFERENCE  # rien n'est décidé
    assert _codes(resultat) == ["conviction", "reference"]
    assert all(option.rationale for option in resultat.options)


def test_la_lecture_soutenue_par_les_faits_est_proposee_en_premier():
    """L'ordre n'est pas cosmétique : le détecté d'abord, le saisi ensuite — sans jamais le
    retirer."""
    resultat = _executer(
        _state(EntryMode.CONVICTION, "Romains 8"), _Corpus(livre="romains", code="Rom")
    )

    assert _codes(resultat) == ["reference", "conviction"]


def test_le_pasteur_tranche_et_le_moteur_ne_redemande_jamais():
    """**Le garde qui évite la boucle infinie.**

    Sans lui : le pasteur choisit, le moteur repart, l'étage 0 s'applique de nouveau, re-détecte,
    et redemande la même chose."""
    corpus = _Corpus()
    moteur = UrimEngine(_deps(corpus), pipeline=(RouteEntry(),))
    depart = moteur.run(_state(EntryMode.REFERENCE, "l amour fraternel a disparu"))
    assert depart.halted

    reprise = moteur.resume(
        depart.state,
        Decision(
            stage_code="route_entry",
            option_code="conviction",
            decided_by=uuid4(),
            changes=(("entry_mode", EntryMode.CONVICTION),),
        ),
    )

    assert reprise.results == ()  # l'étage ne s'applique plus
    assert reprise.state.entry_mode is EntryMode.CONVICTION


# --- L'entrée hybride : un cadeau, pas un conflit ---------------------------------------------


def test_une_reference_avec_sa_citation_ne_rend_jamais_la_main():
    """S16 — **c'est ici que l'entrée hybride se résout.**

    Deux sources qui se corroborent ne sont pas un conflit. On résout sur la référence ; la
    citation servira à vérifier, et c'est elle qui attrape « vous citez Rm 8:1 mais votre texte
    est Rm 8:34 »."""
    resultat = _executer(
        _state(EntryMode.CITATION, "Romains 8 1 il n y a donc maintenant aucune condamnation"),
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
        _state(EntryMode.CONVICTION, "azkkq paradis mlfjz qqz"),
        _Corpus(connus={"paradis"}),
    )

    assert MOTS_RECONNUS_MINIMUM == 1
    assert resultat.outcome is Outcome.CONTINUE
    assert resultat.state.entry_mode is EntryMode.CONVICTION


def test_seul_ce_qui_n_a_rien_de_reconnaissable_est_refuse():
    """Le motif **attire à la correction** et ne renvoie jamais le verdict du corpus.

    « Aucune péricope ne porte cet axe » accuserait le corpus d'un clavier."""
    resultat = _executer(
        _state(EntryMode.CONVICTION, "azkkq mlfjz qqz"), _Corpus(connus=set())
    )

    assert resultat.outcome is Outcome.REFUSE
    assert "peut-être" in resultat.rationale
    assert "péricope" not in resultat.rationale


@pytest.mark.parametrize("vide", ["", "   ", "\n\t", "!!! ??? ...", "'''"])
def test_une_saisie_sans_un_seul_mot_est_refusee(vide: str):
    """Ponctuation seule, apostrophes seules, espaces : il n'y a rien à router."""
    assert _executer(_state(EntryMode.CONVICTION, vide), _Corpus()).outcome is Outcome.REFUSE


def test_le_seuil_de_citation_est_inclusif():
    """Pile au seuil, on lit une citation — la borne penche vers l'interprétation la plus riche."""
    resultat = _executer(
        _state(EntryMode.CITATION, "aucune condamnation pour ceux qui sont en Jesus Christ"),
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
        _state(EntryMode.CONVICTION, PORTE_16, origine=EntryOrigin.DICTATED), _Corpus()
    )

    assert resultat.outcome is Outcome.AWAIT
    assert "J'ai entendu" in resultat.rationale
    assert PORTE_16 in resultat.rationale
    assert _codes(resultat) == [REFORMULER, "conviction"]


def test_la_meme_saisie_tapee_ne_demande_rien():
    """La provenance est la **seule** différence — et c'est tout l'intérêt de S36.

    Quelqu'un qui tape ces mots les a voulus ; quelqu'un dont le micro s'est ouvert, non."""
    resultat = _executer(
        _state(EntryMode.CONVICTION, PORTE_16, origine=EntryOrigin.TYPED), _Corpus()
    )

    assert resultat.outcome is Outcome.CONTINUE
    assert resultat.state.entry_mode is EntryMode.CONVICTION


def test_une_dictee_univoque_passe_sans_confirmation():
    """On ne fait pas confirmer une dictée nette : « Romains 8 » sorti d'un micro reste
    « Romains 8 ». La friction est réservée au doute."""
    resultat = _executer(
        _state(EntryMode.REFERENCE, "Romains 8", origine=EntryOrigin.DICTATED),
        _Corpus(livre="romains", code="Rom"),
    )

    assert resultat.outcome is Outcome.CONTINUE


def test_un_charabia_dicte_dit_que_le_micro_a_pu_se_declencher_seul():
    """Le motif change avec la provenance : accuser quelqu'un d'avoir mal tapé alors que son
    téléphone l'a trahi, c'est le laisser chercher au mauvais endroit."""
    resultat = _executer(
        _state(EntryMode.CONVICTION, "azkkq mlfjz", origine=EntryOrigin.DICTATED),
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
        _state(EntryMode.REFERENCE, PORTE_16, origine=EntryOrigin.DICTATED),
        # « ma » reconnu comme Malachie, et un seul mot du lexique : le pire cas plausible.
        _Corpus(livre="ma", code="Mal", connus={"paradis"}),
    )

    assert resultat.outcome is Outcome.AWAIT
    assert "J'ai entendu" in resultat.rationale
    assert REFORMULER in _codes(resultat)


# --- Le contrat du moteur, sur un étage réel --------------------------------------------------


def test_l_etage_ne_s_applique_qu_une_fois():
    etage = RouteEntry()
    vierge = _state(EntryMode.REFERENCE, "Romains 8")

    assert etage.applies(vierge)
    assert not etage.applies(vierge.with_(trace=(TraceEntry("route_entry", "déjà routé"),)))


def test_le_detecteur_est_deterministe():
    """Même saisie, même corpus ⇒ même sortie. Cent fois."""
    corpus = _Corpus()
    state = _state(EntryMode.REFERENCE, "l amour fraternel a disparu")

    sorties = {
        (r.outcome, r.rationale, tuple(_codes(r)))
        for r in (_executer(state, corpus) for _ in range(100))
    }

    assert len(sorties) == 1
