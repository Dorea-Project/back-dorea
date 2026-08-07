"""Le chemin inversé — d'une intention vers un texte (Architecture §7).

Ce que ces tests gardent n'est pas le chemin heureux : c'est **ce que l'étage n'a pas le
droit de faire**. Choisir un axe à la place du pasteur (S10), retirer une option parce
qu'un modèle a un avis (S12), enterrer les textes qui résistent (S20), ou diagnostiquer
celui qui écrit plutôt que nommer l'effet (S37).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.contexts.urim.calendar.domain.ports import NullEcclesialContext
from app.contexts.urim.engine.deps import (
    BearingSite,
    DoctrinalAxis,
    EngineDeps,
    NullConvictionReader,
)
from app.contexts.urim.engine.outcomes import Outcome
from app.contexts.urim.engine.stages.weigh_conviction import WeighConviction
from app.contexts.urim.engine.state import Bounds, EntryMode, Reference, StudyState

DIX = tuple(
    DoctrinalAxis(code, code.replace("_", " ").capitalize(), rang)
    for rang, code in enumerate(
        (
            "theologie_propre", "christologie", "pneumatologie", "anthropologie",
            "hamartiologie", "soteriologie", "ecclesiologie", "angelologie",
            "demonologie", "eschatologie",
        ),
        start=1,
    )
)


def _site(nom: str, force: str) -> BearingSite:
    return BearingSite(
        pericope_id=uuid4(),
        label=nom,
        bounds=Bounds(start=Reference("Romains", 8, 1), end=Reference("Romains", 8, 11)),
        strength=force,
        rationale=f"motif de {nom}",
    )


class _Doctrine:
    def __init__(self, sites: tuple[BearingSite, ...] = (), axes: tuple = DIX) -> None:
        self._sites, self._axes = sites, axes

    def axes(self):
        return self._axes

    def sites_for_axis(self, axis_code: str):
        return self._sites


class _Modele:
    """Un modèle branché — il *croit* savoir, et il ne doit pouvoir qu'annoter."""

    def __init__(self, axes=(), flags=()) -> None:
        self._axes, self._flags = axes, flags

    def candidate_axes(self, text: str):
        return self._axes

    def risk_flags(self, text: str):
        return self._flags


class _Rien:
    def ceiling_reached(self) -> bool:
        return False


def _deps(doctrine=None, conviction=None) -> EngineDeps:
    return EngineDeps(
        corpus=_Rien(),
        doctrine=doctrine or _Doctrine(),
        homiletics=_Rien(),
        context=NullEcclesialContext(),
        versions=_Rien(),
        clock=lambda: datetime(2026, 8, 7, tzinfo=UTC),
        conviction=conviction or NullConvictionReader(),
    )


def _etat(**kw) -> StudyState:
    base = {
        "session_id": uuid4(), "church_id": uuid4(), "author_id": uuid4(),
        "corpus_snapshot": "corpus-2026-08", "entry_mode": EntryMode.CONVICTION,
        "raw_input": "lamour fraternel nexiiste plus dans leglise",
    }
    return StudyState(**{**base, **kw})


# =================================================================================== portée


def test_le_chemin_inverse_ne_prend_que_la_conviction():
    """Une référence et une citation ont leur propre étage — celui-ci ne les touche pas."""
    assert WeighConviction().applies(_etat()) is True
    assert WeighConviction().applies(_etat(entry_mode=EntryMode.REFERENCE)) is False
    assert WeighConviction().applies(_etat(entry_mode=EntryMode.CITATION)) is False


def test_il_s_efface_des_qu_un_texte_est_retenu():
    """Sans quoi il reposerait indéfiniment la même question — le défaut exact déjà commis
    sur le bornage, où `pericope_id` était enregistré et invisible pour l'étage qui le lisait."""
    assert WeighConviction().applies(_etat(resolved=Reference("Romains", 8, 1))) is False


# ==================================================================== 1. le choix de l'axe


def test_les_dix_loci_sortent_toujours_sans_modele():
    """S12 — l'écran de base, pas un écran de secours.

    C'est ce qui rend Urim livrable **sans aucun modèle branché** : tablette, connexion
    irrégulière, plafond atteint — le mode conviction reste entier."""
    resultat = WeighConviction().execute(_etat(), _deps())

    assert resultat.outcome is Outcome.AWAIT
    assert [o.code for o in resultat.options] == [f"axe:{a.code}" for a in DIX]


def test_le_modele_annote_et_ne_retire_jamais_une_option():
    """S37 — la propriété de sûreté ne tient que si le port ne peut **qu'ajouter**.

    Un modèle qui pourrait écarter un axe pourrait nuire en se trompant. Celui-ci ne peut
    que changer une phrase, donc son erreur est inoffensive — et c'est la seule raison pour
    laquelle on l'autorise à parler."""
    modele = _Modele(axes=("ecclesiologie",))

    resultat = WeighConviction().execute(_etat(), _deps(conviction=modele))

    assert len(resultat.options) == 10, "le modèle a retiré des options"
    signale = next(o for o in resultat.options if o.code == "axe:ecclesiologie")
    autre = next(o for o in resultat.options if o.code == "axe:christologie")
    assert signale.rationale != autre.rationale, "l'annotation ne se voit pas"


def test_aucun_axe_n_est_presente_comme_le_meilleur():
    """S10 — une conviction est souvent une plainte, pas un thème.

    Ordonner les axes reviendrait à interpréter le for intérieur de celui qui écrit ;
    les nommer tous suffit. Le modèle signale, il ne classe pas."""
    resultat = WeighConviction().execute(
        _etat(), _deps(conviction=_Modele(axes=("soteriologie", "ecclesiologie")))
    )

    codes = [o.code for o in resultat.options]
    assert codes.index("axe:soteriologie") > codes.index("axe:theologie_propre"), (
        "un axe suggéré a été remonté en tête — c'est un classement déguisé"
    )


# ================================================================== 2. le choix du texte


def test_les_textes_qui_resistent_sortent_avec_les_autres():
    """§7 / S20 — **toute la protection du mode conviction est là**.

    Et elle a une propriété rare : elle ne dépend pas de la justesse de l'axe retenu. Un
    pasteur qui se trompe d'axe voit quand même les textes qui le compliquent."""
    doctrine = _Doctrine((
        _site("porte le sujet", "dominant"),
        _site("complique", "resiste"),
        _site("soutient", "porte"),
    ))

    resultat = WeighConviction().execute(_etat(axis="soteriologie"), _deps(doctrine))

    assert len(resultat.options) == 3
    resistant = next(o for o in resultat.options if "complique" in o.label)
    assert "⚠" in resistant.label, "un texte qui résiste doit se voir au premier coup d'œil"


def test_le_nombre_de_resistants_est_annonce_dans_le_motif():
    """C'est la partie qu'un pasteur pressé sauterait — donc elle est dite, pas rangée."""
    doctrine = _Doctrine((_site("a", "dominant"), _site("b", "resiste")))

    resultat = WeighConviction().execute(_etat(axis="soteriologie"), _deps(doctrine))

    assert "1 qui le" in resultat.rationale


def test_une_unite_qui_ne_dit_rien_de_l_axe_n_est_pas_un_candidat():
    """`absent` et `resiste` sont **opposés**, pas voisins : ne rien dire n'est pas résister.

    Le port les a déjà séparés ; ce test garde qu'on ne les recolle pas."""
    doctrine = _Doctrine((_site("porte", "porte"),))

    resultat = WeighConviction().execute(_etat(axis="soteriologie"), _deps(doctrine))

    assert [o.label for o in resultat.options] == ["porte — ce texte le soutient"]


def test_un_axe_sans_curation_refuse_en_disant_pourquoi():
    """S2 / S3 — le plafond dur du corpus curé, **dit franchement**.

    ⚠️ Le motif doit distinguer *« l'Écriture n'en dit rien »* de *« la relecture manque »*.
    Les confondre ferait croire au pasteur que son sujet n'est pas biblique."""
    resultat = WeighConviction().execute(_etat(axis="angelologie"), _deps(_Doctrine(())))

    assert resultat.outcome is Outcome.REFUSE
    assert "la curation ne couvre pas" in resultat.rationale
    assert resultat.options == ()


# ============================================================================ 3. le risque


def test_le_motif_du_risque_nomme_l_effet_jamais_celui_qui_ecrit():
    """S10 / S37 — « formulation à forte charge » se conteste ; « vous êtes dans la plainte »
    est un diagnostic, et le produit l'interdit."""
    doctrine = _Doctrine((_site("a", "dominant"),))

    motif = WeighConviction().execute(
        _etat(axis="soteriologie", risk_flags=("charge",)), _deps(doctrine)
    ).rationale

    assert "textes qui résistent sont affichés" in motif
    for diagnostic in ("vous êtes", "vous semblez", "votre état", "plainte", "colère"):
        assert diagnostic not in motif.lower()


def test_sans_drapeau_le_motif_ne_dit_rien_du_risque():
    """Le vide est un état normal — on n'invente pas une mise en garde pour meubler."""
    doctrine = _Doctrine((_site("a", "dominant"),))

    motif = WeighConviction().execute(_etat(axis="soteriologie"), _deps(doctrine)).rationale

    assert "charge" not in motif


# ======================================================================== 4. l'invariant


def test_le_chemin_inverse_est_deterministe():
    """Même intention, même corpus, mêmes options — cent fois. Aucun modèle, aucun hasard."""
    doctrine = _Doctrine((_site("a", "dominant"), _site("b", "resiste")))
    deps = _deps(doctrine)

    vues = {
        tuple(o.code for o in WeighConviction().execute(_etat(axis="x"), deps).options)
        for _ in range(100)
    }

    assert len(vues) == 1


def test_les_options_de_texte_portent_un_identifiant_utilisable():
    """La bordure doit pouvoir retrouver l'unité : le préfixe est explicite, jamais deviné.

    Déduire la nature d'une option de sa forme (« ça ressemble à un UUID ») marcherait
    jusqu'au premier axe nommé comme un identifiant."""
    site = _site("a", "dominant")
    resultat = WeighConviction().execute(_etat(axis="x"), _deps(_Doctrine((site,))))

    code = resultat.options[0].code
    assert code.startswith("texte:")
    assert UUID(code.removeprefix("texte:")) == site.pericope_id
