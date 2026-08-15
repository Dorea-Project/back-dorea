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
    def __init__(
        self,
        code: str,
        dismissed: bool = False,
        strength: str | None = None,
        signature: str | None = None,
    ) -> None:
        self.code = code
        self.label = f"libellé {code}"
        self.rationale = "parce que ce texte traite le sujet"
        self.origin = "locus"
        self.dismissed = dismissed
        self.strength = strength
        #: Qui a écrit le **libellé** — `None` = le corpus, `ia-mistral` = une glose.
        self.signature = signature


class _Pesee:
    def __init__(self, code: str, force: str) -> None:
        self.axis_code = code
        self.label = code.capitalize()
        self.strength = force
        self.rationale = "ce que le texte en fait"


class _Vue:
    """Le strict nécessaire — le constructeur ne lit rien d'autre, et c'est le sujet."""

    def __init__(self, **remplace) -> None:
        self.trace = [_Trace("weigh_conviction")]
        self.outcome = "await_decision"
        self.rationale = "Ni nom de livre, ni phrase des Écritures."
        self.options = [_Option("axe:ecclesiologie")]
        #: Où en est la préparation — lu par les deux tours qui n'offrent rien, pour situer.
        self.resolved = None
        #: L'axe retenu — le bloc des pesées marque le sien et rend les autres sélectionnables.
        self.axis_code = None
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


def test_l_ecran_d_une_correction_ne_parle_pas_des_textes_a_egalite() -> None:
    """🔴 Le mur n°2, en plus petit — et il repointe partout où un écran est neuf.

    Une correction est une pastille comme les autres, donc elle héritait de la phrase de
    l'étage : *« Plusieurs textes portent cette formulation — aucun ne s'impose seul »*
    au-dessus d'une seule proposition, qui ne porte aucune formulation. La forme suit ce dont
    l'écran parle, pas le bloc qui l'affiche."""
    vue = _Vue(trace=[_Trace("resolve_passage")], options=[_Option("Hébreux 2:9")])
    vue.options[0].origin = "correction"

    tour = construire_tour(vue)

    assert "Plusieurs textes" not in tour.say
    assert "proche de ce que vous avez écrit" in tour.say
    assert tour.ask == "Est-ce celle-là ?"


def test_un_libelle_habille_par_le_modele_porte_sa_signature() -> None:
    """🔴 **Sept libellés du corpus et trois du modèle, indiscernables.**

    Sur l'écran des dix loci, le pasteur lit *« voici les dix axes de la dogmatique »* — et
    l'un d'eux s'appelle « L'effusion obligatoire », c'est-à-dire sa propre thèse sous
    l'apparence d'une catégorie du corpus. `origin` valait `locus` pour les dix.

    Mesuré avant d'être corrigé : le modèle **fait écho** à la saisie, il n'invente aucune
    thèse. Ce n'est donc pas la formulation qu'on change — cet écran doit parler la langue du
    pasteur — c'est qu'on dit **lequel est habillé**. §5.4, là où il manquait."""
    vue = _Vue(options=[
        _Option("axe:pneumatologie", signature="ia-mistral"),
        _Option("axe:angelologie"),
    ])

    habille, brut = construire_tour(vue).blocks[0].items

    assert habille.signature == "ia-mistral"
    assert brut.signature is None, "un libellé du corpus ne se signe pas"


def test_la_signature_du_libelle_ne_dit_rien_de_la_provenance_de_l_option() -> None:
    """⚠️ Les deux champs répondent à deux questions, et les confondre dirait faux.

    `origin` : d'où vient la **proposition** — les dix loci viennent tous de la dogmatique.
    `signature` : qui a écrit le **libellé**. Un client qui lirait la signature comme une
    origine annoncerait au pasteur que l'axe lui-même est généré."""
    vue = _Vue(options=[_Option("axe:pneumatologie", signature="ia-mistral")])

    (pastille,) = construire_tour(vue).blocks[0].items

    assert pastille.origin == "locus"
    assert pastille.signature == "ia-mistral"


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


# -- l'axe retenu n'est pas une fatalité du texte (§7) --------------------------------


def _avec_pesees(**remplace) -> _Vue:
    return _Vue(
        trace=[_Trace("bear_axes")], outcome="degrade", options=[],
        bearings=[
            _Pesee("christologie", "dominant"),
            _Pesee("anthropologie", "porte"),
            _Pesee("eschatologie", "resiste"),
            _Pesee("demonologie", "absent"),
        ],
        **remplace,
    )


def _pesees(vue) -> dict[str, object]:
    bloc = next(b for b in construire_tour(vue).blocks if b.kind == "bearings")
    return {i.axis_code: i for i in bloc.items}


def test_l_axe_retenu_est_marque_et_les_autres_axes_portes_sont_prenables() -> None:
    """🔴 **Un texte à un seul dominant voyait son axe posé d'office, sans le dire.**

    Le pasteur orthodoxe ouvre 2 Pierre 1:4 *pour* la déification ; l'unité n'a que
    `christologie` en dominant, donc `bear_axes` continue sans rendre la main. Il repartait avec
    une préparation christologique — et l'unité porte pourtant l'anthropologie.

    Le geste existait déjà de bout en bout côté API. **Rien ne le disait**, et une porte ouverte
    que personne ne voit a l'air d'une fonctionnalité manquante."""
    vue = _avec_pesees()
    vue.axis_code = "christologie"

    items = _pesees(vue)

    assert items["christologie"].selected
    assert not items["christologie"].selectable, "reprendre l'axe déjà retenu ne fait rien"
    assert items["anthropologie"].selectable


def test_un_axe_absent_ou_resistant_n_est_jamais_prenable() -> None:
    """*Un axe absent n'affiche rien, et aucun plan ne se construit dessus.* Et un axe auquel le
    texte **résiste** est un garde-fou, pas un angle : c'est le même partage que `bear_axes`,
    qui offre les dominants, sinon les portants, et jamais les résistants."""
    vue = _avec_pesees()
    vue.axis_code = "christologie"

    items = _pesees(vue)

    assert not items["demonologie"].selectable
    assert not items["eschatologie"].selectable


def test_le_bloc_des_pesees_dit_a_quel_etage_poster() -> None:
    """⚠️ Le tour porte le code de l'étage **courant**, qui n'est pas celui-ci.

    Le cas est celui du dernier tour : les pesées y voyagent en décor, le tour dit
    `propose_theme`, et le geste qu'elles portent s'adresse à `bear_axes`. Sans `decide_stage`,
    un client les enverrait à l'étage qui vient de parler et se ferait refuser — le 422 au clic,
    dans l'autre sens."""
    vue = _avec_pesees()
    vue.trace = [_Trace("propose_theme")]
    vue.theme = "Un thème proposé"
    vue.axis_code = "christologie"

    tour = construire_tour(vue)

    bloc = next(b for b in tour.blocks if b.kind == "bearings")
    assert bloc.decide_stage == "bear_axes"
    assert tour.stage_code == "propose_theme", "le tour ne parle pas de l'étage des pesées"


def test_le_tour_des_pesees_nomme_le_geste_qu_il_rend_possible() -> None:
    """Le bloc porte l'affordance ; la phrase doit la dire, sinon elle reste invisible."""
    vue = _avec_pesees()
    vue.axis_code = "christologie"

    assert "axes" in construire_tour(vue).ask


# -- la dominance : le trou 1 du contrat ---------------------------------------------


def test_les_unites_sont_groupees_par_ce_qu_elles_font_du_sujet() -> None:
    """🔴 **Le trou 1, et il est bouché par une donnée qui existait déjà.**

    `sites_for_axis` portait la force depuis le premier jour — elle voyageait *collée dans le
    libellé* : « La charité sans hypocrisie — en fait son sujet ». Le client qui veut séparer
    les groupes devait donc lire le texte du libellé, ce qui marche jusqu'au jour où la
    formulation change."""
    vue = _Vue(options=[
        _Option("texte:a", strength="dominant"),
        _Option("texte:b", strength="porte"),
        _Option("texte:c", strength="resiste"),
    ])
    bloc = construire_tour(vue).blocks[0]
    assert bloc.kind == "units"
    assert [g.role for g in bloc.groups] == ["dominant", "porte", "resiste"]


def test_le_texte_qui_resiste_a_son_groupe() -> None:
    """C'est la seule mécanique anti-proof-texting du produit : elle s'affiche au même rang."""
    vue = _Vue(options=[_Option("texte:c", strength="resiste")])
    groupes = construire_tour(vue).blocks[0].groups
    assert [g.role for g in groupes] == ["resiste"]


def test_un_groupe_vide_n_est_pas_emis() -> None:
    vue = _Vue(options=[_Option("texte:a", strength="dominant")])
    assert len(construire_tour(vue).blocks[0].groups) == 1


def test_les_options_non_pesees_restent_des_pastilles() -> None:
    """⚠️ « Allez droit à un texte » n'a rien de relu — le mêler aux unités le laisserait croire."""
    vue = _Vue(options=[
        _Option("texte:a", strength="dominant"),
        _Option("Hébreux 13:1-2"),
    ])
    blocs = construire_tour(vue).blocks
    assert [b.kind for b in blocs[:2]] == ["units", "chips"]
    assert [i.code for i in blocs[1].items] == ["Hébreux 13:1-2"]
