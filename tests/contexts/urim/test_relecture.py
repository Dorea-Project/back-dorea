"""La relecture — **la seule chose qui fasse décroître la dette de 45 557 lignes générées**.

Ce fichier garde trois propriétés, et chacune vient d'une erreur qu'on a faite ou frôlée.

**L'empreinte est prise au moment du verdict.** C'est ce qui interdit qu'un accord protège une
curation qu'il n'a jamais vue, et c'est aussi ce qui rend l'ordre *corriger d'abord, signer
ensuite* mécanique plutôt que recommandé : signer avant de réparer périme sa propre signature.

**Le nom du signataire est prouvé, pas déclaré.** Un verdict a été posé au nom du propriétaire
du dépôt pour un essai, et il a fallu le retirer. Aucun validateur ne pouvait l'empêcher tant
que le nom arrivait dans un corps de requête.

**Un verdict `accepte` ne fait pas disparaître le signalement.** Apocalypse 5 porte réellement
huit loci : le détecteur a raison de la trouver inhabituelle et tort d'en faire un défaut. Ce
qui sort de la file est l'unité, pas la trace de ce qu'on lui reprochait.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.contexts.urim.application.curation import (
    COUCHE_MISE_EN_GARDE,
    COUCHE_PESEE,
    empreinte_de_curation,
)
from app.contexts.urim.application.relecture import (
    LigneCuration,
    RegistreDesRelecteurs,
    Relecteur,
    Relecture,
    Signalement,
    UniteSignalee,
    VerdictPose,
    empreinte_de_secret,
)
from app.contexts.urim.domain.errors import (
    CurationInvalideError,
    RelecteurInconnuError,
    UniteIntrouvableError,
)
from app.contexts.urim.infrastructure.persistence.corpus_models import (
    CorpusBookNameModel,
    CorpusDoctrinalBearingModel,
    CorpusDoctrinalCaveatModel,
    CorpusPericopeModel,
    CorpusReviewerModel,
    CorpusSignalModel,
    CorpusVerseModel,
    CorpusVersionModel,
)
from app.contexts.urim.infrastructure.persistence.relecture_repository import (
    SqlRegistreRepository,
    SqlRelectureRepository,
)
from app.core.database import Base

_NOW = datetime(2026, 8, 13, tzinfo=UTC)
UNITE = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
KOUASSI = Relecteur(identifiant="kouassi", nom="Kouassi Jean")


def _ligne(corps: str, *, axe: str = "christologie", generee: bool = True) -> LigneCuration:
    return LigneCuration(
        couche=COUCHE_PESEE, axe=axe, force="porte", corps=corps,
        source="lecture suivie", signee_par="ia-mistral" if generee else "Kouassi Jean",
    )


class _Repo:
    """Une doublure qui **recalcule l'empreinte**, comme le fait le vrai dépôt.

    C'est le seul comportement qu'il ne fallait pas simplifier ici : une doublure qui mémorise
    l'empreinte au lieu de la dériver des lignes rendrait verts exactement les tests censés
    attraper un verdict qui survit à la curation qu'il jugeait."""

    def __init__(self, lignes: list[LigneCuration], detecteurs: tuple[str, ...] = ("D4",)):
        self.lignes_courantes = lignes
        self.detecteurs = detecteurs
        self.verdicts: dict[str, VerdictPose] = {}

    def _empreinte(self) -> str:
        return empreinte_de_curation(
            (ligne.couche, ligne.axe, ligne.corps) for ligne in self.lignes_courantes
        )

    def _unite(self) -> UniteSignalee:
        return UniteSignalee(
            id=UNITE, reference="Apocalypse 5:5-14", libelle="Le Lion et l'Agneau",
            signature="ia-mistral", empreinte_courante=self._empreinte(),
            signalements=[
                Signalement(
                    detecteur=code, libelle=f"{code} aberration", gravite=2,
                    detail="8 loci portants sur 10", corps="",
                    empreinte_balayage=self._empreinte(),
                )
                for code in self.detecteurs
            ],
            verdicts=list(self.verdicts.values()),
        )

    async def file(self, *, limite: int, decalage: int) -> list[UniteSignalee]:
        return [self._unite()][decalage : decalage + limite]

    async def unite(self, pericope_id: UUID) -> UniteSignalee | None:
        return self._unite() if pericope_id == UNITE else None

    async def lignes(self, pericope_id: UUID) -> list[LigneCuration]:
        return self.lignes_courantes

    async def texte(self, pericope_id: UUID):
        return []

    async def enregistrer_verdict(self, pericope_id: UUID, verdict: VerdictPose) -> None:
        self.verdicts[verdict.portee] = verdict

    async def retirer_verdict(self, pericope_id: UUID, portee: str) -> str | None:
        retire = self.verdicts.pop(portee, None)
        return retire.relu_par if retire else None

    async def compteur(self):  # pragma: no cover - éprouvé sur le vrai dépôt plus bas
        raise NotImplementedError


def _relecture(repo: _Repo) -> Relecture:
    return Relecture(repo=repo, clock=lambda: _NOW)


# ============================================== l'empreinte est prise au moment du verdict


async def test_corriger_apres_avoir_signe_perime_sa_propre_signature():
    """🔴 **La propriété qui rend inutile tout contrôle sur l'ordre des gestes.**

    On aurait pu exiger qu'un verdict `corrige` soit accompagné d'une correction — un contrôle
    de plus, contournable, et qui aurait fait porter au produit un jugement sur le travail du
    relecteur. L'empreinte suffit : signer d'abord fige la décision sur la curation fautive, la
    correction la périme, l'unité revient en file. Le mécanisme se garde lui-même."""
    repo = _Repo([_ligne("le Lion de Juda a vaincu")])
    relecture = _relecture(repo)

    await relecture.poser(
        UNITE, portee="D4", verdict="corrige", note=None, relecteur=KOUASSI
    )
    assert await relecture.file() == []

    repo.lignes_courantes = [_ligne("l'Agneau immolé est le Lion qui a vaincu", generee=False)]

    (revenue,) = await relecture.file()
    assert [s.detecteur for s in revenue.restants] == ["D4"]
    assert revenue.verdicts[0].empreinte_jugee != revenue.empreinte_courante


async def test_le_verdict_juge_ce_que_la_base_contient_et_non_ce_que_le_balayage_avait_vu():
    """Le signalement porte l'empreinte du balayage ; le verdict, celle du moment où l'on signe.

    Confondre les deux ferait juger une ligne réécrite depuis — c'est-à-dire signer pour une
    phrase qu'on n'a pas lue."""
    repo = _Repo([_ligne("première rédaction")])
    depuis_le_balayage = repo._empreinte()
    repo.lignes_courantes = [_ligne("rédaction corrigée entre-temps")]

    pose = await _relecture(repo).poser(
        UNITE, portee="D4", verdict="accepte", note=None, relecteur=KOUASSI
    )

    assert pose.empreinte_jugee != depuis_le_balayage
    assert pose.empreinte_jugee == repo._empreinte()


# ============================================================ ce que la file rend, et n'efface pas


async def test_accepte_sort_l_unite_de_la_file_sans_effacer_ce_qu_on_lui_reprochait():
    """⚠️ **`accepte` n'est pas « c'est bien »** : c'est *« l'écart est réel et la curation est
    juste quand même »*. Apocalypse 5 porte réellement huit loci. Sans ce verdict elle
    reviendrait en tête de file éternellement — et une file qui ne décroît pas n'est pas une
    file, c'est un reproche permanent."""
    repo = _Repo([_ligne("le texte porte huit loci, et c'est le cas")])
    relecture = _relecture(repo)

    await relecture.poser(UNITE, portee="D4", verdict="accepte", note=None, relecteur=KOUASSI)

    assert await relecture.file() == []
    dossier = await relecture.dossier(UNITE)
    assert [s.detecteur for s in dossier.unite.signalements] == ["D4"]
    assert dossier.unite.restants == []


async def test_ensemble_couvre_les_detecteurs_qu_on_n_a_pas_nommes():
    """Un relecteur qui a relu tout le passage n'a pas à revenir sur chaque signalement.

    C'est aussi la seule portée qui réponde à *« quelle part du corpus un humain a-t-il vraiment
    relue ? »* — d'où le fait qu'elle couvre au lieu de s'ajouter."""
    repo = _Repo([_ligne("relu en entier")], detecteurs=("D1", "D3", "D5"))
    relecture = _relecture(repo)

    await relecture.poser(
        UNITE, portee="ensemble", verdict="accepte", note=None, relecteur=KOUASSI
    )

    assert await relecture.file() == []
    assert (await relecture.dossier(UNITE)).unite.relue_en_entier


async def test_le_dossier_ne_masque_pas_ce_que_le_modele_a_ecrit():
    """La signature s'affiche partout, **pour que rien de généré ne se confonde avec une
    relecture**. C'est la raison d'être de `generee` : un relecteur qui ne sait pas qui a écrit
    la ligne ne relit pas, il approuve."""
    repo = _Repo([
        _ligne("pesée générée"),
        _ligne("pesée reprise à la main", axe="ecclesiologie", generee=False),
    ])

    dossier = await _relecture(repo).dossier(UNITE)

    assert dossier.lignes_generees == 1
    assert [ligne.signee_par for ligne in dossier.lignes] == ["ia-mistral", "Kouassi Jean"]


# ================================================================= ce que la surface refuse


async def test_une_portee_qui_n_a_rien_signale_est_refusee():
    """Un verdict sur un détecteur muet aurait l'air d'un travail fait sans faire décroître la
    file d'une unité — c'est le pire des deux mondes : du temps dépensé et rien de mesuré."""
    relecture = _relecture(_Repo([_ligne("…")], detecteurs=("D4",)))

    with pytest.raises(CurationInvalideError, match="D4"):
        await relecture.poser(
            UNITE, portee="D2", verdict="accepte", note=None, relecteur=KOUASSI
        )


async def test_une_unite_disparue_de_la_base_rend_404_et_non_une_file_filtree():
    """La file est une photographie : une unité retirée entre-temps y figure encore. La surface
    doit dire que l'entrée est périmée, pas la faire disparaître en silence."""
    with pytest.raises(UniteIntrouvableError):
        await _relecture(_Repo([_ligne("…")])).dossier(uuid4())


async def test_un_verdict_retire_rend_le_nom_de_qui_l_avait_signe():
    """Un verdict posé à tort ne se répare pas en le **remplaçant** — cela laisserait une
    signature à la place d'une autre. Et la réponse dit qui signait, parce que c'est la seule
    chose qu'on voudra savoir ensuite."""
    repo = _Repo([_ligne("…")])
    relecture = _relecture(repo)
    await relecture.poser(UNITE, portee="D4", verdict="accepte", note=None, relecteur=KOUASSI)

    assert await relecture.retirer(UNITE, "D4") == "Kouassi Jean"
    assert len(await relecture.file()) == 1


# ============================================================ qui signe : prouvé, pas déclaré


class _Registre:
    def __init__(self, connus: dict[str, tuple[str, str]]) -> None:
        self.connus = connus

    async def secret_et_nom(self, identifiant: str) -> tuple[str, str] | None:
        return self.connus.get(identifiant)


async def test_le_registre_rend_un_nom_contre_la_preuve_d_un_secret():
    registre = RegistreDesRelecteurs(
        _Registre({"kouassi": (empreinte_de_secret("s3cr3t"), "Kouassi Jean")})
    )

    assert (await registre.identifier("kouassi:s3cr3t")).nom == "Kouassi Jean"


@pytest.mark.parametrize(
    "porteur",
    [None, "", "kouassi", "kouassi:faux", "inconnu:s3cr3t", "Kouassi Jean"],
    ids=["absent", "vide", "sans secret", "mauvais secret", "inconnu", "un nom, justement"],
)
async def test_rien_d_autre_ne_signe(porteur):
    """🔴 **Le dernier cas est celui qui a mordu.** « Kouassi Jean » est un nom parfaitement
    valide au sens de `verifier_verdict()` — il désigne quelqu'un, ce n'est ni `demo` ni
    `ia-mistral`. Il ne prouve rien pour autant, et c'est exactement par là qu'un verdict a été
    posé au nom du propriétaire du dépôt."""
    registre = RegistreDesRelecteurs(
        _Registre({"kouassi": (empreinte_de_secret("s3cr3t"), "Kouassi Jean")})
    )

    with pytest.raises(RelecteurInconnuError):
        await registre.identifier(porteur)


# ================================================== le dépôt réel, contre une base construite


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connexion:
        await connexion.run_sync(Base.metadata.create_all)
    fabrique = async_sessionmaker(engine, expire_on_commit=False)
    async with fabrique() as ouverte:
        yield ouverte
    await engine.dispose()


async def _semer(session, *, signaux: int = 1) -> UUID:
    version = uuid4()
    session.add(CorpusVersionModel(
        id=version, code="LSG", language="fra", label="Segond 1910",
        translation_kind="formelle", license_kind="domaine_public",
        offline_allowed=True, metered=False, versification="standard",
    ))
    session.add(CorpusBookNameModel(
        book_id=66, language="fr", label="Apocalypse", abbreviations=["Ap"]
    ))
    for verset in (5, 6, 7):
        session.add(CorpusVerseModel(
            version_id=version, book_id=66, chapter=5, verse=verset,
            body=f"verset {verset}", body_norm=f"verset {verset}",
        ))
    unite = uuid4()
    session.add(CorpusPericopeModel(
        id=unite, book_id=66, start_ch=5, start_v=5, end_ch=5, end_v=6,
        label="Le Lion et l'Agneau", rationale="l'unité tient du v. 5 au v. 6",
        source_ref="découpage usuel", reviewed_by="ia-mistral", reviewed_at=_NOW,
    ))
    session.add(CorpusDoctrinalBearingModel(
        pericope_id=unite, axis_code="christologie", strength="dominant",
        rationale="le Lion est l'Agneau immolé", source_ref="lecture suivie",
        reviewed_by="ia-mistral", reviewed_at=_NOW,
    ))
    session.add(CorpusDoctrinalCaveatModel(
        id=uuid4(), pericope_id=unite, axis_code="christologie",
        body="le passage ne décrit pas le mécanisme de l'expiation",
        caveat_kind="exegetique", tradition_scope=None, source_ref="Beale",
        reviewed_by="Kouassi Jean", reviewed_at=_NOW,
    ))
    for rang in range(signaux):
        session.add(CorpusSignalModel(
            id=uuid4(), pericope_id=unite, detector=f"D{rang + 1}",
            label=f"D{rang + 1} aberration", severity=3, detail="8 loci portants",
            body="", scan_fingerprint="z" * 32, scanned_at=_NOW,
        ))
    await session.flush()
    return unite


async def test_le_depot_rend_la_reference_le_passage_et_les_signatures(session):
    """La référence, le texte et les signatures viennent de la base — pas d'un libellé recopié.

    Le passage est servi dans la version **contre laquelle la curation a été écrite** : comparer
    une pesée de la Segond au français de 1744 avait déjà produit treize fausses accusations
    d'invention dans le détecteur d'écarts."""
    unite = await _semer(session)
    depot = SqlRelectureRepository(session)

    (entree,) = await depot.file(limite=10, decalage=0)
    versets = await depot.texte(unite)
    lignes = await depot.lignes(unite)

    assert entree.reference == "Apocalypse 5:5-6"
    assert entree.signature == "ia-mistral"
    assert [(v.chapitre, v.verset) for v in versets] == [(5, 5), (5, 6)]
    assert {ligne.couche for ligne in lignes} == {COUCHE_PESEE, COUCHE_MISE_EN_GARDE}
    assert [ligne.generee for ligne in lignes] == [True, False]


async def test_le_compteur_compte_les_signatures_et_non_les_verdicts(session):
    """⚠️ **La mesure doit rester sévère là où elle sert.**

    Un `accepte` laisse la ligne signée `ia-mistral`, et c'est juste : le relecteur a validé une
    ligne générée, il ne l'a pas écrite. Compter les verdicts dans `lignes_humaines` gonflerait
    le seul chiffre qui dise de combien la promesse est en retard sur le fait."""
    unite = await _semer(session, signaux=2)
    depot = SqlRelectureRepository(session)
    lignes = await depot.lignes(unite)
    await depot.enregistrer_verdict(unite, VerdictPose(
        portee="ensemble", verdict="accepte", note=None, relu_par="Kouassi Jean",
        relu_le=_NOW,
        empreinte_jugee=empreinte_de_curation(
            (ligne.couche, ligne.axe, ligne.corps) for ligne in lignes
        ),
    ))

    compteur = await depot.compteur()

    assert compteur.unites == 1
    assert compteur.unites_relues == 1
    assert compteur.signalements == 2
    assert compteur.signalements_tranches == 2
    assert (compteur.lignes, compteur.lignes_humaines) == (2, 1)
    assert compteur.derniere_analyse is not None


async def test_un_relecteur_revoque_devient_introuvable(session):
    """La révocation n'efface pas la ligne — les verdicts signés doivent continuer de désigner
    quelqu'un — mais elle se comporte comme une absence à l'authentification. Sinon la
    différence entre « révoqué » et « inconnu » fuiterait dans les réponses."""
    session.add(CorpusReviewerModel(
        identifiant="kouassi", display_name="Kouassi Jean",
        secret_hash=empreinte_de_secret("s3cr3t"), active=False,
        enrolled_at=_NOW, revoked_at=_NOW,
    ))
    await session.flush()

    assert await SqlRegistreRepository(session).secret_et_nom("kouassi") is None
