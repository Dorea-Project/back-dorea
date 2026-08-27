"""**D55 — le moteur tranche, et il dit pourquoi.**

L'étage 6 proposait trois couples `plan x matière` avec, pour tout motif, un niveau de risque :
« faible », « moyen », « élevé ». Le fondateur l'a vu sur un téléphone — *« il ne faut pas
donner du boulot en supplément »*. Trois défauts en un écran :

- **du vocabulaire d'exégète**, pas de prédicateur : un pasteur ne choisit pas entre
  « textuel » et « thématique », il veut un plan ;
- **un adjectif sans motif** : les couples *écartés* étaient argumentés, les couples *retenus*
  ne l'étaient pas. On expliquait pourquoi on refuse, jamais pourquoi on accepte ;
- **le travail reporté** sur lui au moment où il vient chercher de l'aide.

Deux interdits gouvernent la correction, et ils tirent en sens contraire :

> *Un plan retenu sans son motif est un oracle* — trancher sans dire pourquoi trahit le filet
> doré plus gravement que l'ancien écran.

> *Le moteur n'écrit jamais une division à la place du pasteur* — il retient une **mise en
> forme**, ce qui n'est pas un plan.
"""

from __future__ import annotations

import pytest

from app.contexts.urim.domain.libelles import RISQUES as _EN_CLAIR
from app.contexts.urim.engine.deps import Feasibility
from app.contexts.urim.engine.outcomes import Outcome
from app.contexts.urim.engine.stages.shape_homiletic import (
    ShapeHomiletic,
    couple_propose,
)
from app.contexts.urim.interface.schemas import StudyView
from app.contexts.urim.interface.turn import construire_tour

from .test_shape_and_theme import _deps, _Homiletique, _state
from .test_study_service import _PESEES, _index, _ouvrir, _service

FAIBLE = Feasibility("textuel", "doctrinal", True, "", "faible")
MOYEN = Feasibility("expositif", "doctrinal", True, "", "moyen")
ELEVE = Feasibility("thematique", "ethique", True, "", "eleve")
REFUSE = Feasibility(
    "textuel", "biographique", False, "ce passage ne porte aucun personnage", "faible"
)


async def _jusqu_a_la_forme(couples):
    """Une préparation menée jusqu'à ce que la mise en forme soit retenue."""
    service = _service(index=_index(bearings=_PESEES, couples=couples))
    dto = await _ouvrir(service, "Hébreux 13:1-2")
    return await service.decide(
        actor_account_id=dto.record.author_id, study_id=dto.record.id,
        stage_code="bear_axes", option_code="anthropologie",
    )


def _faisabilite(dto):
    return next(
        b for b in construire_tour(StudyView.from_dto(dto)).blocks
        if b.kind == "feasibility"
    )


# ================================================================= 1. ce que le moteur retient


def test_le_moteur_retient_le_faisable_qui_expose_le_moins():
    assert couple_propose([ELEVE, FAIBLE, MOYEN]) is FAIBLE


def test_a_risque_egal_le_depart_se_fait_par_le_nom():
    """Sans départage, l'ordre du corpus déciderait — et le motif deviendrait faux au premier
    ressemis, sans que rien ne lève."""
    a = Feasibility("expositif", "doctrinal", True, "", "faible")
    b = Feasibility("textuel", "doctrinal", True, "", "faible")

    assert couple_propose([b, a]) is a
    assert couple_propose([a, b]) is a


def test_un_risque_hors_echelle_passe_en_dernier():
    """On ne classe pas ce qu'on ne comprend pas devant ce qu'on a relu."""
    inconnu = Feasibility("textuel", "doctrinal", True, "", "colossal")

    assert couple_propose([inconnu, ELEVE]) is ELEVE


def test_les_drapeaux_de_charge_ne_choisissent_jamais():
    """🔴 **La propriété de sûreté de S26 et S37, et elle se perdrait sans bruit.**

    Un drapeau relève la vigilance d'un cran, uniformément. Le faire peser sur le choix lui
    donnerait le pouvoir de *choisir un texte* — exactement ce qu'on refuse à un signal qui
    peut se tromper. `couple_propose` ne reçoit donc pas les drapeaux : ils n'ont aucune porte
    d'entrée ici, et il n'y a rien à oublier de débrancher."""
    homiletique = _Homiletique([MOYEN, FAIBLE])

    avec = ShapeHomiletic().execute(
        _state(risk_flags=("intention_persuasive", "charge")),
        _deps(homiletics=homiletique),
    )
    sans = ShapeHomiletic().execute(_state(), _deps(homiletics=homiletique))

    assert avec.state.plan_source == sans.state.plan_source == "textuel"


# ==================================================================== 2. le motif, toujours


@pytest.mark.parametrize(
    "couples",
    [[FAIBLE], [FAIBLE, MOYEN], [FAIBLE, REFUSE], [MOYEN, ELEVE]],
    ids=["seule", "deux", "avec-un-refus", "aucune-faible"],
)
def test_aucun_plan_retenu_ne_sort_sans_motif(couples):
    """*Un plan retenu sans son motif est un oracle.* Le filet doré n'a pas d'exception."""
    resultat = ShapeHomiletic().execute(_state(), _deps(homiletics=_Homiletique(couples)))

    assert resultat.outcome is Outcome.CONTINUE
    assert resultat.state.plan_source
    assert "Plan retenu" in resultat.rationale
    assert any(clair in resultat.rationale.lower() for clair in _EN_CLAIR.values()), (
        f"le risque ne se dit pas : {resultat.rationale}"
    )


def test_le_motif_parle_predicateur_et_non_schema():
    """Un pasteur ne choisit pas entre « textuel » et « thématique », il veut un plan."""
    resultat = ShapeHomiletic().execute(
        _state(), _deps(homiletics=_Homiletique([FAIBLE, MOYEN]))
    )

    assert "un plan collé au texte sur une doctrine" in resultat.rationale
    assert "textuel x doctrinal" not in resultat.rationale


def test_le_depart_alphabetique_ne_passe_pas_pour_un_jugement():
    """Deux couples exposent aussi peu : le dire est la seule façon honnête de trancher entre
    eux — sinon un tri par nom se lit comme une préférence."""
    ex_aequo = Feasibility("expositif", "doctrinal", True, "", "faible")

    resultat = ShapeHomiletic().execute(
        _state(), _deps(homiletics=_Homiletique([FAIBLE, ex_aequo]))
    )

    assert "exposent aussi peu" in resultat.rationale


# =========================================================== 3. l'écran : une seule question


@pytest.mark.asyncio
async def test_le_tour_rend_un_plan_son_motif_et_une_seule_question():
    bloc = _faisabilite(await _jusqu_a_la_forme((MOYEN, FAIBLE, REFUSE)))

    #: Un plan retenu, dit en français.
    (retenu,) = [i for i in bloc.items if i.selected]
    assert retenu.label == "un plan collé au texte sur une doctrine"
    #: Son motif, **à côté de lui** — pas seulement dans la trace.
    assert "expose le moins" in bloc.rationale
    #: Et une seule question, qui n'est plus « lequel voulez-vous suivre ? ».
    assert bloc.heading == "Vous changez quoi ?"


@pytest.mark.asyncio
async def test_le_motif_du_bloc_ne_redit_pas_les_ecartees():
    """Elles sont déjà là, chacune avec la sienne. Les recoller en paragraphe est la
    répétition que D42 a chassée — onze écrans, dont neuf de matière déjà lue."""
    bloc = _faisabilite(await _jusqu_a_la_forme((FAIBLE, REFUSE)))

    assert "Écartées" not in bloc.rationale
    ecartee = next(i for i in bloc.items if not i.feasible)
    assert ecartee.rationale == "ce passage ne porte aucun personnage"
    assert not ecartee.selectable, "un refusé ne se prend pas"


@pytest.mark.asyncio
async def test_sans_rien_a_changer_aucune_question_n_est_posee():
    """**Un écran qui pose une question sur zéro geste possible est le mur qu'on a déjà
    corrigé une fois** — `expects: choice` sur zéro pastille."""
    bloc = _faisabilite(await _jusqu_a_la_forme((FAIBLE,)))

    assert bloc.heading == ""
    assert not any(i.selectable for i in bloc.items), "la retenue s'offrirait elle-même"
