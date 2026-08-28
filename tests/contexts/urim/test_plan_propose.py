"""**D55, seconde moitié — le plan qu'Urim propose, à côté du sien.**

Le fondateur l'a demandé dans ces termes : *« avant de générer le document, il faut proposer
le plan, le titre, avec les versets qui soutiennent chaque point ; ça peut être un sujet à
discussion, le user aussi peut corriger »*.

C'est la proposition la plus utile d'Urim et la plus dangereuse. Tous les autres blocs
montrent ce que le **corpus** porte — des pesées relues, des couples curés, des versets
servis. Celui-ci montre ce qu'un **modèle** a écrit.

Trois choses le rendent acceptable, et ce fichier ne teste qu'elles :

> **Le verrou** — le livrable n'imprime que `preparation_element`. La proposition vit dans sa
> propre table et n'atteint un document que par un geste de reprise, point par point.

> **Les versets sont relus** — ce que le modèle a cité hors du texte servi est retiré. Un
> verset inventé sur l'écran d'un pasteur est fatal, et il est détectable.

> **Un plan ne bouge pas sous son auteur** — l'empreinte fait qu'un rejeu retrouve le plan
> gardé au lieu d'en fabriquer un autre.
"""

from __future__ import annotations

import pytest

from app.contexts.urim.application.ports import (
    Feasibility,
    PointPropose,
    SquelettePropose,
)
from app.contexts.urim.application.study_service import OptionInconnueError
from app.contexts.urim.interface.schemas import StudyView
from app.contexts.urim.interface.turn import construire_tour

from .test_study_service import _PESEES, AUTEUR, _index, _Modele, _ouvrir, _service

COUPLES = (Feasibility("textuel", "doctrinal", True, "", "faible"),)


class _ModeleQuiPropose(_Modele):
    """Un modèle qui rend un plan — **et qui cite un verset hors du texte servi**.

    Les deux références sont volontaires : « Hébreux 13:1 » est dans le passage ouvert par les
    tests, « Romains 3:21 » ne l'est pas. C'est exactement le comportement mesuré le 22/08 —
    le modèle **complète de mémoire**, exactement, et donc de façon invérifiable."""

    def __init__(self, **kw) -> None:
        super().__init__(**kw)
        self.appels = 0
        self._model = "mistral-small-latest"

    async def squelette(self, *, reference, texte, axe, forme):
        self.appels += 1
        return SquelettePropose(
            titre="L'hospitalité, porte des anges",
            points=(
                PointPropose(
                    titre="Aimer ses frères sans se lasser",
                    versets=("Hébreux 13:1", "Romains 3:21"),
                ),
                PointPropose(titre="Accueillir l'inconnu", versets=()),
            ),
            model=self._model,
        )


def _avec_un_modele(modele):
    service = _service(index=_index(bearings=_PESEES, couples=COUPLES))
    service.resolver = modele
    return service


async def _jusqu_au_plan(modele):
    """Une préparation menée jusqu'à ce qu'un plan soit proposé."""
    service = _avec_un_modele(modele)
    dto = await _ouvrir(service, "Hébreux 13:1-2")
    dto = await service.decide(
        actor_account_id=AUTEUR, study_id=dto.record.id,
        stage_code="bear_axes", option_code="anthropologie",
    )
    return service, dto


# ============================================================== 1. les versets sont relus


@pytest.mark.asyncio
async def test_un_verset_hors_du_texte_servi_est_retire_et_le_point_reste():
    """🔴 **Retiré, pas signalé.** Un avertissement laisse la référence lisible — et c'est la
    référence qu'on recopie.

    Le point, lui, reste : son titre ne dépend pas de ses appuis, et le pasteur juge mieux un
    point nu qu'un point disparu sans explication."""
    _, dto = await _jusqu_au_plan(_ModeleQuiPropose())

    premier = dto.squelette.points[0]
    assert premier.titre == "Aimer ses frères sans se lasser"
    assert "Romains 3:21" not in premier.versets, "un verset de mémoire a traversé"
    assert premier.versets == ("Hébreux 13:1",)


@pytest.mark.asyncio
async def test_un_point_sans_verset_traverse_intact():
    """Un point nu n'est pas un point cassé. Le modèle n'a rien cité, on n'invente rien."""
    _, dto = await _jusqu_au_plan(_ModeleQuiPropose())

    assert dto.squelette.points[1].versets == ()


# ================================================ 2. un plan ne bouge pas sous son auteur


@pytest.mark.asyncio
async def test_parler_dans_le_fil_ne_refabrique_pas_le_plan():
    """⚠️ **Deux effets, et le second compte plus que le premier.**

    Le rejeu ne refacture pas — mais surtout, **le pasteur ne voit pas ses points changer sous
    lui** à chaque phrase qu'il écrit. Un plan qui bouge à chaque tour n'est pas un plan.

    Le tour de parole est le bon geste pour l'éprouver : il **persiste**, donc il traverse le
    chemin où la fabrication a lieu. Une simple relecture ne prouverait rien, elle ne fabrique
    jamais."""
    modele = _ModeleQuiPropose()
    service, dto = await _jusqu_au_plan(modele)
    avant = modele.appels

    encore = await service.dire(
        actor_account_id=AUTEUR, study_id=dto.record.id,
        raw_input="il faudra parler de l'accueil des voyageurs",
    )

    assert modele.appels == avant, "le plan a été refabriqué sur une phrase du fil"
    assert encore.squelette.titre == dto.squelette.titre


@pytest.mark.asyncio
async def test_changer_d_axe_refabrique_le_plan():
    """Le pendant, et il n'est pas une dépense de trop : un plan sur l'homme et un plan sur le
    Christ ne se ressemblent pas. Garder le premier après un changement d'axe montrerait au
    pasteur des points faits pour une question qu'il ne pose plus.

    🔴 C'est ce test-ci qui a corrigé le précédent : j'y voyais d'abord une refabrication
    parasite, et le compteur disait vrai — le moteur retient un axe dès l'ouverture, et le
    pasteur en avait choisi un autre."""
    modele = _ModeleQuiPropose()
    service, dto = await _jusqu_au_plan(modele)
    avant = modele.appels

    await service.decide(
        actor_account_id=AUTEUR, study_id=dto.record.id,
        stage_code="bear_axes", option_code="christologie",
    )

    assert modele.appels == avant + 1


@pytest.mark.asyncio
async def test_sans_modele_le_pasteur_ecrit_son_plan_comme_avant():
    """`None` partout, et **rien ne casse** : c'est l'état de production sans clé, et le
    comportement de tous les adaptateurs `Null*` du dépôt."""
    _, dto = await _jusqu_au_plan(_Modele())

    assert dto.squelette is None
    tour = construire_tour(StudyView.from_dto(dto))
    assert not [b for b in tour.blocks if b.kind == "skeleton"]


# ========================================================================= 3. le verrou


@pytest.mark.asyncio
async def test_le_plan_propose_n_atteint_aucun_element_sans_geste():
    """🔴 **La règle centrale du livrable, et elle se défait sans bruit.**

    Le document n'imprime que `preparation_element`. Tant que le pasteur n'a rien repris, son
    plan est **vide** — même si Urim lui en propose un complet à l'écran."""
    _, dto = await _jusqu_au_plan(_ModeleQuiPropose())

    assert dto.squelette.points, "rien n'a été proposé, le test ne prouve rien"
    assert dto.elements == (), "une proposition a atteint le plan toute seule"


@pytest.mark.asyncio
async def test_reprendre_un_point_l_ecrit_dans_son_plan_avec_ses_versets():
    """Les versets sont **dans le corps**, pas à côté : c'est cette ligne que le document
    imprimera, et celle que l'articulation relira pour servir les appuis."""
    service, dto = await _jusqu_au_plan(_ModeleQuiPropose())

    apres = await service.reprendre(
        actor_account_id=AUTEUR, study_id=dto.record.id, propose_code="point:0",
    )

    (point,) = apres.elements
    assert point.element_code == "divisions"
    assert point.body == "Aimer ses frères sans se lasser — Hébreux 13:1"


@pytest.mark.asyncio
async def test_reprendre_le_titre_le_range_sous_titre():
    service, dto = await _jusqu_au_plan(_ModeleQuiPropose())

    apres = await service.reprendre(
        actor_account_id=AUTEUR, study_id=dto.record.id, propose_code="titre",
    )

    (titre,) = apres.elements
    assert (titre.element_code, titre.body) == ("titre", "L'hospitalité, porte des anges")


@pytest.mark.asyncio
async def test_reprendre_deux_fois_le_meme_point_est_refuse():
    """**Une fois, et une seule** — comme la promotion d'une note. Deux points identiques dans
    un plan, et le pasteur ne saurait plus lequel est le sien."""
    service, dto = await _jusqu_au_plan(_ModeleQuiPropose())
    await service.reprendre(
        actor_account_id=AUTEUR, study_id=dto.record.id, propose_code="point:0",
    )

    with pytest.raises(OptionInconnueError, match="déjà repris"):
        await service.reprendre(
            actor_account_id=AUTEUR, study_id=dto.record.id, propose_code="point:0",
        )


@pytest.mark.asyncio
async def test_reprendre_n_ecrase_jamais_ce_qu_il_avait_ecrit():
    """⚠️ **On ajoute à la fin.** Ses divisions sont les siennes ; une reprise qui viendrait
    remplacer la troisième lui ferait perdre ce qu'il avait écrit."""
    from app.contexts.urim.application.ports import ElementRecord

    service, dto = await _jusqu_au_plan(_ModeleQuiPropose())
    await service.set_elements(
        actor_account_id=AUTEUR, study_id=dto.record.id,
        elements=[ElementRecord("divisions", 1, "Ce que j'avais déjà écrit")],
    )

    apres = await service.reprendre(
        actor_account_id=AUTEUR, study_id=dto.record.id, propose_code="point:1",
    )

    corps = [e.body for e in apres.elements]
    assert "Ce que j'avais déjà écrit" in corps
    assert "Accueillir l'inconnu" in corps


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "code", ["point:9", "point:abc", "chapeau", "point:-1"],
    ids=["rang-perime", "rang-illisible", "prefixe-inconnu", "rang-negatif"],
)
async def test_un_code_qui_ne_designe_rien_est_refuse(code):
    """Un rang hors liste est un refus, pas un dernier point : le client aurait envoyé un
    index périmé, et l'écrire quelque part serait inventer ce que le pasteur a désigné."""
    service, dto = await _jusqu_au_plan(_ModeleQuiPropose())

    with pytest.raises(OptionInconnueError):
        await service.reprendre(
            actor_account_id=AUTEUR, study_id=dto.record.id, propose_code=code,
        )


# ========================================================================= 4. l'écran


@pytest.mark.asyncio
async def test_le_bloc_porte_les_points_leurs_versets_et_leur_reprise():
    _, dto = await _jusqu_au_plan(_ModeleQuiPropose())

    bloc = next(
        b for b in construire_tour(StudyView.from_dto(dto)).blocks
        if b.kind == "skeleton"
    )

    assert bloc.title == "L'hospitalité, porte des anges"
    assert [p.propose_code for p in bloc.points] == ["point:0", "point:1"]
    assert bloc.points[0].verses == ["Hébreux 13:1"]
    assert not any(p.taken for p in bloc.points)


@pytest.mark.asyncio
async def test_un_point_repris_ne_s_offre_plus():
    """La reprise ne s'offre pas deux fois. 🔴 Et la comparaison se fait sur le corps
    **normalisé** : le pasteur retaille ses points, et un bouton qui reviendrait sur un point
    déjà dans son plan lui ferait écrire le même deux fois."""
    service, dto = await _jusqu_au_plan(_ModeleQuiPropose())

    apres = await service.reprendre(
        actor_account_id=AUTEUR, study_id=dto.record.id, propose_code="point:0",
    )

    bloc = next(
        b for b in construire_tour(StudyView.from_dto(apres)).blocks
        if b.kind == "skeleton"
    )
    assert bloc.points[0].taken
    assert not bloc.points[1].taken
