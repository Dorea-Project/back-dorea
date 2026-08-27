"""**Le thème lisible, et le gabarit qu'on n'a pas touché.**

Le thème s'affichait `theologie_propre, en textuel doctrinal` : du vocabulaire de schéma,
montré à un prédicateur. Le corriger était petit — le piège était de le corriger **au bon
endroit**.

🔴 `theme_propose` est une **empreinte**. Le moteur compare le thème enregistré à ce que le
gabarit rendrait pour savoir si le pasteur l'a réécrit. Le rendre lisible ferait cesser de
correspondre *tous les thèmes déjà en base*, et le système conclurait que chaque pasteur a
réécrit le sien — **sans lever la moindre erreur**. C'est la régression que ces tests
attrapent : le premier fige le gabarit au caractère près, les autres prouvent qu'on a bien
ajouté à côté."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from app.contexts.urim.engine.stages.propose_theme import theme_propose
from app.contexts.urim.interface.schemas import StudySummaryView, theme_en_clair


@dataclass
class _Prep:
    theme: str | None
    axis_code: str | None = None
    plan_source: str | None = None
    subject_matter: str | None = None


def test_le_gabarit_ne_bouge_pas_dun_caractere():
    """L'empreinte est un contrat avec **la base**, pas un choix de présentation.

    Ce test n'a l'air de rien tant qu'on n'a pas compris qu'il tient à lui seul la lisibilité
    de tous les thèmes déjà enregistrés."""
    assert theme_propose("theologie_propre", "textuel", "doctrinal") == (
        "theologie_propre, en textuel doctrinal"
    )
    assert theme_propose("christologie", None, None) == "christologie"


def test_reecrire_le_libelle_ne_change_pas_lempreinte():
    """Le test que la note d'atterrissage demandait, mot pour mot."""
    prep = _Prep("theologie_propre, en textuel doctrinal", "theologie_propre", "textuel",
                 "doctrinal")

    assert prep.theme == theme_propose(prep.axis_code, prep.plan_source, prep.subject_matter)
    assert theme_en_clair(prep) == "Dieu lui-même — un plan collé au texte sur une doctrine"
    #: Et après lecture, l'empreinte est toujours celle que le moteur reconnaît.
    assert prep.theme == theme_propose(prep.axis_code, prep.plan_source, prep.subject_matter)


def test_une_phrase_du_pasteur_nest_pas_recouverte():
    """Un thème qui ne correspond plus au gabarit est **déjà** une phrase d'homme.

    Lui coller un libellé de schéma par-dessus effacerait à l'écran ce qu'il a écrit — la
    même faute que celle qu'on répare, dans l'autre sens."""
    sien = _Prep("La réclamation du corps de Moïse", "theologie_propre", "textuel", "doctrinal")

    assert theme_en_clair(sien) is None


def test_un_axe_sans_forme_se_dit_quand_meme():
    """L'étage 6 n'est pas toujours passé. Un demi-thème se dit, il ne se tait pas."""
    assert theme_en_clair(_Prep("christologie", "christologie")) == "Jésus-Christ"


def test_sans_theme_il_ny_a_rien_a_dire():
    assert theme_en_clair(_Prep(None, "christologie", "textuel", "doctrinal")) is None


def test_le_fil_montre_le_theme_en_clair():
    """La carte d'accueil est **l'endroit où le pasteur le lit le plus souvent** — c'est là
    que le vocabulaire de schéma se voyait."""
    @dataclass
    class _Record:
        id = uuid4()
        raw_input = "Jean 3"
        title = None
        theme = "soteriologie, en expositif doctrinal"
        axis_code = "soteriologie"
        plan_source = "expositif"
        subject_matter = "doctrinal"
        service_date = None
        status = "ouverte"
        last_outcome = None
        last_stage_code = None
        last_turn_at = None
        opened_at = None

    vue = StudySummaryView.from_record(_Record())

    assert vue.theme == "soteriologie, en expositif doctrinal"
    assert vue.theme_label == "le salut — un plan verset par verset sur une doctrine"


def test_un_code_inconnu_saffiche_plutot_que_de_disparaitre():
    """Mieux vaut un mot technique qu'un trou dans la note de quelqu'un."""
    assert theme_en_clair(_Prep("mariologie", "mariologie")) == "mariologie"
