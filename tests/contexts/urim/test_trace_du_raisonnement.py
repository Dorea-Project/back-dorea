"""**« Comment j'en suis arrivé là »** — le parcours, avec ce que chaque étage tenait.

Le pipeline pèse à chaque étage et **n'en garde qu'un** : `StudyDTO.options` porte les
propositions de celui qui a rendu la main, les autres tombaient. Le pasteur voyait ce qu'Urim
conclut, jamais par où il est passé — et le libellé `blockTrace` existait côté application
depuis le sprint 4, sans donnée pour le remplir.

Trois interdits gouvernent ces tests :

- **le bloc voyage replié** — il est du décor, il ne peut jamais devenir le bloc qui parle ;
- **les écartées voyagent avec leur motif**, comme les couples refusés ;
- **rien d'inventé** — un étage qui n'a rien pesé rend une liste vide, pas une phrase pour
  meubler.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.contexts.urim.application.ports import StageWeighing, WeighedOption
from app.contexts.urim.application.study_service import _ce_que_chaque_etage_tenait
from app.contexts.urim.engine.pipeline import PIPELINE
from app.contexts.urim.interface.turn import construire_tour

from .test_study_service import AUTEUR, _ouvrir, _service
from .test_turn import _Vue

# ============================================================ 1. le parcours, de bout en bout


@pytest.mark.asyncio
async def test_les_etages_arrivent_dans_l_ordre_du_pipeline():
    """La trace dit *pourquoi*, les pesées disent *sur quoi* — et les deux marchent au pas.

    L'appariement n'est garanti par aucun champ : `StageResult` ne porte pas son code. Il
    tient à ce que `run()` pousse le résultat et le passage de trace dans la même itération,
    et ce test est ce qui le vérifie."""
    dto = await _ouvrir(_service(), "Hébreux 13:1")

    assert [w.stage_code for w in dto.weighings] == [c for c, _ in dto.trace]
    assert [w.rationale for w in dto.weighings] == [m for _, m in dto.trace]

    #: **Une sous-suite du pipeline**, jamais une permutation. Un étage peut ne pas
    #: s'appliquer — `applies()` le saute — mais aucun ne double celui qui le précède.
    ordre = [s.code for s in PIPELINE]
    joues = [w.stage_code for w in dto.weighings]
    assert [c for c in ordre if c in joues] == joues


@pytest.mark.asyncio
async def test_un_etage_qui_n_a_rien_pese_ne_meuble_pas():
    """Le motif de l'étage suffit. Une liste vide **est** la réponse honnête."""
    dto = await _ouvrir(_service(), "Hébreux 13:1")

    muets = [w for w in dto.weighings if not w.weighed]
    assert muets, "aucun étage silencieux : le cas n'est plus couvert"
    assert all(w.rationale for w in muets)


# ============================================================== 2. l'écartée garde son motif


@pytest.mark.asyncio
async def test_une_option_ecartee_reste_dans_le_parcours_avec_son_motif():
    """🔴 **La cacher laisserait croire qu'on n'y a pas pensé.**

    C'est la règle des couples refusés, appliquée au parcours : le pasteur doit pouvoir
    relire ce qu'Urim lui avait avancé — et voir qu'il l'a repoussé."""
    service = _service()
    dto = await _ouvrir(service, "Hébreux 13:1")
    etage = next(w for w in dto.weighings if w.weighed)
    proposee = etage.weighed[0]

    apres = await service.dismiss(
        actor_account_id=AUTEUR, study_id=dto.record.id,
        stage_code=etage.stage_code, option_code=proposee.code,
    )

    rejouee = next(
        o for w in apres.weighings if w.stage_code == etage.stage_code
        for o in w.weighed if o.code == proposee.code
    )
    assert rejouee.dismissed
    assert rejouee.rationale == proposee.rationale


def test_ecarter_a_un_etage_ne_dit_rien_de_l_autre():
    """Le filtre porte sur `(étage, code)`. La même option peut être offerte deux fois, et
    l'écarter ici ne l'écarte pas là — sinon un geste local en annulerait un distant."""
    tenu = SimpleNamespace(
        options=(SimpleNamespace(code="axe:x", label="L'Église", rationale="motif"),)
    )
    trace = (
        SimpleNamespace(stage_code="bear_axes", rationale="pesé"),
        SimpleNamespace(stage_code="shape_homiletic", rationale="mis en forme"),
    )

    ici, ailleurs = _ce_que_chaque_etage_tenait(
        trace, (tenu, tenu), [("bear_axes", "axe:x")]
    )

    assert ici.weighed[0].dismissed
    assert not ailleurs.weighed[0].dismissed


# ==================================================== 3. l'alignement, et le décalage d'un cran


def test_le_parcours_s_aligne_par_la_fin():
    """🔴 **Par le début, un rejeu décalerait chaque motif d'un cran.**

    La trace est un accumulateur. Le jour où un rejeu repartirait d'un état déjà tracé, un
    appariement depuis le début donnerait à chaque étage le motif de son prédécesseur — rien
    ne lèverait, et l'écran qui explique le raisonnement deviendrait celui qui le fausse."""
    trace = (
        SimpleNamespace(stage_code="un_tour_passe", rationale="déjà là"),
        SimpleNamespace(stage_code="route_entry", rationale="lu comme une référence"),
        SimpleNamespace(stage_code="resolve_passage", rationale="Hébreux 13:1"),
    )
    resultats = (
        SimpleNamespace(options=()),
        SimpleNamespace(options=()),
    )

    pesees = _ce_que_chaque_etage_tenait(trace, resultats, [])

    assert [w.stage_code for w in pesees] == ["route_entry", "resolve_passage"]
    assert pesees[0].rationale == "lu comme une référence"


def test_sans_etage_joue_il_n_y_a_pas_de_parcours():
    assert _ce_que_chaque_etage_tenait((), (), []) == ()


# ================================================================ 4. le bloc, replié, en fin


def _pesee(stage_code="bear_axes", **kw):
    return StageWeighing(
        stage_code=stage_code, rationale=kw.get("rationale", "ce que le texte porte"),
        weighed=kw.get("weighed", ()),
    )


def test_le_bloc_ferme_le_tour_et_ne_parle_jamais():
    """⚠️ **Le décor déplié à chaque tour est ce que D42 a corrigé** — onze écrans devenus
    trois. Un raisonnement qui s'impose enterre le geste ; il se consulte quand on le
    cherche."""
    tour = construire_tour(_Vue(weighings=[_pesee()]))

    assert tour.blocks[-1].kind == "trace"
    assert tour.speaks != "trace"


def test_le_bloc_rend_les_etages_et_leurs_ecartees():
    tour = construire_tour(_Vue(weighings=[
        _pesee("route_entry", rationale="lu comme une référence"),
        _pesee("bear_axes", weighed=(
            WeighedOption("axe:x", "L'Église", "en fait son sujet"),
            WeighedOption("axe:y", "Le salut", "le soutient", dismissed=True),
        )),
    ]))

    bloc = next(b for b in tour.blocks if b.kind == "trace")
    assert [e.stage_code for e in bloc.stages] == ["route_entry", "bear_axes"]
    assert bloc.stages[0].weighed == []
    ecartee = bloc.stages[1].weighed[1]
    assert ecartee.dismissed and ecartee.rationale == "le soutient"


def test_sans_pesee_le_bloc_n_apparait_pas():
    """Jamais un bloc vide — la règle de `_blocs`, et elle vaut aussi pour l'histoire."""
    assert all(b.kind != "trace" for b in construire_tour(_Vue()).blocks)
