"""La boucle conversationnelle — **ce qui ne doit coûter aucun appel**.

Le chiffre que ce banc surveille n'est pas un taux de justesse : c'est le **nombre d'appels**.
Un tour que la liaison pouvait résoudre et qui atteint quand même le modèle est un défaut, pas
une inefficacité — le scénario du 12/08 a payé neuf appels et dix secondes pour trois refus, et
l'aiguilleur ne pouvait de toute façon pas dire *quelle* option était visée.

Le second groupe tient l'autre bout : aucune intention n'exécute quoi que ce soit. Un aiguilleur
probabiliste sans pouvoir d'exécution ne peut pas détruire un samedi soir de travail.
"""

from __future__ import annotations

import pytest

from app.contexts.urim.adapters.mistral import INTENTIONS_CONNUES
from app.contexts.urim.application.conversation import Ecran, Notation, conduire
from app.contexts.urim.application.ports import NullVerseResolver
from app.contexts.urim.engine.repondeurs import (
    _REPONDEURS,
    repondre_indechiffrable,
)
from app.contexts.urim.engine.state import Reference

#: L'écran du tour 2 de la maquette, tel que le pasteur le voit : deux loci, puis deux
#: passages proposés par le sens. L'ordre est celui de l'affichage — c'est lui qui donne
#: son sens à « le deuxième ».
ECRAN = Ecran(
    codes=("axe:soteriologie", "axe:ecclesiologie", "Romains 12:9-16", "Luc 15:11-24"),
    references=(
        Reference(""),
        Reference(""),
        Reference("Romains", 12, 9, 16),
        Reference("Luc", 15, 11, 24),
    ),
    libelles=(
        "Le salut offert", "La vie de l'assemblée", "Romains 12:9-16", "Luc 15:11-24",
    ),
    ancre="Romains 12:9-16",
    attend=True,
)


class _Aiguilleur:
    """Le modèle, **avec son compteur d'échecs** — c'est lui qui distingue les deux silences."""

    def __init__(self, intention: str | None = "interroger_travail", *, panne: bool = False):
        self.appels: list[str] = []
        self.echecs = 0
        self._intention, self._panne = intention, panne

    async def vestibule(self, text, *, sujet_en_cours=None):
        """Le double ne conduit pas de conversation : **il s'efface**, comme un modèle
        injoignable, et la préparation descend sans consentement — le régime d'avant le
        vestibule, qui est ce que ces tests éprouvent."""
        return None

    async def aiguiller(self, text: str) -> str | None:
        self.appels.append(text)
        if self._panne:
            # Exactement ce que fait `MistralAssistant.demander` sur un 429 : le compteur
            # monte, et le retour est `None` — le même `None` qu'un tour non classable.
            self.echecs += 1
            return None
        return self._intention


# ================================================ ce que la liaison consomme, à zéro appel


@pytest.mark.asyncio
async def test_une_reference_affichee_ne_coute_aucun_appel():
    ia = _Aiguilleur()

    tour = await conduire("Romains 12", ECRAN, ia)

    assert tour.decision == "Romains 12:9-16"
    assert tour.appels == 0 and ia.appels == []


@pytest.mark.asyncio
async def test_un_rang_designe_l_option_de_ce_rang():
    ia = _Aiguilleur()

    tour = await conduire("le deuxième", ECRAN, ia)

    assert tour.decision == "axe:ecclesiologie"
    assert ia.appels == []


@pytest.mark.asyncio
async def test_un_locus_se_designe_par_son_titre():
    """Le tour 2 de la maquette. Le pasteur tape le libellé qu'il lit — pas un code."""
    ia = _Aiguilleur()

    tour = await conduire("La vie de l'assemblée", ECRAN, ia)

    assert tour.decision == "axe:ecclesiologie"
    assert ia.appels == []


@pytest.mark.asyncio
async def test_trois_refus_successifs_ne_coutent_aucun_appel():
    """🔴 **Le scénario mesuré du 12/08 : neuf appels, dix secondes, rien appris.**

    C'est le défaut qui justifie tout l'étage. Et le coût n'était pas le pire : l'aiguilleur
    rendait `preciser` — ce qui est juste — sans aucun moyen de dire **quelle** option était
    visée. Il devinait, ou il redemandait."""
    ia = _Aiguilleur()

    tours = [
        await conduire(saisie, ECRAN, ia)
        for saisie in ("non, pas le premier", "pas le deuxième non plus", "enlève Luc 15")
    ]

    assert [t.refus for t in tours] == [
        "axe:soteriologie", "axe:ecclesiologie", "Luc 15:11-24",
    ]
    assert ia.appels == []


@pytest.mark.asyncio
async def test_des_bornes_qui_correspondent_a_une_option_la_designent():
    ia = _Aiguilleur()

    tour = await conduire("versets 9 à 16", ECRAN, ia)

    assert tour.decision == "Romains 12:9-16"
    assert ia.appels == []


@pytest.mark.asyncio
async def test_l_acquiescement_ne_coute_aucun_appel():
    """⚠️ La troisième forme d'`indechiffrable` n'atteint jamais son répondeur : la liaison la
    consomme. Elle ne devine pas pour autant sur **quoi** porte l'accord — elle redemande."""
    ia = _Aiguilleur()

    tour = await conduire("ok", ECRAN, ia)

    assert ia.appels == []
    assert tour.decision is None and tour.refus is None
    assert "accord" in (tour.reponse or "")


# ================================================ ce que la liaison laisse passer, et pourquoi


@pytest.mark.asyncio
async def test_un_demonstratif_seul_rend_la_main_au_modele():
    """🔴 **Le cas qui justifie la frontière.** Deux options peuvent convenir, et se tromper
    d'objet coûte plus cher qu'un appel : la liaison rend la main plutôt que de deviner."""
    ia = _Aiguilleur()

    tour = await conduire("celui-là", ECRAN, ia)

    assert tour.decision is None and tour.refus is None
    assert ia.appels == ["celui-là"] and tour.appels == 1


@pytest.mark.asyncio
async def test_une_question_libre_rend_la_main_au_modele():
    """Le tour 5 de la maquette — celui qui n'avait aucune route."""
    ia = _Aiguilleur("interroger_travail")

    tour = await conduire("Quel plan je peux tenir sur ce texte ?", ECRAN, ia)

    assert tour.appels == 1
    assert "plans que ce texte peut tenir" in (tour.reponse or "")


@pytest.mark.asyncio
async def test_des_bornes_qui_ne_correspondent_a_rien_rendent_la_main():
    """Il n'existe aucune route pour poser des bornes neuves. En fabriquer une ici serait
    inventer un geste — la demande part à l'aiguilleur, qui sait au moins la lire."""
    ia = _Aiguilleur("preciser")

    tour = await conduire("plutôt les versets 3 à 5", ECRAN, ia)

    assert tour.decision is None
    assert tour.appels == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("saisie", ["...", "   ", "?!"])
async def test_une_saisie_sans_un_seul_mot_ne_coute_aucun_appel(saisie: str):
    """Le fragment d'`indechiffrable` se reconnaît sans modèle : il n'y a rien à classer."""
    ia = _Aiguilleur()

    tour = await conduire(saisie, ECRAN, ia)

    assert ia.appels == []
    assert tour.reponse == repondre_indechiffrable(saisie, ECRAN.ancre)


@pytest.mark.asyncio
async def test_hors_attente_une_designation_ne_decide_rien():
    """⚠️ La liaison est aveugle à l'issue : elle reconnaît la cible, elle ne nomme le geste
    que sur un marqueur explicite. Quand aucune question n'est posée, une désignation nue n'a
    pas de geste évident — et c'est l'aiguilleur qui tranche."""
    ia = _Aiguilleur("interroger_texte")

    tour = await conduire("La vie de l'assemblée", Ecran(**{
        **{c: getattr(ECRAN, c) for c in ("codes", "references", "libelles", "ancre")},
        "attend": False,
    }), ia)

    assert tour.decision is None
    assert tour.appels == 1


# ============================================================ le contrôle de référence


@pytest.mark.asyncio
async def test_une_reference_que_le_corpus_refuse_recoit_le_verdict_du_corpus():
    """🔴 **`Hb 2v29` est dans les notes du Pasteur X, et Hébreux 2 compte 18 versets.**

    Urim savait le dire depuis le premier jour, et ne le disait qu'aux textes d'appui : au
    tour, la saisie repartait à l'aiguilleur, qui répondait à côté sans rien dire de l'erreur
    de référence."""
    ia = _Aiguilleur()
    motif = "Hébreux 2 compte 18 versets — il n'y a pas de verset 29."

    tour = await conduire("Hb 2v29", ECRAN, ia, Notation(introuvable=motif))

    assert ia.appels == [], "le corpus sait cela sans le modèle"
    assert motif in (tour.reponse or ""), "le motif du corpus traverse intact"
    assert tour.decision is None and tour.refus is None


@pytest.mark.asyncio
async def test_le_controle_passe_avant_la_liaison():
    """⚠️ Une référence que le corpus rejette peut quand même **désigner** une option — `Hb
    2v29` tombe dans une option affichée en chapitre entier. Décider silencieusement cacherait
    la seule chose utile de ce tour."""
    ecran = Ecran(
        codes=("Hébreux 2",),
        references=(Reference("Hébreux", 2),),
        libelles=("Hébreux 2",),
        ancre="Romains 12:9-16",
        attend=True,
    )
    lue = Reference("Hébreux", 2, 29)

    tour = await conduire(
        "Hb 2v29", ecran, _Aiguilleur(), Notation((lue,), "il n'y a pas de verset 29.")
    )

    assert tour.decision is None
    assert "verset 29" in (tour.reponse or "")


# ============================================================ les deux silences du modèle


@pytest.mark.asyncio
async def test_une_panne_n_est_pas_une_reponse():
    """🔴 Un 429 rend `None`, exactement comme un tour non classable. Les confondre ferait
    servir *« je n'ai rien reçu qui concerne la préparation »* à un pasteur dont la seule
    faute est d'avoir écrit pendant une coupure."""
    ia = _Aiguilleur(panne=True)

    tour = await conduire("Quel plan je peux tenir ?", ECRAN, ia)

    assert tour.reponse != repondre_indechiffrable("Quel plan je peux tenir ?", ECRAN.ancre)
    assert "de mon côté" in (tour.reponse or "")


@pytest.mark.asyncio
async def test_sans_modele_le_tour_le_dit_au_lieu_de_le_traiter_comme_du_bruit():
    """Pas de clé, ou quota épuisé — **un état de production, pas une panne** (S12, S37)."""
    tour = await conduire("Quel plan je peux tenir ?", ECRAN, NullVerseResolver())

    assert tour.appels == 0
    assert "phrase libre" in (tour.reponse or "")


# ============================================================ le vocabulaire, et son pouvoir


@pytest.mark.asyncio
@pytest.mark.parametrize("intention", sorted(INTENTIONS_CONNUES))
async def test_aucune_intention_n_execute_de_geste(intention: str):
    """⚠️ **Une intention propose, elle n'agit jamais.**

    `changer_de_sujet` ne ferme aucune préparation, `demander_production` ne fabrique rien.
    C'est ce qui rend un aiguilleur probabiliste acceptable : son mode d'échec est la
    non-pertinence, jamais la destruction."""
    tour = await conduire("une phrase que la liaison ne lit pas", ECRAN, _Aiguilleur(intention))

    assert tour.decision is None and tour.refus is None
    assert (tour.reponse or "").strip()


def test_les_sept_codes_ont_chacun_leur_repondeur():
    """Les deux listes vivent dans deux couches — le vocabulaire chez l'adaptateur, la voix
    dans le moteur. Rien d'autre que ce test ne les empêche de diverger en silence."""
    assert set(_REPONDEURS) == set(INTENTIONS_CONNUES)


@pytest.mark.asyncio
async def test_un_code_hors_vocabulaire_retombe_sur_indechiffrable():
    """Le filtre de l'adaptateur rend déjà `None` sur un code inventé ; le répondeur ne doit
    pas pour autant lever une clé manquante en pleine préparation."""
    tour = await conduire("bon alors", ECRAN, _Aiguilleur("code_invente"))

    assert (tour.reponse or "").strip()


# ================================================ la civilité, à zéro appel (terrain 22/08)


@pytest.mark.asyncio
@pytest.mark.parametrize("saisie", ["bonjour", "bonjour Urim", "merci beaucoup", "bonsoir"])
async def test_un_salut_en_cours_de_fil_ne_coute_aucun_appel(saisie):
    """🔴 **Le défaut du 22/08, côté fil.**

    « bonjour Urim » partait à l'aiguilleur, qui le classait `indechiffrable`. La réponse était
    correcte, et on avait payé un appel pour apprendre qu'il n'y avait rien à apprendre — le
    défaut même que `Tour.appels` existe pour mesurer."""
    ia = _Aiguilleur()

    tour = await conduire(saisie, ECRAN, ia)

    assert tour.appels == 0 and ia.appels == []
    assert tour.reponse and tour.decision is None and tour.refus is None


@pytest.mark.asyncio
async def test_le_salut_situe_le_travail_plutot_que_de_se_presenter():
    """Au milieu du fil, redire ce qu'on fait serait feindre de ne pas reconnaître celui à qui
    on parle depuis dix tours."""
    tour = await conduire("bonjour", ECRAN, _Aiguilleur())

    assert "Romains 12:9-16" in (tour.reponse or "")


@pytest.mark.asyncio
async def test_un_ecartement_reste_un_geste_et_non_une_politesse():
    """⚠️ **La garde est après la liaison, et c'est pour ça.**

    « oui », « non », « d'accord » appartiennent aussi au vocabulaire de la politesse. Les
    intercepter plus haut ferait répondre « bonjour » à un pasteur qui vient d'écarter un
    texte."""
    tour = await conduire("non, pas Luc 15:11-24", ECRAN, _Aiguilleur())

    assert tour.refus == "Luc 15:11-24"
