"""**Le vestibule** — on n'entre pas en préparation sans avoir dit oui.

🔴 **Ce fichier existe à cause d'un téléphone.** Le 22/08/2026, un pasteur écrit « bonjour
Urim » : une préparation s'ouvre, le moteur descend, et rend 1 Corinthiens. Ce n'était pas un
accident — **écrire une phrase et ouvrir une préparation étaient le même geste**, et 150 lignes
vides en base le disaient depuis des semaines sans que personne les lise.

Trois propriétés, et la première est la seule qui compte vraiment :

- `confirme` ne s'écrit **que** sur un tour du pasteur — ni le modèle, ni un défaut, ni une
  saisie qui la souffle ;
- tant qu'il n'a pas dit oui, **aucun étage aval ne s'exécute** : ni détection, ni résolution,
  ni pesée ;
- sans modèle, le vestibule **s'efface** — il ne bloque pas. C'est la dégradation de la spec :
  *le pasteur perd de la finesse, jamais l'accès.*
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.contexts.urim.application.ports import LectureVestibule
from app.contexts.urim.calendar.domain.ports import NullEcclesialContext
from app.contexts.urim.engine import (
    EngineDeps,
    Maturite,
    Outcome,
    StudyState,
    UrimEngine,
)
from app.contexts.urim.engine.pipeline import PIPELINE
from app.contexts.urim.engine.stages.vestibule import (
    CHANGER,
    CONSENTIR,
    LIRE_SEULEMENT,
    RATTACHER,
    Vestibule,
)


class _Rien:
    """Le corpus n'est jamais consulté ici : le vestibule ne lit pas la saisie, il lit le
    consentement. Un double qui refuserait tout suffirait donc aussi bien."""

    def snapshot(self) -> str:
        return "corpus-2026-08"

    def ceiling_reached(self) -> bool:
        return False

    def find_reference_span(self, mots):
        return None

    def scripture_affinity(self, mots):
        return 0.0

    def known_words(self, mots):
        return len(mots)

    #: Le chemin inversé consulte la doctrine dès que la porte l'y envoie. Ce double n'a rien
    #: à dire : ce fichier éprouve **qui parle en premier**, pas ce qui se dit ensuite.
    def axes(self):
        return ()


def _deps() -> EngineDeps:
    return EngineDeps(
        corpus=_Rien(),
        doctrine=_Rien(),
        homiletics=_Rien(),
        context=NullEcclesialContext(),
        versions=_Rien(),
        clock=lambda: datetime(2026, 8, 22, tzinfo=UTC),
    )


def _state(**champs) -> StudyState:
    return StudyState(
        session_id=uuid4(),
        church_id=None,
        author_id=uuid4(),
        corpus_snapshot="corpus-2026-08",
        entry_mode=None,
        raw_input=champs.pop("raw_input", "bonjour Urim"),
        **champs,
    )


# --- L'étage seul ----------------------------------------------------------------------------


def test_sans_sujet_le_moteur_ne_descend_pas():
    """`absent` — il salue, il hésite, il parle d'autre chose. **Rien ne s'ouvre.**"""
    resultat = Vestibule().execute(_state(maturity=Maturite.ABSENT), _deps())

    assert resultat.outcome is Outcome.REFUSE
    assert resultat.rationale, "un refus sans motif serait un mur"


def test_un_theme_effleure_ne_declenche_aucune_proposition():
    """`pressenti` — *« la semaine a été dure »*. Proposer ici **forcerait la main**.

    C'est le scénario W4, et la retenue RT4 : on relance, on ne propose pas."""
    resultat = Vestibule().execute(
        _state(maturity=Maturite.PRESSENTI, carried_subject="la semaine a été dure"),
        _deps(),
    )

    assert resultat.outcome is Outcome.REFUSE
    assert not resultat.options, "une proposition sur un thème effleuré est un harcèlement poli"


def test_un_sujet_nomme_ouvre_deux_portes_et_n_en_franchit_aucune():
    """`nomme` — W1 : on **demande**, on n'ouvre pas.

    Les deux options ne sont pas symétriques et ne doivent pas l'être : préparer engage un
    travail, lire n'engage rien."""
    resultat = Vestibule().execute(
        _state(maturity=Maturite.NOMME, carried_subject="le pardon"), _deps()
    )

    assert resultat.outcome is Outcome.AWAIT
    assert [o.code for o in resultat.options] == [CONSENTIR, LIRE_SEULEMENT]


def test_le_consentement_efface_le_vestibule_pour_toujours():
    """⚠️ **Il ne se ré-applique jamais après.** Sans quoi chaque rejeu redemanderait son
    accord à quelqu'un qui l'a déjà donné — le défaut qu'`entry_mode` a connu, et qui reposait
    éternellement la même question."""
    assert not Vestibule().applies(_state(maturity=Maturite.CONFIRME))
    assert Vestibule().applies(_state(maturity=Maturite.NOMME))


def test_le_vestibule_ne_bloque_jamais_sur_une_parole_absente():
    """Pas de phrase du modèle — panne au milieu du tour. L'étage **rend quand même un motif**."""
    resultat = Vestibule().execute(
        _state(maturity=Maturite.ABSENT, vestibule_reply=None), _deps()
    )

    assert resultat.rationale.strip()


# --- Le pipeline entier ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "maturite", [Maturite.ABSENT, Maturite.PRESSENTI, Maturite.NOMME]
)
def test_aucun_etage_aval_ne_s_execute_avant_le_oui(maturite):
    """**I23, et il est mécanique.** Le vestibule est en tête du pipeline : tant qu'il n'a pas
    la main, rien derrière lui n'a la sienne.

    C'est ce que le défaut du 22/08 a rendu nécessaire : « bonjour Urim » traversait la porte,
    la résolution, le bornage et la pesée — quatre étages sur un salut."""
    run = UrimEngine(_deps(), pipeline=PIPELINE).run(
        _state(maturity=maturite, carried_subject="le pardon")
    )

    codes = [entree.stage_code for entree in run.state.trace]
    assert codes == ["vestibule"], "le pipeline s'arrête au vestibule"
    assert run.halted


def test_une_fois_confirme_le_moteur_descend_comme_avant():
    """Le consentement donné, le vestibule disparaît du chemin — et la porte d'entrée reprend
    son travail. Rien d'autre ne change : aucun étage aval ne sait qu'il a existé."""
    run = UrimEngine(_deps(), pipeline=PIPELINE).run(
        _state(maturity=Maturite.CONFIRME, raw_input="l amour fraternel a disparu")
    )

    codes = [entree.stage_code for entree in run.state.trace]
    assert "vestibule" not in codes
    assert codes[0] == "route_entry"


# --- Le contrat du modèle --------------------------------------------------------------------


def test_le_modele_ne_peut_pas_rendre_confirme():
    """🔴 **I26 — l'invariant qui rend l'ouverture inatteignable par une phrase.**

    Un modèle qui écrirait `confirme` — parce qu'il a mal lu, parce qu'une saisie le lui a
    soufflé — verrait sa valeur ramenée à `absent` par la validation de l'adaptateur. On le
    vérifie ici sur le vocabulaire lui-même : `confirme` n'est pas dans ce que le modèle peut
    rendre."""
    assert Maturite.CONFIRME not in Maturite.DU_MODELE
    assert Maturite.DU_MODELE < Maturite.TOUTES


def test_une_lecture_ne_propose_jamais_depuis_un_theme_effleure():
    """RT4 tenue par le **type**, pas par la consigne : le défaut de `propose_preparation` est
    faux, et l'adaptateur le force à faux hors de `nomme`."""
    lecture = LectureVestibule(maturite=Maturite.PRESSENTI, sujet="la semaine dure")

    assert lecture.propose_preparation is False


# --- La retenue, et la suspension (lot 5) ----------------------------------------------------


def test_un_sujet_decline_ne_revient_jamais():
    """**RT1.** La pente d'un modèle est d'être serviable tout de suite : s'il peut proposer, il
    proposera à chaque tour, et la conversation devient un harcèlement poli."""
    resultat = Vestibule().execute(
        _state(
            maturity=Maturite.NOMME,
            carried_subject="le pardon",
            declined_subjects=("le pardon",),
        ),
        _deps(),
    )

    assert resultat.outcome is Outcome.REFUSE
    assert not resultat.options


def test_la_retenue_ne_se_contourne_pas_par_une_majuscule():
    """La comparaison est normalisée — sinon « Le Pardon » revient après « le pardon »."""
    resultat = Vestibule().execute(
        _state(
            maturity=Maturite.NOMME,
            carried_subject="Le Pardon",
            declined_subjects=("le pardon",),
        ),
        _deps(),
    )

    assert not resultat.options


def test_un_autre_candidat_peut_toujours_murir():
    """RT1 ferme **un sujet**, pas la conversation. Sans quoi un refus deviendrait un mur."""
    resultat = Vestibule().execute(
        _state(
            maturity=Maturite.NOMME,
            carried_subject="la persévérance",
            declined_subjects=("le pardon",),
        ),
        _deps(),
    )

    assert resultat.outcome is Outcome.AWAIT
    assert [o.code for o in resultat.options] == [CONSENTIR, LIRE_SEULEMENT]


def test_un_nouveau_sujet_sur_un_travail_commence_suspend_au_lieu_de_fondre():
    """**§4 — le défaut le plus sournois du fil.**

    Une fois un sujet en mémoire, tout ce qui arrive est lu *à travers lui* : le pasteur envoie
    Luc 15 alors qu'il travaillait sur le pardon, et l'agent lui répond sur le pardon. Il répond
    avec ce qu'il a gardé, **pas à la préoccupation du tour**.

    La question posée n'est donc plus celle de l'ouverture : ce n'est pas *« voulez-vous
    préparer ? »*, c'est *« lequel des deux ? »*."""
    resultat = Vestibule().execute(
        _state(
            maturity=Maturite.NOMME,
            carried_subject="Luc 15:11-32",
            theme="le pardon",
        ),
        _deps(),
    )

    assert resultat.outcome is Outcome.AWAIT
    assert [o.code for o in resultat.options] == [CHANGER, RATTACHER]
    assert "le pardon" in resultat.rationale, "on nomme ce qu'il risque de perdre"


def test_sans_travail_commence_un_nouveau_sujet_n_est_pas_une_suspension():
    """Interrompre une conversation qui n'a rien engagé serait du zèle : c'est simplement la
    suite du fil, et la question redevient celle de l'ouverture."""
    resultat = Vestibule().execute(
        _state(maturity=Maturite.NOMME, carried_subject="Luc 15:11-32"), _deps()
    )

    assert [o.code for o in resultat.options] == [CONSENTIR, LIRE_SEULEMENT]


# --- Aucune branche du vestibule ne se termine par un mur ------------------------------------


def _tour_du_vestibule(resultat, relance=None):
    """La vue telle que le client la reçoit, pour la soumettre au détecteur du banc.

    `_Vue` est celle des tests de tour : une vue complète avec ses défauts vides, ce qui est
    exactement l'état d'un tour de vestibule — rien de résolu, rien de pesé, rien à montrer."""
    from app.contexts.urim.interface.turn import construire_tour

    from .test_turn import _Option, _Trace, _Vue

    vue = _Vue(
        trace=[_Trace("vestibule")],
        outcome="await_decision" if resultat.outcome is Outcome.AWAIT else "refuse",
        # Les options du moteur deviennent celles de la vue — c'est ce que le
        # service fait, et le détecteur ne juge que ce que le client reçoit.
        options=[_Option(o.code) for o in resultat.options],
        rationale=resultat.rationale,
    )
    return construire_tour(vue, relance=relance)


@pytest.mark.parametrize(
    "maturite", [Maturite.ABSENT, Maturite.PRESSENTI, Maturite.NOMME]
)
def test_aucun_tour_du_vestibule_n_est_un_mur(maturite):
    """🔴 **Le banc a rattrapé une erreur que les tests n'ont pas vue.**

    En repliant le vestibule sur une seule voix, j'avais vidé `ask` — et un `expects: text`
    sans passerelle nommée est exactement ce que `mur()` refuse : *« barre ouverte, mais aucune
    passerelle nommée »*. Les 813 tests passaient : leurs vues datent d'avant cet étage.

    C'est la forme sous laquelle un mur survit à une relecture de code, parce que la structure
    a l'air correcte."""
    from scripts.urim_banc_arbre import mur

    resultat = Vestibule().execute(
        _state(maturity=maturite, carried_subject="le pardon"), _deps()
    )

    assert mur(_tour_du_vestibule(resultat)) is None


def test_la_parole_du_modele_devient_la_relance_quand_il_en_pose_une():
    """Une seule voix, deux rôles : l'une accueille, l'autre ouvre. Elles voyagent séparées
    parce que le détecteur ne sait pas lire à l'intérieur d'une phrase."""
    resultat = Vestibule().execute(
        _state(maturity=Maturite.ABSENT, vestibule_reply="Bonjour."), _deps()
    )
    tour = _tour_du_vestibule(resultat, relance="De quoi partons-nous ?")

    assert tour.say == "Bonjour."
    assert tour.ask == "De quoi partons-nous ?"
    assert not tour.why, "le motif EST la parole ici — le répéter en gris ferait deux voix"
