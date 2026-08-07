"""**Étages 3 et 5** — servir le texte, et montrer ce à quoi il résiste.

Deux étages, deux promesses différentes :

- **l'étage 3** tient *« aucun mur un vendredi soir »* — le plafond mord ici et nulle part
  ailleurs, et le repli est increvable par construction ;
- **l'étage 5** tient l'argument du produit. Retirez-lui la ligne qui fait remonter les pesées
  `resiste` au même rang que les portantes, et Urim devient un moteur de proof-texting avec de
  meilleures manières.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.contexts.urim.calendar.domain.ports import NullEcclesialContext
from app.contexts.urim.engine import (
    AxisBearing,
    BearAxes,
    Bounds,
    EngineDeps,
    EntryMode,
    Outcome,
    Reference,
    ServeCorpus,
    StudyState,
)
from app.contexts.urim.engine.errors import StagePrerequisiteError

ROM_8 = Reference(book="Romains", chapter=8, verse_start=1, verse_end=17)
BORNES = Bounds(start=ROM_8, end=ROM_8)

LSG = uuid4()
SOUS_LICENCE = uuid4()
PERICOPE = uuid4()


def _pesee(code, label, force, motif="curé et relu"):
    return AxisBearing(axis_code=code, label=label, strength=force, rationale=motif)


class _Versions:
    def __init__(self, *, plafond=False, comptees=()):
        self._plafond, self._comptees = plafond, set(comptees)

    def ceiling_reached(self) -> bool:
        return self._plafond

    def is_metered(self, version_id: UUID) -> bool:
        return version_id in self._comptees

    def public_domain_fallback(self) -> UUID:
        return LSG


class _Doctrine:
    def __init__(self, pesees=(), garde=()):
        self._pesees, self._garde = tuple(pesees), tuple(garde)

    def bearings(self, pericope_id):
        return self._pesees

    def caveats(self, pericope_id):
        return self._garde

    def dominant_axis(self, pericope_id):
        return None


class _Rien:
    def snapshot(self) -> str:
        return "corpus-2026-08"


def _deps(*, versions=None, doctrine=None):
    return EngineDeps(
        corpus=_Rien(), doctrine=doctrine or _Doctrine(), homiletics=_Rien(),
        context=NullEcclesialContext(), versions=versions or _Versions(),
        clock=lambda: datetime(2026, 8, 6, tzinfo=UTC),
    )


def _state(**kw):
    base = {
        "session_id": uuid4(), "church_id": uuid4(), "author_id": uuid4(),
        "corpus_snapshot": "corpus-2026-08", "entry_mode": EntryMode.REFERENCE,
        "raw_input": "Romains 8:1-17", "resolved": ROM_8, "bounds": BORNES,
        "pericope_id": PERICOPE,
    }
    return StudyState(**{**base, **kw})


# =================================================================================================
# Étage 3 — servir le texte
# =================================================================================================


def test_le_domaine_public_ne_rencontre_jamais_le_plafond():
    """§13 — *« un pasteur qui travaille sur Segond 1910 ne rencontre jamais aucune limite »*.

    C'est le chemin de la grande majorité des préparations, et il ne coûte rien — même quand le
    plafond de l'église est atteint pour d'autres."""
    resultat = ServeCorpus().execute(
        _state(), _deps(versions=_Versions(plafond=True, comptees={SOUS_LICENCE}))
    )

    assert resultat.outcome is Outcome.CONTINUE
    assert resultat.state.version_id == LSG


def test_une_version_comptee_passe_tant_que_le_plafond_n_est_pas_atteint():
    """**S6 — réserver n'est pas consommer.** Le droit s'acquiert ici, au premier service."""
    resultat = ServeCorpus().execute(
        _state(version_id=SOUS_LICENCE),
        _deps(versions=_Versions(plafond=False, comptees={SOUS_LICENCE})),
    )

    assert resultat.outcome is Outcome.CONTINUE
    assert resultat.state.version_id == SOUS_LICENCE


def test_au_plafond_on_retombe_sur_le_domaine_public_et_la_preparation_continue():
    """**Aucun mur un vendredi soir.** `DEGRADE` ne coupe pas le pipeline."""
    resultat = ServeCorpus().execute(
        _state(version_id=SOUS_LICENCE),
        _deps(versions=_Versions(plafond=True, comptees={SOUS_LICENCE})),
    )

    assert resultat.outcome is Outcome.DEGRADE
    assert resultat.state.version_id == LSG
    assert not resultat.halts


def test_le_motif_du_repli_n_affiche_aucun_compteur_et_ne_reproche_rien():
    """§13 — un compteur visible ferait **rationner** : le pasteur hésiterait avant d'ouvrir un
    texte, l'inverse exact du but. Rien ne s'affiche avant la dégradation, et la dégradation
    s'explique en une ligne."""
    resultat = ServeCorpus().execute(
        _state(version_id=SOUS_LICENCE),
        _deps(versions=_Versions(plafond=True, comptees={SOUS_LICENCE})),
    )

    assert "continue" in resultat.rationale
    for interdit in ("limite", "quota", "restant", "dépassé"):
        assert interdit not in resultat.rationale.lower()


def test_l_etage_exige_des_bornes():
    etage = ServeCorpus()

    assert not etage.applies(_state(bounds=None))
    assert etage.applies(_state())

    with pytest.raises(StagePrerequisiteError):
        etage.execute(_state(bounds=None), _deps())


# =================================================================================================
# Étage 5 — les axes, et ceux qui résistent
# =================================================================================================


def test_un_axe_dominant_unique_passe_et_le_texte_qui_resiste_voyage_avec_lui():
    """**La ligne qui porte tout le produit.**

    Un pasteur sûr de son axe est précisément celui qui a le plus besoin de lire ce qui lui
    résiste — donc les résistants s'affichent **même quand rien n'est ambigu**."""
    doctrine = _Doctrine(
        pesees=[
            _pesee("soteriologie", "Sotériologie — le salut", "dominant", "aucune condamnation"),
            _pesee("hamartiologie", "Hamartiologie — le péché", "resiste", "la chair demeure"),
        ]
    )

    resultat = BearAxes().execute(_state(), _deps(doctrine=doctrine))

    assert resultat.outcome is Outcome.CONTINUE
    assert resultat.state.axis == "soteriologie"
    assert "résiste" in resultat.rationale
    assert "la chair demeure" in resultat.rationale


def test_plusieurs_axes_dominants_sont_rendus_au_meme_rang():
    """S10 — les ordonner reviendrait à décider ce que le pasteur veut prêcher."""
    doctrine = _Doctrine(
        pesees=[
            _pesee("christologie", "Christologie", "dominant"),
            _pesee("pneumatologie", "Pneumatologie", "dominant"),
        ]
    )

    resultat = BearAxes().execute(_state(), _deps(doctrine=doctrine))

    assert resultat.outcome is Outcome.AWAIT
    assert [o.code for o in resultat.options] == ["christologie", "pneumatologie"]
    assert resultat.state.axis is None


def test_sans_dominant_on_propose_ce_que_le_texte_porte():
    doctrine = _Doctrine(
        pesees=[
            _pesee("ecclesiologie", "Ecclésiologie", "porte"),
            _pesee("angelologie", "Angélologie", "absent"),
        ]
    )

    resultat = BearAxes().execute(_state(), _deps(doctrine=doctrine))

    assert resultat.outcome is Outcome.AWAIT
    assert [o.code for o in resultat.options] == ["ecclesiologie"]


def test_un_axe_absent_n_apparait_jamais_comme_option():
    """`absent` et `resiste` sont **opposés**, pas voisins : ne rien dire n'est pas résister.

    Un axe absent n'affiche rien et aucun plan ne se construit dessus."""
    doctrine = _Doctrine(
        pesees=[
            _pesee("christologie", "Christologie", "dominant"),
            _pesee("demonologie", "Démonologie", "absent"),
        ]
    )

    resultat = BearAxes().execute(_state(), _deps(doctrine=doctrine))

    assert "Démonologie" not in resultat.rationale


def test_les_mises_en_garde_s_affichent_toujours():
    """D-F — y compris quand la tradition de l'église est inconnue. C'est la **formulation** qui
    le rend possible : « ici les traditions divergent », jamais « votre tradition dit X »."""
    doctrine = _Doctrine(
        pesees=[_pesee("soteriologie", "Sotériologie", "dominant")],
        garde=["ici les traditions divergent sur la persévérance"],
    )

    resultat = BearAxes().execute(_state(), _deps(doctrine=doctrine))

    assert "traditions divergent" in resultat.rationale


def test_hors_unite_curee_on_degrade_au_lieu_de_deviner():
    """**S22 rendu mécanique.** Le pasteur a forcé ses bornes : `pericope_id` est nul, donc il n'y
    a rien de relu à lire. On ne devine pas une pesée doctrinale — `reviewed_by NOT NULL`."""
    resultat = BearAxes().execute(_state(pericope_id=None), _deps())

    assert resultat.outcome is Outcome.DEGRADE
    assert resultat.state.axis is None
    assert "relue" in resultat.rationale


def test_une_unite_sans_aucune_pesee_ne_pretend_pas_avoir_ete_relue():
    """**L'ajustement le plus important de ce lot.**

        ligne absente  →  personne n'a encore regardé
        ligne `absent` →  quelqu'un a regardé, et le texte n'en dit rien

    Ce sont des choses **opposées**. En les confondant, le moteur affirmait avec assurance qu'un
    texte ne portait pas un axe que personne n'avait examiné — et une curation à moitié faite
    ressemblait à une curation finie."""
    resultat = BearAxes().execute(_state(), _deps(doctrine=_Doctrine(pesees=[])))

    assert resultat.outcome is Outcome.DEGRADE
    assert "n'a encore été relue" in resultat.rationale
    assert "ne porte aucun" not in resultat.rationale


def test_une_unite_relue_qui_ne_porte_rien_le_dit_et_montre_quand_meme_les_resistants():
    """Ne porter aucun des dix loci est une **information**, pas un échec — et les résistants
    s'affichent même là."""
    doctrine = _Doctrine(
        pesees=[
            _pesee("eschatologie", "Eschatologie", "absent"),
            _pesee("soteriologie", "Sotériologie", "resiste", "le texte complique l'assurance"),
        ]
    )

    resultat = BearAxes().execute(_state(), _deps(doctrine=doctrine))

    assert resultat.outcome is Outcome.DEGRADE
    assert "complique l'assurance" in resultat.rationale


def test_l_etage_ne_repasse_pas_sur_un_axe_deja_pose():
    etage = BearAxes()

    assert etage.applies(_state())
    assert not etage.applies(_state(axis="christologie"))


# =================================================================================================
# Le pipeline
# =================================================================================================


def test_le_texte_est_servi_avant_qu_on_le_pese():
    """L'ordre importe : on ne pèse pas la doctrine d'un texte qu'on n'a pas encore servi.

    La composition complète du pipeline est vérifiée une seule fois, dans
    `test_shape_and_theme.py`, avec le dernier étage livré."""
    from app.contexts.urim.engine import PIPELINE

    codes = [etage.code for etage in PIPELINE]
    assert codes.index("serve_corpus") < codes.index("bear_axes")


def test_l_identite_de_l_unite_voyage_avec_les_bornes():
    """Sans elle, les étages 4 à 6 n'ont **rien à lire** — c'est ce champ qui propage la liberté
    accordée au bornage jusqu'au bout du pipeline, sans qu'aucun étage n'ait à connaître la règle.
    """
    from app.contexts.urim.engine import PericopeView
    from app.contexts.urim.engine.stages.bound_pericope import BoundPericope

    unite = PericopeView(id=PERICOPE, bounds=BORNES, label="Romains 8:1-17", rationale="curé")

    class _CorpusUnite:
        def snapshot(self):
            return "corpus-2026-08"

        def pericopes_for(self, reference):
            return (unite,)

    resultat = BoundPericope().execute(
        _state(bounds=None, pericope_id=None),
        EngineDeps(
            corpus=_CorpusUnite(), doctrine=_Doctrine(), homiletics=_Rien(),
            context=NullEcclesialContext(), versions=_Versions(),
            clock=lambda: datetime(2026, 8, 6, tzinfo=UTC),
        ),
    )

    assert resultat.state.pericope_id == PERICOPE
