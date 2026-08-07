"""La curation — **les refus**, pas les succès.

Cette surface est la seule qui écrive dans ce que le pasteur lira comme *relu*. Ce qu'elle
laisse passer devient de la doctrine affichée sous l'autorité de quelqu'un. Les tests ici
gardent donc ce qu'elle **refuse** : une signature qui ne désigne personne, une relecture à
moitié faite qui ressemblerait à une relecture finie (S38), un refus muet, un caveat
confessionnel qui ne nomme pas les traditions.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.contexts.urim.application.curation import (
    BearingDraft,
    CaveatDraft,
    ContextDraft,
    FeasibilityDraft,
    PericopeDraft,
    UrimCuration,
)
from app.contexts.urim.domain.errors import CurationInvalideError
from app.contexts.urim.engine.deps import DoctrinalAxis
from app.contexts.urim.infrastructure.corpus.index import CorpusIndex

LOCI = (
    "theologie_propre", "christologie", "pneumatologie", "anthropologie", "hamartiologie",
    "soteriologie", "ecclesiologie", "angelologie", "demonologie", "eschatologie",
)

UNITE = UUID("11111111-2222-3333-4444-555555555555")

MOTIF = "Le coeur du chant, encadre par le mepris du v. 3 et le silence du v. 7."


def _index() -> CorpusIndex:
    return CorpusIndex(
        snapshot="essai", fallback_version_id=uuid4(), metered_versions=frozenset(),
        books_by_form={}, forms_by_length=(),
        label_by_book={23: "Ésaïe"}, book_by_label={"Ésaïe": 23}, osis_by_book={23: "Isa"},
        chapters_held={23: frozenset({53})}, max_verse_held={(23, 53): 12},
        idf={}, verses=(), postings={},
        pericopes=(), bearings={}, caveats={}, notes={}, couples={}, dominant={},
        axes=tuple(DoctrinalAxis(c, c, i) for i, c in enumerate(LOCI, start=1)),
    )


class _Repo:
    """Dépôt en mémoire — il enregistre, il ne juge rien. C'est le service qu'on éprouve."""

    def __init__(self, existe: bool = True) -> None:
        self.existe = existe
        self.bearings: list[BearingDraft] = []
        self.caveats: list[CaveatDraft] = []
        self.feasibility: list[FeasibilityDraft] = []
        self.cree: list[PericopeDraft] = []

    async def add_pericope(self, draft, book_id):
        self.cree.append(draft)
        return UNITE

    async def get_book_id(self, pericope_id):
        return 23 if self.existe else None

    async def replace_bearings(self, pericope_id, drafts, reviewed_by):
        self.bearings = drafts

    async def add_caveat(self, pericope_id, draft, reviewed_by):
        self.caveats.append(draft)
        return uuid4()

    async def add_context(self, pericope_id, draft, reviewed_by):
        return uuid4()

    async def replace_feasibility(self, pericope_id, drafts, reviewed_by):
        self.feasibility = drafts

    async def delete_pericope(self, pericope_id):
        return self.existe

    async def list_pericopes(self, book_id):
        return []

    async def coverage(self):  # pragma: no cover - non éprouvé ici
        raise NotImplementedError


def _service(repo: _Repo | None = None) -> tuple[UrimCuration, list[int]]:
    purges: list[int] = []
    return (
        UrimCuration(
            repo=repo or _Repo(), index=_index(), invalidate=lambda: purges.append(1)
        ),
        purges,
    )


def _draft(**kw) -> PericopeDraft:
    base = {
        "book": "Ésaïe", "start_ch": 53, "start_v": 4, "end_ch": 53, "end_v": 6,
        "rationale": MOTIF, "source_ref": "BHS", "reviewed_by": "Cedric Sasi",
    }
    return PericopeDraft(**{**base, **kw})


def _dix(**remplace) -> list[BearingDraft]:
    return [
        BearingDraft(remplace.get(a, a), "absent", "rien de notable ici.", "BHS")
        for a in LOCI
    ]


# ====================================================================== la signature


@pytest.mark.parametrize("nom", ["semis-demo", "auto", "ia", "  ", "x"])
async def test_on_ne_signe_pas_d_un_nom_qui_ne_designe_personne(nom):
    """Le champ dit au pasteur **qui a pesé** ce texte.

    `semis-demo` est refusé explicitement : c'est la marque d'un jeu de démonstration, et
    la laisser passer rendrait le garde décoratif — un corpus semé ressemblerait alors à un
    corpus relu, ce qui est exactement la confusion que `reviewed_by NOT NULL` empêche."""
    service, _ = _service()

    with pytest.raises(CurationInvalideError):
        await service.create_pericope(_draft(reviewed_by=nom))


# ================================================================= l'unité littéraire


async def test_un_motif_qui_ne_dit_rien_est_refuse():
    """Le `NOT NULL` de la base accepte une chaîne vide ; le pasteur, non.

    C'est *la* phrase qu'il lit pour comprendre ces bornes-là — ou pour les contester."""
    service, _ = _service()

    with pytest.raises(CurationInvalideError, match="pourquoi celles-ci"):
        await service.create_pericope(_draft(rationale="parce que"))


async def test_des_bornes_hors_du_texte_sont_refusees():
    """Curer Ésaïe 53:99 produirait une unité que personne ne peut lire."""
    service, _ = _service()

    with pytest.raises(CurationInvalideError, match="12 versets"):
        await service.create_pericope(_draft(end_v=99))


async def test_un_livre_inconnu_est_refuse():
    service, _ = _service()

    with pytest.raises(CurationInvalideError, match="Enoch"):
        await service.create_pericope(_draft(book="Enoch"))


async def test_des_bornes_inversees_sont_refusees():
    service, _ = _service()

    with pytest.raises(CurationInvalideError, match="inversées"):
        await service.create_pericope(_draft(start_v=9, end_v=4))


# ========================================================== les dix loci (S38, le coeur)


async def test_les_dix_loci_se_pesent_ensemble():
    """⚠️ **S38 rendu structurel.**

    Une unité sans ligne sur un axe signifie *« personne n'a regardé »* ; marquée `absent`,
    elle signifie *« quelqu'un a regardé et le texte n'en dit rien »*. Le moteur distingue
    déjà les deux — si la surface acceptait une saisie partielle, une curation à moitié
    faite ressemblerait à une curation finie."""
    service, _ = _service()

    with pytest.raises(CurationInvalideError, match="manquants"):
        await service.set_bearings(UNITE, _dix()[:9], "Cedric Sasi")


async def test_un_axe_invente_est_refuse():
    """Le cas réel : « amour de Dieu » avait été **inventé** comme axe au début du projet.

    Les dix loci de la théologie systématique sont une liste canonique, pas une famille
    ouverte : un onzième axe passerait inaperçu et fonderait des sermons."""
    service, _ = _service()

    with pytest.raises(CurationInvalideError, match="amour_de_dieu"):
        await service.set_bearings(
            UNITE, _dix(eschatologie="amour_de_dieu"), "Cedric Sasi"
        )


async def test_un_axe_pese_deux_fois_est_refuse():
    """Dix lignes, mais neuf axes — le compte y est et la relecture n'y est pas."""
    service, _ = _service()
    doublon = [*_dix()[:9], BearingDraft("soteriologie", "porte", "encore.", "BHS")]

    with pytest.raises(CurationInvalideError, match="deux fois"):
        await service.set_bearings(UNITE, doublon, "Cedric Sasi")


async def test_une_pesee_absente_exige_quand_meme_son_motif():
    """Dire *pourquoi* un texte ne porte pas un axe est aussi utile que l'inverse — et c'est
    ce qui distingue « j'ai regardé » de « j'ai laissé le champ vide »."""
    service, _ = _service()
    muet = _dix()
    muet[3] = BearingDraft("anthropologie", "absent", "   ", "BHS")

    with pytest.raises(CurationInvalideError, match="sans motif"):
        await service.set_bearings(UNITE, muet, "Cedric Sasi")


async def test_les_dix_loci_complets_passent():
    repo = _Repo()
    service, purges = _service(repo)

    await service.set_bearings(UNITE, _dix(), "Cedric Sasi")

    assert len(repo.bearings) == 10
    assert purges, "l'index n'a pas été purgé — la curation resterait invisible"


# ============================================================ les mises en garde, la forme


async def test_un_caveat_confessionnel_nomme_les_traditions():
    """D-F — il s'affiche **toujours**, y compris quand la tradition de l'église est inconnue.

    C'est la formulation qui le rend possible (« ici les traditions divergent »), et elle
    exige de savoir lesquelles."""
    service, _ = _service()

    with pytest.raises(CurationInvalideError, match="traditions"):
        await service.add_caveat(
            UNITE,
            CaveatDraft("soteriologie", "confessionnel", "Ici les lectures divergent.", "BHS"),
            "Cedric Sasi",
        )


async def test_un_caveat_exegetique_n_a_pas_besoin_de_traditions():
    repo = _Repo()
    service, _ = _service(repo)

    await service.add_caveat(
        UNITE,
        CaveatDraft("soteriologie", "exegetique", "Le texte ne dit pas comment.", "BHS"),
        "Cedric Sasi",
    )

    assert len(repo.caveats) == 1


async def test_le_contexte_est_source_ou_absent():
    """« Il n'y a pas de troisième possibilité. »"""
    service, _ = _service()

    with pytest.raises(CurationInvalideError, match="sourcé"):
        await service.add_context(
            UNITE, ContextDraft("historique", "Sous le regne d'Ozias.", 1, "  "), "Cedric"
        )


# ================================================================== le refus homilétique


async def test_un_couple_refuse_sans_motif_est_rejete():
    """Un refus muet est un refus qu'on ne peut pas contester — et celui-ci s'oppose au
    travail de quelqu'un."""
    service, _ = _service()

    with pytest.raises(CurationInvalideError, match="refusé sans motif"):
        await service.set_feasibility(
            UNITE,
            [FeasibilityDraft("expositif", "biographique", False, "eleve", None)],
            "Cedric Sasi",
        )


async def test_un_couple_faisable_n_a_pas_besoin_de_motif_de_refus():
    repo = _Repo()
    service, _ = _service(repo)

    await service.set_feasibility(
        UNITE, [FeasibilityDraft("expositif", "doctrinal", True, "faible", None)], "Cedric"
    )

    assert len(repo.feasibility) == 1


# =========================================================================== l'index gelé


async def test_toute_ecriture_purge_l_index():
    """L'index est gelé par processus : sans purge, une curation signée resterait invisible
    jusqu'au redémarrage — et le relecteur croirait son travail perdu."""
    repo = _Repo()
    service, purges = _service(repo)

    await service.create_pericope(_draft())
    await service.set_bearings(UNITE, _dix(), "Cedric Sasi")
    await service.delete_pericope(UNITE)

    assert len(purges) == 3


async def test_supprimer_une_unite_absente_ne_purge_rien():
    service, purges = _service(_Repo(existe=False))

    assert await service.delete_pericope(UNITE) is False
    assert purges == []
