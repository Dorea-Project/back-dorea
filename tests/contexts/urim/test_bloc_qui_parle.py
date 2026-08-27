"""Le tour dit **de quoi il parle**, pour que le client sache quoi deplier.

Sans cette valeur, un client recoit des blocs sans hierarchie : il les deplie
tous, et le pasteur traverse onze ecrans dont neuf de matiere deja lue pour
atteindre son geste. Le serveur, lui, le savait — `_forme` le calcule pour
choisir la phrase, et le jetait ensuite.

Ces tests gardent l'accord entre les deux : **la phrase et le bloc deplie
parlent de la meme chose**. Le jour ou ils divergent, l'ecran annonce une chose
et en ouvre une autre.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.contexts.urim.interface.turn import (
    FORME_EPUISE,
    FORME_RIEN,
    construire_tour,
)


def _option(code, libelle, *, force=None, ecartee=False, origine="moteur"):
    return SimpleNamespace(
        code=code, label=libelle, rationale="motif", origin=origine,
        dismissed=ecartee, strength=force, signature=None, reference="",
    )


def _pesee(axe, force):
    return SimpleNamespace(
        axis_code=axe, label=axe.title(), strength=force, rationale="motif"
    )


def _vue(**kw):
    defauts = dict(
        trace=[SimpleNamespace(stage_code="weigh_conviction", rationale="motif")],
        options=[],
        bearings=[],
        caveats=[],
        couples=[],
        weighings=[],
        elements=[],
        theme=None,
        outcome="await_decision",
        rationale="le motif du moteur",
        resolved=None,
        axis_code=None,
        curation_reviewed_by=None,
    )
    return SimpleNamespace(**{**defauts, **kw})


def test_le_tour_nomme_le_bloc_dont_il_parle():
    tour = construire_tour(_vue(options=[_option("axe:x", "L'Église")]))

    assert tour.speaks == "chips"
    assert [b.kind for b in tour.blocks] == ["chips"]


def test_ce_qui_parle_n_est_pas_toujours_le_premier_bloc():
    """Le decor ambiant est en tete quand l'etage n'offre rien a choisir.

    Les pesees accompagnent tous les tours qui suivent l'etage qui les a
    produites ; quand plus rien n'est a choisir, c'est le bloc le plus **avance**
    qui dit ce qui vient d'arriver. Un client qui deplierait le premier ouvrirait
    du decor et replierait le sujet.
    """
    tour = construire_tour(_vue(
        bearings=[_pesee("christologie", "dominant")],
        theme="La communion comme pratique",
        outcome="continue",
    ))

    assert [b.kind for b in tour.blocks][0] == "bearings"
    assert tour.speaks == "theme"


def test_le_decor_ambiant_ne_parle_jamais_seul():
    """`actions` accompagne le theme, il ne le remplace pas."""
    tour = construire_tour(_vue(
        theme="Un thème",
        outcome="continue",
    ))

    assert "actions" in [b.kind for b in tour.blocks]
    assert tour.speaks == "theme"


def test_un_tour_sans_rien_a_montrer_le_dit():
    tour = construire_tour(_vue())

    assert tour.speaks == FORME_RIEN
    assert tour.blocks == []


def test_une_liste_entierement_ecartee_se_distingue_du_vide():
    """Deux formes differentes, et le client n'affiche pas la meme chose."""
    tour = construire_tour(_vue(
        options=[_option("axe:x", "L'Église", ecartee=True)],
    ))

    assert tour.speaks == FORME_EPUISE


def test_la_phrase_et_le_bloc_deplie_parlent_de_la_meme_chose():
    """La garde principale.

    `say` est choisi **par** la forme ; `speaks` est cette forme. Les deux ne
    peuvent donc pas diverger — sauf si quelqu'un recalcule l'une des deux
    ailleurs, et c'est exactement ce que ce test interdit.
    """
    cas = [
        _vue(options=[_option("axe:x", "L'Église")]),
        _vue(bearings=[_pesee("christologie", "dominant")], outcome="continue"),
        _vue(theme="Un thème", outcome="continue"),
        _vue(),
    ]

    for vue in cas:
        tour = construire_tour(vue)
        formes = {b.kind for b in tour.blocks} | {FORME_RIEN, FORME_EPUISE}
        assert tour.speaks in formes, tour.say


def test_une_phrase_de_repondeur_ne_change_pas_ce_qui_parle():
    """Le repondeur remplace `say`, **et rien d'autre**.

    Si `speaks` suivait la phrase soufflee, le client replierait le bloc dont le
    tour parle vraiment parce qu'un repondeur a pris la parole.
    """
    vue = _vue(options=[_option("axe:x", "L'Église")])

    sans = construire_tour(vue)
    avec = construire_tour(vue, say="Je ne sais pas conseiller sur les personnes.")

    assert avec.say != sans.say
    assert avec.speaks == sans.speaks == "chips"
