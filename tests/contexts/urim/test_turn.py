"""Le tour — **les garanties du contrat**, pas la forme d'une phrase.

`docs/Urim_Conversation.md` §5 énumère cinq choses qu'aucun client ne peut casser. Ce banc les
tient côté serveur, puisque c'est là qu'elles se décident : *le serveur rend le tour, le client
rend des blocs.*
"""

from __future__ import annotations

import pytest

from app.contexts.urim.interface.turn import TurnView, construire_tour


class _Trace:
    def __init__(self, code: str) -> None:
        self.stage_code = code
        self.rationale = "motif d'étage"


class _Option:
    def __init__(self, code: str, dismissed: bool = False) -> None:
        self.code = code
        self.label = f"libellé {code}"
        self.rationale = "parce que ce texte traite le sujet"
        self.origin = "locus"
        self.dismissed = dismissed


class _Vue:
    """Le strict nécessaire — le constructeur ne lit rien d'autre, et c'est le sujet."""

    def __init__(self, **remplace) -> None:
        self.trace = [_Trace("weigh_conviction")]
        self.outcome = "await_decision"
        self.rationale = "Ni nom de livre, ni phrase des Écritures."
        self.options = [_Option("axe:ecclesiologie")]
        self.bearings = []
        self.caveats = []
        self.couples = []
        self.theme = None
        self.curation_reviewed_by = None
        for cle, valeur in remplace.items():
            setattr(self, cle, valeur)


def test_le_motif_du_moteur_traverse_intact() -> None:
    """🔴 **`why` n'est jamais réécrit — c'est le filet doré.**

    Un tour sans motif serait une conclusion sans provenance : la seule chose qu'Urim
    s'interdit. Et un motif reformulé serait pire, parce qu'il aurait l'air d'un motif."""
    vue = _Vue(rationale="Un motif très précis venu de l'étage.")
    assert construire_tour(vue).why == "Un motif très précis venu de l'étage."


@pytest.mark.parametrize(
    "etage",
    [
        "route_entry", "weigh_conviction", "resolve_passage", "bound_pericope",
        "bear_axes", "shape_homiletic", "propose_theme", "serve_corpus",
    ],
)
def test_chaque_etage_a_sa_phrase_et_aucune_n_est_vide(etage: str) -> None:
    tour = construire_tour(_Vue(trace=[_Trace(etage)]))
    assert tour.say.strip()
    assert tour.why.strip()


def test_un_etage_inconnu_degrade_au_lieu_de_planter() -> None:
    """Un étage ajouté demain ne doit pas faire tomber la conversation."""
    tour = construire_tour(_Vue(trace=[_Trace("etage_de_demain")]))
    assert tour.say.strip()
    assert tour.stage_code == "etage_de_demain"


def test_la_question_ne_se_pose_que_si_le_moteur_attend() -> None:
    """⚠️ Une question sans attente ferait répondre le pasteur à un tour déjà passé."""
    attend = construire_tour(_Vue(outcome="await_decision"))
    continue_ = construire_tour(_Vue(outcome="continue"))
    assert attend.ask and attend.expects == "choice"
    assert not continue_.ask
    assert continue_.expects == "text"


def test_le_refus_laisse_la_barre_de_saisie_ouverte() -> None:
    """Un refus est une issue, pas une panne : le pasteur peut reformuler."""
    tour = construire_tour(_Vue(outcome="refuse"))
    assert tour.expects == "text"


def test_les_options_ecartees_ne_reviennent_pas_dans_les_pastilles() -> None:
    """Elles restent dans `options` — reléguées — mais on ne les repropose pas au toucher."""
    vue = _Vue(options=[_Option("a"), _Option("b", dismissed=True)])
    pastilles = construire_tour(vue).blocks[0]
    assert [i.code for i in pastilles.items] == ["a"]


def test_l_origine_ne_se_perd_pas() -> None:
    """§5.3 — deux options côte à côte ne valent pas la même chose."""
    pastilles = construire_tour(_Vue()).blocks[0]
    assert pastilles.items[0].origin == "locus"


def test_la_signature_est_portee_jusqu_au_tour() -> None:
    """§5.4 — *pour que rien de généré ne se confonde avec une relecture.*"""
    assert construire_tour(_Vue(curation_reviewed_by="ia-mistral")).signature == "ia-mistral"


def test_le_bornage_porte_sa_consequence() -> None:
    """Elle n'est pas optionnelle à l'affichage — d'où un `kind` distinct des pastilles."""
    bloc = construire_tour(_Vue(trace=[_Trace("bound_pericope")])).blocks[0]
    assert bloc.kind == "bounds"
    assert "proof-texting" in bloc.consequence


def test_un_bouton_grise_porte_toujours_son_motif() -> None:
    """⚠️ Un bouton grisé muet est un mensonge poli."""
    tour = construire_tour(_Vue(theme="L'amour sans masque", trace=[_Trace("propose_theme")]))
    actions = next(b for b in tour.blocks if b.kind == "actions")
    for bouton in actions.items:
        assert bouton.enabled or bouton.unavailable_reason.strip()


def test_aucun_bloc_vide_n_est_emis() -> None:
    """Un bloc sans contenu ferait afficher un titre au-dessus de rien."""
    tour = construire_tour(_Vue(options=[]))
    assert all(
        getattr(b, "items", None) or getattr(b, "groups", None) or getattr(b, "body", None)
        for b in tour.blocks
    )


def test_le_tour_est_serialisable_tel_quel() -> None:
    """Il part sur le fil : les blocs typés doivent survivre au passage en JSON."""
    tour = construire_tour(_Vue(theme="Un thème", trace=[_Trace("propose_theme")]))
    rendu = TurnView.model_validate(tour.model_dump()).model_dump()
    assert {b["kind"] for b in rendu["blocks"]} == {"theme", "actions", "chips"}
