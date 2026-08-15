"""Le service d'étude — **les cinq défauts que l'utilisateur a trouvés, pas la suite**.

Ce fichier n'existait pas, et c'est ce qui a permis à cinq régressions d'atteindre une
démonstration devant un pasteur. Les 1 362 tests couvraient le moteur pur et les lecteurs
d'index ; ni `UrimStudyService`, ni la bordure. Or c'est là que tout se casse — parce que
c'est là que le pur rencontre la base, le réseau et le modèle.

Chaque test ci-dessous porte le nom de ce qu'il a laissé passer :

1. **le 500 sur toutes les ouvertures** — `record_attempt` appelé sans `chosen_ref` ;
2. **le 422 au clic** — une option `origin: sens` que l'étage proposait et que le service
   refusait ;
3. **le bouclage du chemin intention** — l'unité choisie qui n'était plus le passage ;
4. **le refus de ce que personne n'avait relu** — `shape_homiletic` confondant l'absence de
   ligne avec un verdict ;
5. **la saisie stylisée** — les caractères mathématiques envoyés tels quels au modèle ;
6. **le 422 au clic, deuxième fois** — `en_un_seul` au bornage, une option que l'étage émet
   depuis l'origine et que le service n'a jamais su lire.

Aucun ne demande de base ni de réseau. C'est le point : ils auraient tous pu exister avant.

Le sixième dit ce que les cinq premiers laissaient croire résolu : la faute n'est pas un code
oublié, c'est qu'**aucun test ne relisait la liste des options en la rejouant**. Celui-ci le
fait pour son étage, et c'est la seule forme qui vaille — un code se corrige une fois, une
classe de défauts se garde.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.contexts.urim.application.ports import (
    PreparationRecord,
    UsageSnapshot,
)
from app.contexts.urim.application.study_service import UrimStudyService, _lisible
from app.contexts.urim.domain.errors import OptionInconnueError
from app.contexts.urim.engine.deps import AxisBearing, DoctrinalAxis, Feasibility
from app.contexts.urim.engine.stages.bound_pericope import EN_UN_SEUL
from app.contexts.urim.engine.state import AxisGloss, PassageSuggestion, Reference
from app.contexts.urim.infrastructure.corpus.index import (
    CollisionRow,
    CorpusIndex,
    OriginalWord,
    PericopeRow,
    Temoin,
    VerseRow,
    WitnessReading,
)

LOCI = (
    "theologie_propre", "christologie", "pneumatologie", "anthropologie", "hamartiologie",
    "soteriologie", "ecclesiologie", "angelologie", "demonologie", "eschatologie",
)

UNITE = UUID("11111111-2222-3333-4444-555555555555")
EGLISE, AUTEUR = uuid4(), uuid4()
MAINTENANT = datetime(2026, 8, 10, tzinfo=UTC)

#: Hébreux 13:1-6 — l'unité sur laquelle le Pasteur X a buté. Deux versets suffisent à
#: éprouver le service : ce qu'on mesure ici, c'est la bordure, pas l'exégèse.
TEXTE = {
    (58, 13, 1): "Persévérez dans l'amour fraternel.",
    (58, 13, 2): "N'oubliez pas l'hospitalité.",
}


def _index(*, bearings=(), couples=(), temoins=None) -> CorpusIndex:
    unite = PericopeRow(
        UNITE, 58, 13, 1, 13, 2, "Exhortations", "L'unité tient du v. 1 au v. 2.", "ia-mistral"
    )
    return CorpusIndex(
        snapshot="essai", fallback_version_id=uuid4(), metered_versions=frozenset(),
        # ⚠️ `hb` **doit** y être : le vrai corpus l'a appris cette semaine, et une doublure
        # moins capable que lui ferait passer un test pour une preuve. C'est le sigle des
        # notes du Pasteur X.
        books_by_form={("hebreux",): (58,), ("hb",): (58,)},
        forms_by_length=(("hebreux",), ("hb",)),
        label_by_book={58: "Hébreux"}, book_by_label={"Hébreux": 58},
        osis_by_book={58: "Heb"},
        # Le chapitre 2 est tenu **sans ses versets au-delà de 18** : c'est ce qui permet au
        # motif de dire « Hébreux 2 compte 18 versets », comme le vrai corpus le dit.
        chapters_held={58: frozenset({2, 13})},
        max_verse_held={(58, 13): 2, (58, 2): 18},
        # ⚠️ Le lexique **doit** être garni, sinon `route_entry` lit du charabia : il exige au
        # moins un mot reconnu (S34) avant d'accepter une intention. Un index de test à `idf`
        # vide fait donc refuser toute conviction — le banc mentirait sur le moteur.
        idf={mot: 1.0 for mot in (
            "je", "veux", "precher", "sur", "la", "fraternite", "retour",
            "perseverez", "dans", "lamour", "fraternel",
        )},
        postings={},
        verses=tuple(
            VerseRow(b, c, v, corps, frozenset(), tuple(corps.lower().split()))
            for (b, c, v), corps in sorted(TEXTE.items())
        ),
        pericopes=(unite,),
        bearings={UNITE: tuple(bearings)}, caveats={}, notes={},
        couples={UNITE: tuple(couples)}, dominant={},
        axes=tuple(DoctrinalAxis(c, c, i) for i, c in enumerate(LOCI, start=1)),
        temoins=temoins or {},
    )


class _Studies:
    """Le dépôt, **avec la signature exacte du port**.

    ⚠️ C'est tout l'enjeu du fichier : une doublure plus permissive que le vrai dépôt ne
    prouve rien. Le 500 en production venait d'un `record_attempt` appelé sans `chosen_ref`,
    et aucun test ne pouvait l'attraper puisqu'aucun test n'appelait ce chemin."""

    def __init__(self) -> None:
        self.records: dict[UUID, PreparationRecord] = {}
        self.attempts: list[dict] = []
        self.supports: dict[UUID, list] = {}
        self.ecartees: set[tuple[str, str]] = set()
        #: Le mémo des suggestions — une doublure sans lui ferait redemander le modèle à
        #: chaque rejeu, donc mesurerait un service que la production n'a plus.
        self.memos: dict[UUID, object] = {}

    async def add(self, record): self.records[record.id] = record

    async def get(self, study_id): return self.records.get(study_id)

    async def save(self, record): self.records[record.id] = record

    async def record_attempt(
        self, *, study_id, input_hash, candidates, chosen_ref, chosen_by, at
    ) -> None:
        self.attempts.append({"chosen_ref": chosen_ref, "chosen_by": chosen_by})

    async def set_elements(self, study_id, elements): ...

    async def list_elements(self, study_id): return []

    async def set_supports(self, study_id, supports):
        self.supports[study_id] = list(supports)

    async def list_supports(self, study_id):
        return self.supports.get(study_id, [])

    async def dismiss(self, *, study_id, stage_code, option_code, at):
        self.ecartees.add((stage_code, option_code))

    async def restore(self, *, study_id, stage_code, option_code):
        self.ecartees.discard((stage_code, option_code))

    async def list_dismissals(self, study_id): return sorted(self.ecartees)

    async def save_suggestions(self, study_id, snapshot, at):
        self.memos[(study_id, snapshot.input_hash)] = snapshot

    async def get_suggestions(self, study_id, input_hash):
        return self.memos.get((study_id, input_hash))

    async def recently_preached_axes(self, author_id, since): return []


class _Reservations:
    """⚠️ **La signature exacte du port**, ici aussi.

    `usage` a gagné `author_id` le jour où le quota est devenu personnel : sans église, le
    sujet du comptage est le compte, et une doublure restée à deux arguments aurait laissé
    passer un service qui ne compile pas."""

    def __init__(self, *, epuise: bool = False) -> None:
        self.recles: list[str] = []
        self.factures: list[str] = []
        self._epuise = epuise

    async def reserve(self, *, church_id, author_id, pericope_key, at): return uuid4()

    async def rekey_for(self, *, church_id, author_id, provisional_key, pericope_key, at):
        self.recles.append(pericope_key)

    async def mark_assisted(self, *, church_id, author_id, pericope_key, at):
        self.factures.append(pericope_key)

    async def usage(self, church_id, author_id, at):
        return UsageSnapshot(assistance_exhausted=self._epuise)


class _Acces:
    async def ensure_may_prepare(self, *, account_id, church_id) -> None: ...


class _Modele:
    """Un modèle **qui note ce qu'on lui donne** — c'est ce qu'on vérifie au test 5."""

    def __init__(self, *, axes=(), passages=(), flags=(), resolu=None) -> None:
        self._axes, self._passages = tuple(axes), tuple(passages)
        self._flags, self._resolu = tuple(flags), resolu
        self.recu: list[str] = []

    async def resolve(self, text):
        self.recu.append(text)
        return self._resolu

    async def axes(self, text):
        self.recu.append(text)
        return self._axes

    async def lever(self, text):
        self.recu.append(text)
        return self._flags

    async def passages(self, text):
        self.recu.append(text)
        return self._passages


def _service(index=None, modele=None) -> UrimStudyService:
    return UrimStudyService(
        studies=_Studies(), reservations=_Reservations(), access=_Acces(),
        index=index or _index(), clock=lambda: MAINTENANT,
        resolver=modele or _Modele(),
    )


async def _ouvrir(service, saisie: str):
    return await service.open(
        actor_account_id=AUTEUR, church_id=EGLISE, raw_input=saisie
    )


# ================================================================== 1. le 500 des ouvertures


@pytest.mark.asyncio
async def test_ouvrir_enregistre_la_tentative_avec_sa_reference():
    """🔴 **Toutes les ouvertures rendaient 500.**

    `record_attempt` était appelé sans `chosen_ref` — un argument obligatoire du port. La
    faute a survécu à `ruff` et aux 192 tests du moteur, et n'a été trouvée qu'en ouvrant une
    préparation depuis Thunder."""
    service = _service()

    dto = await _ouvrir(service, "Hébreux 13:1")

    assert dto.record.resolved_ref is not None
    (tentative,) = service.studies.attempts
    assert tentative["chosen_ref"] == dto.record.resolved_ref
    assert tentative["chosen_by"] == "moteur"


# =============================================================== 2. le 422 au clic sur « sens »


@pytest.mark.asyncio
async def test_un_passage_propose_par_le_sens_se_choisit_a_l_etage_de_la_conviction():
    """🔴 **Le clic tombait en 422.**

    En ajoutant les passages du modèle à l'écran des axes, j'ai créé des options dont le code
    est le libellé — « Hébreux 13:1-2 », sans préfixe — alors que l'étage n'acceptait que
    `axe:` et `texte:<uuid>`. La réponse était juste ; c'est le coup d'après qui échouait, et
    aucun test ne jouait le coup d'après."""
    modele = _Modele(passages=(
        PassageSuggestion(Reference("Hébreux", 13, 1, 2), "traite ce sujet"),
        PassageSuggestion(Reference("Hébreux", 13, 1, 1), "aussi"),
    ))
    service = _service(modele=modele)
    dto = await _ouvrir(service, "je veux prêcher sur la fraternité")
    assert dto.entry_mode == "conviction"

    apres = await service.decide(
        actor_account_id=AUTEUR, study_id=dto.record.id,
        stage_code="weigh_conviction", option_code="Hébreux 13:1-2",
    )

    assert apres.resolved_label == "Hébreux 13:1-2"


# ================================================================ 3. le bouclage de l'intention


@pytest.mark.asyncio
async def test_l_unite_choisie_reste_le_passage_au_rejeu():
    """🔴 **Le chemin conviction bouclait sur l'écran des axes.**

    Il n'existe pas de colonne `resolved_ref` : la référence se **déduit** de la péricope, et
    `resolved` ne la déduisait pas. Le chemin référence masquait le trou en reparsant sa
    saisie à chaque rejeu ; une intention ne se reparse pas."""
    service = _service()
    dto = await _ouvrir(service, "je veux prêcher sur la fraternité")
    record = service.studies.records[dto.record.id]
    record.entry_mode = "conviction"
    record.resolved_ref = None
    record.pericope_id = UNITE

    relu = await service.get(actor_account_id=AUTEUR, study_id=record.id)

    assert relu.resolved_label == "Hébreux 13:1-2"
    assert "weigh_conviction" not in [code for code, _ in relu.trace]


# ====================================================== 4. le refus de ce que nul n'a relu


@pytest.mark.asyncio
async def test_une_faisabilite_jamais_relue_degrade_au_lieu_de_refuser():
    """🔴 **Ajouter de la curation rendait la sortie pire.**

    Sans péricope, l'étage dégradait et continuait. Avec une péricope pesée mais sans
    faisabilité relue, il refusait — « aucune mise en forme n'est faisable sur cette unité »
    — alors que personne n'avait regardé.

        aucune ligne  →  personne n'a encore regardé
        que des refus →  quelqu'un a regardé, et rien ne tient

    Quand une amélioration de données rend une sortie plus sévère, ce n'est pas de la rigueur :
    c'est une confusion entre le silence et le verdict."""
    pesees = (AxisBearing("anthropologie", "Anthropologie", "dominant", "le sujet"),)
    service = _service(index=_index(bearings=pesees))
    dto = await _ouvrir(service, "Hébreux 13:1-2")

    assert dto.outcome != "refuse"
    motifs = dict(dto.trace)
    assert "n'a encore été relue" in motifs["shape_homiletic"]


@pytest.mark.asyncio
async def test_une_faisabilite_relue_et_toute_refusee_refuse_bel_et_bien():
    """L'autre moitié : quelqu'un **a** regardé, et rien ne tient. Le refus est alors un fait
    curé, et il porte son motif."""
    pesees = (AxisBearing("anthropologie", "Anthropologie", "dominant", "le sujet"),)
    couples = (
        Feasibility("expositif", "biographique", False, "aucun personnage", "eleve"),
    )
    service = _service(index=_index(bearings=pesees, couples=couples))

    dto = await _ouvrir(service, "Hébreux 13:1-2")

    assert dto.outcome == "refuse"
    assert "aucun personnage" in dto.rationale


# ============================================ 4-bis. le couple que personne n'a jamais vérifié


@pytest.mark.asyncio
async def test_un_couple_invente_n_atteint_pas_le_theme():
    """🔴 **Trouvé en marchant l'arbre, sur un sermon pentecôtiste.**

    `shape_homiletic.applies()` exige `subject_matter is None` ; la décision écrivait les deux
    champs d'un coup, donc l'étage ne se ré-exécutait plus jamais et sa validation devenait
    injoignable. `abracadabra:sur-mesure` traversait tout le pipeline et ressortait dans le
    thème rendu au pasteur : *« pneumatologie, en abracadabra sur-mesure »*.

    C'est le miroir exact du 422 au clic : là, l'étage proposait ce que le service refusait ;
    ici, le service accepte ce que l'étage aurait refusé."""
    pesees = (AxisBearing("anthropologie", "Anthropologie", "dominant", "le sujet"),)
    couples = (Feasibility("expositif", "doctrinal", True, "", "faible"),)
    service = _service(index=_index(bearings=pesees, couples=couples))
    dto = await _ouvrir(service, "Hébreux 13:1-2")

    with pytest.raises(OptionInconnueError):
        await service.decide(
            actor_account_id=AUTEUR, study_id=dto.record.id,
            stage_code="shape_homiletic", option_code="abracadabra:sur-mesure",
        )

    relu = await service.get(actor_account_id=AUTEUR, study_id=dto.record.id)
    assert "abracadabra" not in (relu.record.theme or "")


@pytest.mark.asyncio
async def test_un_couple_refuse_par_la_curation_est_refuse_avec_son_motif_a_lui():
    """⚠️ **Le motif est celui du texte, pas celui du logiciel** (S19).

    *« ce passage ne porte aucun personnage »* apprend quelque chose au pasteur ; *« option
    inconnue »* le laisse chercher ce qu'il a mal cliqué. La curation a déjà écrit la phrase,
    on la sert."""
    pesees = (AxisBearing("anthropologie", "Anthropologie", "dominant", "le sujet"),)
    couples = (
        Feasibility("expositif", "doctrinal", True, "", "faible"),
        Feasibility("textuel", "biographique", False, "aucun personnage nommé", "moyen"),
    )
    service = _service(index=_index(bearings=pesees, couples=couples))
    dto = await _ouvrir(service, "Hébreux 13:1-2")

    with pytest.raises(OptionInconnueError, match="aucun personnage nommé"):
        await service.decide(
            actor_account_id=AUTEUR, study_id=dto.record.id,
            stage_code="shape_homiletic", option_code="textuel:biographique",
        )


@pytest.mark.asyncio
async def test_un_couple_offert_se_choisit_toujours():
    """La sévérité ne doit pas fermer la porte qu'on vient d'ouvrir : ce que l'étage propose
    doit rester cliquable. C'est la moitié du test qui manquait au 422 au clic."""
    pesees = (AxisBearing("anthropologie", "Anthropologie", "dominant", "le sujet"),)
    couples = (Feasibility("expositif", "doctrinal", True, "", "faible"),)
    service = _service(index=_index(bearings=pesees, couples=couples))
    dto = await _ouvrir(service, "Hébreux 13:1-2")
    offert = next(o[0] for o in dto.options)

    apres = await service.decide(
        actor_account_id=AUTEUR, study_id=dto.record.id,
        stage_code="shape_homiletic", option_code=offert,
    )

    assert apres.record.theme


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("etage", "code"),
    [("bear_axes", "abracadabra"), ("weigh_conviction", "axe:abracadabra")],
)
async def test_un_axe_invente_n_atteint_pas_la_preparation(etage: str, code: str):
    """🔴 **Deux étages écrivent `axis_code`, et aucun ne vérifiait.**

    Trouvé en marchant un sermon orthodoxe : un texte à un seul axe dominant pose l'axe
    d'office, et la seule façon de le redresser — `POST /decisions` sur `bear_axes` — acceptait
    n'importe quelle chaîne. `abracadabra` devenait l'axe doctrinal, puis le thème.

    ⚠️ La garde porte sur **les dix loci**, pas sur ce que l'unité porte : prêcher un texte sur
    un axe qu'il soutient sans en faire son sujet reste possible, et c'est délibéré."""
    service = _service()
    dto = await _ouvrir(service, "Hébreux 13:1-2")

    with pytest.raises(OptionInconnueError, match="axes doctrinaux"):
        await service.decide(
            actor_account_id=AUTEUR, study_id=dto.record.id,
            stage_code=etage, option_code=code,
        )


@pytest.mark.asyncio
async def test_un_axe_que_le_texte_soutient_reste_choisissable():
    """La porte de sortie du pasteur dont l'angle n'est pas celui du corpus.

    2 Pierre 1:4 a `christologie` pour seul dominant ; il porte aussi l'anthropologie. Le
    pasteur qui l'ouvre **pour** la déification doit pouvoir le dire — l'étage existe pour ne
    pas décider à sa place."""
    service = _service()
    dto = await _ouvrir(service, "Hébreux 13:1-2")

    apres = await service.decide(
        actor_account_id=AUTEUR, study_id=dto.record.id,
        stage_code="bear_axes", option_code="anthropologie",
    )

    assert apres.record.axis_code == "anthropologie"


# ================================== 4-ter. la cascade — une décision amont périme l'aval


#: Une unité pesée et faisable : de quoi mener une préparation jusqu'au thème, puis la reprendre.
_PESEES = (
    AxisBearing("christologie", "Christologie", "dominant", "le sujet du texte"),
    AxisBearing("anthropologie", "Anthropologie", "porte", "le texte le soutient"),
)
_COUPLES = (
    Feasibility("expositif", "doctrinal", True, "", "faible"),
    Feasibility("textuel", "doctrinal", True, "", "faible"),
)


async def _jusqu_au_theme(service):
    """Ouvrir, choisir une mise en forme, et obtenir le thème — la préparation aboutie."""
    dto = await _ouvrir(service, "Hébreux 13:1-2")
    dto = await service.decide(
        actor_account_id=AUTEUR, study_id=dto.record.id,
        stage_code="shape_homiletic", option_code="expositif:doctrinal",
    )
    assert dto.record.theme == "christologie, en expositif doctrinal"
    return dto


@pytest.mark.asyncio
async def test_changer_l_axe_fait_suivre_le_theme():
    """🔴 **Le rejeu ne rejouait que ce que personne n'avait décidé.**

    L'axe, le couple, les bornes et le thème sont stockés comme des **résultats**, et chaque
    étage qui les produit se garde de tourner deux fois (`applies`). Une décision amont ne
    remontait donc jamais l'aval : le pasteur redressait son axe et emportait en chaire un
    thème qui nommait l'ancien."""
    service = _service(index=_index(bearings=_PESEES, couples=_COUPLES))
    dto = await _jusqu_au_theme(service)

    apres = await service.decide(
        actor_account_id=AUTEUR, study_id=dto.record.id,
        stage_code="bear_axes", option_code="anthropologie",
    )

    assert apres.record.theme == "anthropologie, en expositif doctrinal"


@pytest.mark.asyncio
async def test_changer_le_couple_fait_suivre_le_theme():
    """Le thème nommait la mise en forme que le pasteur venait précisément d'abandonner."""
    service = _service(index=_index(bearings=_PESEES, couples=_COUPLES))
    dto = await _jusqu_au_theme(service)

    apres = await service.decide(
        actor_account_id=AUTEUR, study_id=dto.record.id,
        stage_code="shape_homiletic", option_code="textuel:doctrinal",
    )

    assert apres.record.theme == "christologie, en textuel doctrinal"


@pytest.mark.asyncio
async def test_forcer_ses_bornes_emporte_la_faisabilite_mais_pas_l_angle():
    """**S22 devient enfin mécanique.** *« La liberté accordée se propage d'elle-même, sans
    qu'aucun étage n'ait à connaître la règle. »* Elle ne se propageait pas du tout : le couple
    et le thème tirés de l'unité abandonnée lui survivaient.

    L'axe, lui, reste — c'est un angle doctrinal, il ne dépend pas des bornes, et sur le chemin
    intention c'est le pasteur qui l'a nommé avant même de voir un texte."""
    service = _service(index=_index(bearings=_PESEES, couples=_COUPLES))
    dto = await _jusqu_au_theme(service)

    apres = await service.decide(
        actor_account_id=AUTEUR, study_id=dto.record.id,
        stage_code="bound_pericope", option_code="tel_quel",
    )

    assert apres.record.pericope_id is None
    assert apres.record.plan_source is None and apres.record.subject_matter is None
    assert apres.record.axis_code == "christologie", "l'angle du pasteur a été emporté"
    # Le thème est reproposé **sans** faisabilité : c'est la branche que `propose_theme`
    # déclarait inatteignable, et que la cascade vient d'ouvrir.
    assert apres.record.theme == "christologie"
    assert "aucune faisabilité relue" in dict(apres.trace)["propose_theme"]


@pytest.mark.asyncio
async def test_changer_de_texte_perime_tout_l_aval():
    """Un autre passage, c'est une autre unité, d'autres pesées, une autre faisabilité. Ce qui
    en était tiré ne vaut plus rien — et le pipeline le recalcule au lieu de le charrier."""
    service = _service(index=_index(bearings=_PESEES, couples=_COUPLES))
    dto = await _jusqu_au_theme(service)

    apres = await service.decide(
        actor_account_id=AUTEUR, study_id=dto.record.id,
        stage_code="resolve_passage", option_code="Hébreux 13:1",
    )

    assert apres.record.axis_code is None
    assert apres.record.plan_source is None
    assert apres.record.theme is None


@pytest.mark.asyncio
async def test_sur_le_chemin_inverse_changer_de_texte_ne_reprend_pas_son_angle():
    """⚠️ **La subtilité de la cascade, et elle vient du chemin inversé.**

    Sur une intention, l'ordre est renversé : le pasteur nomme son **axe** avant qu'aucun texte
    n'existe, puis choisit un texte qui le porte. Périmer l'axe avec le reste lui reprendrait la
    seule chose qu'il ait dite — et le renverrait à l'écran des dix loci qu'il vient de quitter.

    Le couple et le thème tombent, eux : ils étaient tirés de l'unité qu'il abandonne."""
    service = _service(index=_index(bearings=_PESEES, couples=_COUPLES))
    dto = await _ouvrir(service, "je veux prêcher sur la fraternité")
    assert dto.entry_mode == "conviction"

    for etage, option in (
        ("weigh_conviction", "axe:anthropologie"),
        ("weigh_conviction", f"texte:{UNITE}"),
        ("shape_homiletic", "expositif:doctrinal"),
    ):
        dto = await service.decide(
            actor_account_id=AUTEUR, study_id=dto.record.id,
            stage_code=etage, option_code=option,
        )
    assert dto.record.theme == "anthropologie, en expositif doctrinal"

    apres = await service.decide(
        actor_account_id=AUTEUR, study_id=dto.record.id,
        stage_code="weigh_conviction", option_code=f"texte:{UNITE}",
    )

    assert apres.record.axis_code == "anthropologie", "son angle lui a été repris"
    assert apres.record.plan_source is None
    assert apres.record.theme != "anthropologie, en expositif doctrinal"


@pytest.mark.asyncio
async def test_le_theme_reecrit_par_le_pasteur_ne_se_perime_jamais():
    """⚠️ **C'est son sermon** — *une proposition, jamais un titre ; le titre, c'est votre voix.*

    On ne distingue pas une phrase du pasteur d'une phrase du moteur par une colonne : le
    gabarit est déterministe, donc l'égalité suffit à dire que personne n'y a touché. Même ruse
    que `_une_unite_existait`, qui repose la question au corpus plutôt que d'ajouter un champ
    qui pourrait le contredire."""
    service = _service(index=_index(bearings=_PESEES, couples=_COUPLES))
    dto = await _jusqu_au_theme(service)
    sien = "L'amour sans masque — ce que l'Église se doit les uns aux autres"
    await service.decide(
        actor_account_id=AUTEUR, study_id=dto.record.id,
        stage_code="propose_theme", option_code=sien,
    )

    apres = await service.decide(
        actor_account_id=AUTEUR, study_id=dto.record.id,
        stage_code="bear_axes", option_code="anthropologie",
    )

    assert apres.record.theme == sien
    assert apres.record.axis_code == "anthropologie"


# ================================================================ la chaîne de textes d'appui


@pytest.mark.asyncio
async def test_une_reference_illisible_n_interrompt_pas_la_chaine():
    """🔴 **La vraie faute du Pasteur X, et pourquoi elle n'avait jamais été vue.**

    Ses notes portaient `Hb 2v29` — Hébreux 2 compte 18 versets. Urim savait le dire depuis le
    premier jour et ne l'avait jamais dit : il ne soumettait que son passage principal, pas ses
    douze appuis.

    Et le refus **n'interrompt rien** (S19) : la saisie fautive reste dans la liste avec son
    motif, à côté des justes. Refuser les douze pour une faute de frappe ferait perdre onze
    textes bons — c'est le contraire du service rendu."""
    service = _service()
    dto = await _ouvrir(service, "Hébreux 13:1")

    apres = await service.set_supports(
        actor_account_id=AUTEUR, study_id=dto.record.id,
        saisies=["Hébreux 13:2", "Hb 2v29", "Zorobabel 3:5"],
    )

    assert len(apres.supports) == 3, "une saisie fautive ne doit pas disparaître"
    (_, ref_bonne, texte, motif_bon) = apres.supports[0]
    assert ref_bonne == "Hébreux 13:2" and "hospitalité" in texte and motif_bon == ""

    (brut, ref, _, motif) = apres.supports[1]
    assert brut == "Hb 2v29" and ref == ""
    assert "18 versets" in motif, "le motif nomme ce qui manque AU CORPUS"

    (_, _, _, inconnu) = apres.supports[2]
    assert "Zorobabel" in inconnu


@pytest.mark.asyncio
async def test_la_chaine_garde_l_ordre_du_pasteur():
    """L'ordre porte la progression du sermon — l'annonce avant l'accomplissement. Retrier
    dans l'ordre du canon déferait son plan."""
    service = _service()
    dto = await _ouvrir(service, "Hébreux 13:1")

    apres = await service.set_supports(
        actor_account_id=AUTEUR, study_id=dto.record.id,
        saisies=["Hébreux 13:2", "Hébreux 13:1"],
    )

    assert [ref for _, ref, _, _ in apres.supports] == ["Hébreux 13:2", "Hébreux 13:1"]


# ============================================================ la concordance — le module recherche


def _index_avec_original() -> CorpusIndex:
    """Deux occurrences d'un même lemme, et un `total` supérieur à ce qu'on rendra."""
    index = _index()
    mots = {
        (58, 13, 1): (OriginalWord(1, "ἀγάπη", "ἀγάπη", "N-", "----NSF-", "grc"),),
        (58, 13, 2): (OriginalWord(1, "ἀγάπης", "ἀγάπη", "N-", "----GSF-", "grc"),),
    }
    return replace(
        index,
        originals=mots,
        occurrences_by_lemma={"ἀγάπη": ((58, 13, 1, 0), (58, 13, 2, 0))},
    )


@pytest.mark.asyncio
async def test_la_concordance_rend_le_texte_francais_avec_la_forme_originale():
    """**La seule réponse du module de recherche qui ne puisse rien inventer.**

    Le pasteur qui voit `ὑπόδημα` dans Luc 15:22 veut savoir ce que le mot porte. Une note
    historique le lui dirait et pourrait se tromper sans que personne ne le vérifie ; la
    concordance ne fait que montrer le texte."""
    service = _service(index=_index_avec_original())

    dto = await service.concordance(
        actor_account_id=AUTEUR, church_id=EGLISE, lemme="ἀγάπη"
    )

    assert dto.total == 2
    assert dto.language == "grc"
    references = [reference for reference, *_ in dto.occurrences]
    assert references == ["Hébreux 13:1", "Hébreux 13:2"]
    (_, texte, surface, _) = dto.occurrences[0]
    assert "amour fraternel" in texte and surface == "ἀγάπη"


@pytest.mark.asyncio
async def test_un_lemme_absent_dit_qu_il_ne_parait_nulle_part():
    """Le refus nomme ce qui manque **au corpus**, pas au pasteur — et l'AT n'a pas encore
    d'original, donc l'absence sera fréquente."""
    service = _service(index=_index_avec_original())

    with pytest.raises(OptionInconnueError, match="ne paraît dans aucun"):
        await service.concordance(
            actor_account_id=AUTEUR, church_id=EGLISE, lemme="ὑπόδημα"
        )


# ====================================================== les collisions, servies au passage


def _index_avec_collision() -> CorpusIndex:
    """Une collision sur Hébreux 13:2, et une autre sur un verset qu'on ne sert pas."""
    lues = (
        WitnessReading("LSG", "accorde", "eclectique", "Segond 1910", None,
                       "N'oubliez pas l'hospitalité."),
        WitnessReading("DARBY", "diverge", "critique", "Darby", "hospitalier",
                       "N'oubliez pas l'hospitalité fraternelle."),
        WitnessReading("MARTIN", "muet", "texte_recu", "Martin 1744", None, ""),
    )
    return replace(_index(), collisions={
        (58, 13, 2): (CollisionRow(58, 13, 2, "lhospitalite", "temoin_isole", lues),),
        (58, 13, 9): (CollisionRow(58, 13, 9, "doctrines", "partage", lues),),
    })


@pytest.mark.asyncio
async def test_les_collisions_suivent_le_texte_servi_et_pas_l_unite():
    """Même règle que les mots de l'original : on annote **ce qu'on affiche**.

    Une collision qui traîne ailleurs dans l'unité parlerait d'un verset que le pasteur n'a pas
    sous les yeux — il irait chercher un désaccord là où son écran ne montre rien."""
    service = _service(index=_index_avec_collision())

    dto = await service.explorer(
        actor_account_id=AUTEUR, church_id=EGLISE, reference="Hébreux 13:2"
    )

    [collision] = dto.collisions
    assert collision.reference == "Hébreux 13:2"
    assert collision.word == "lhospitalite"
    assert [(t.code, t.stance) for t in collision.witnesses] == [
        ("LSG", "accorde"), ("DARBY", "diverge"), ("MARTIN", "muet")
    ]


@pytest.mark.asyncio
async def test_un_passage_sans_collision_n_en_invente_aucune():
    """La très grande majorité des passages n'en portent pas, et c'est l'état normal.

    Seuls les 5 % où le désaccord pèse le plus lourd sont retenus — *rien plutôt qu'une
    vraisemblance.* Un écran vide ici ne signale pas une panne."""
    service = _service(index=_index_avec_collision())

    dto = await service.explorer(
        actor_account_id=AUTEUR, church_id=EGLISE, reference="Hébreux 13:1"
    )

    assert dto.collisions == ()


# ================================================================= 5. la saisie stylisée


def test_les_caracteres_mathematiques_sont_replies_avant_le_modele():
    """🔴 **Le pasteur écrivait depuis WhatsApp.**

    Le moteur s'accommode des caractères mathématiques — son normaliseur les replie. Le
    modèle non : sur la version stylisée il rendait Actes 2, Éphésiens 2, 1 Pierre 2 ; sur la
    même phrase en caractères ordinaires, **Actes 1:8 en premier**, le texte que le pasteur a
    réellement prêché.

    On ne passe pas par `normalize` du moteur : elle dépouille accents et casse, ce qui sert à
    comparer des tokens et nuit à un modèle de langue — il lit du français, pas des clés."""
    par = "\U0001d443\U0001d44e\U0001d45f"
    le = "\U0001d459\U0001d452"

    assert _lisible(f"{par} {le}") == "Par le"
    # Les accents sont **recomposés**, pas retirés : « été » reste « été ».
    assert _lisible("été") == "été"


@pytest.mark.asyncio
async def test_le_modele_recoit_la_saisie_repliee_pas_la_brute():
    stylise = "\U0001d45f\U0001d452\U0001d461\U0001d45c\U0001d462\U0001d45f"  # « retour »
    modele = _Modele(axes=(AxisGloss("christologie", "Le retour", "…"),))
    service = _service(modele=modele)

    await _ouvrir(service, stylise)

    assert modele.recu, "le modèle n'a pas été consulté"
    assert all(recu == "retour" for recu in modele.recu)


# --- le numéro que le verset porte ailleurs -------------------------------------
#
# Le pasteur prépare sur la Segond et ouvre en chaire la Bible de son assemblée. Les deux
# références sont bien formées, donc rien ne l'avertirait — c'est ce silence-là qu'on casse,
# et seulement là où il coûte quelque chose.


def test_le_verset_dit_ou_un_autre_temoin_le_range():
    """Le cas d'Exode 7:26, transposé sur l'unité du banc : le numéro change, on le dit."""
    service = _service(_index(temoins={
        "OST": Temoin("OST", {(58, 13): frozenset({5})}, {(58, 13, 1): (13, 5)}),
    }))

    ailleurs = service._ailleurs(58, 13, 1)

    assert [(a.version, a.reference) for a in ailleurs] == [("OST", "13:5")]


def test_la_concordance_reste_silencieuse():
    """🔴 **Le silence est la réponse ordinaire, et c'est voulu.**

    La numérotation concorde sur la quasi-totalité du corpus. Annoncer « Ostervald : 13:1 »
    sous chaque verset enterrerait les quelques centaines d'endroits où elle ne concorde pas —
    c'est-à-dire exactement ceux pour lesquels ce champ existe."""
    service = _service(_index(temoins={
        "OST": Temoin("OST", {(58, 13): frozenset({1, 2})}, {}),
    }))

    assert service._ailleurs(58, 13, 1) == ()


def test_un_temoin_qui_ne_porte_pas_le_verset_le_dit():
    """Darby n'a pas Actes 8:37, que le texte critique ne retient pas.

    Se taire laisserait le pasteur chercher dans son livre quelque chose qui n'y est pas ;
    l'annoncer absent est une information, pas une panne."""
    service = _service(_index(temoins={
        "DARBY": Temoin("DARBY", {(58, 13): frozenset({2})}, {}),
    }))

    ailleurs = service._ailleurs(58, 13, 1)

    assert [(a.version, a.reference) for a in ailleurs] == [("DARBY", None)]

# ============================================== 6. le 422 au clic, deuxième fois — le bornage


UNITE_1 = UUID("aaaaaaaa-1111-1111-1111-aaaaaaaaaaaa")
UNITE_2 = UUID("bbbbbbbb-2222-2222-2222-bbbbbbbbbbbb")

def _index_a_deux_unites() -> CorpusIndex:
    """Hébreux 13 curé en **deux** unités — le cas d'école `Galates 5`, à l'échelle du banc.

    Une demande qui *englobe*, donc N + 1 options : c'est la seule branche du bornage que le
    service n'avait jamais eu à relire, et l'index à une unité ne pouvait pas l'atteindre."""
    return replace(
        _index(),
        pericopes=(
            PericopeRow(
                UNITE_1, 58, 13, 1, 13, 1, "Amour fraternel",
                "L'exhortation tient seule.", "ia-mistral",
            ),
            PericopeRow(
                UNITE_2, 58, 13, 2, 13, 2, "Hospitalité",
                "Le v. 2 ouvre un autre motif.", "ia-mistral",
            ),
        ),
    )


@pytest.mark.asyncio
async def test_chaque_code_propose_par_le_bornage_est_accepte_par_le_service():
    """🔴 **Le même défaut que le test 2, à un autre étage — et il courait depuis l'origine.**

    L'étage 2 émet `en_un_seul` dès que la demande couvre plusieurs unités ; `_appliquer` ne
    connaissait que `tel_quel` et un UUID, donc `UUID("en_un_seul")` → 422 au clic. Une option
    affichée, motivée, et refusée au moment de la choisir.

    Ce test ne vérifie pas *une* option : il **relit celles que l'étage vient d'émettre** et les
    rejoue toutes. C'est la seule forme qui protège de la classe entière — une option ajoutée
    demain au bornage tombera ici, et non devant un pasteur."""
    index = _index_a_deux_unites()
    ouverte = await _ouvrir(_service(index), "Hébreux 13")

    assert ouverte.trace[-1][0] == "bound_pericope", "le banc ne joue pas la bonne branche"
    codes = [code for code, *_ in ouverte.options]
    assert {str(UNITE_1), str(UNITE_2), EN_UN_SEUL} == set(codes)

    for code in codes:
        service = _service(index)
        dto = await _ouvrir(service, "Hébreux 13")

        apres = await service.decide(
            actor_account_id=AUTEUR, study_id=dto.record.id,
            stage_code="bound_pericope", option_code=code,
        )

        # Accepté **et** tranché : l'étage ne s'applique plus, donc il ne repose pas sa
        # question au tour suivant. Un code avalé sans rien écrire passerait le premier
        # critère et laisserait le pasteur tourner en rond.
        assert "bound_pericope" not in [etage for etage, _ in apres.trace], code


@pytest.mark.asyncio
async def test_le_tout_en_un_seul_sermon_garde_la_demande_entiere():
    """**Ce que « le tout, en un seul sermon » écrit — et pourquoi ce n'est pas une évidence.**

    Aucune des N unités ne peut porter ce sermon-là : en retenir une attacherait au tout la
    relecture d'un tiers du texte, sans que rien ne le dise. `pericope_id` retombe donc à None
    et le drapeau de bornage est vrai — la demande du pasteur l'emporte sur ce que la curation
    proposait, et S22 devient mécanique : plus rien de curé n'est lisible en aval.

    ⚠️ **Et le texte servi est celui qu'il a demandé, entier.** « Hébreux 13 » n'a pas de
    verset (S7) : la présentation le lisait comme un verset unique et rendait 13:1 — « le tout »
    aurait rendu la première ligne du tout."""
    service = _service(_index_a_deux_unites())
    dto = await _ouvrir(service, "Hébreux 13")

    apres = await service.decide(
        actor_account_id=AUTEUR, study_id=dto.record.id,
        stage_code="bound_pericope", option_code=EN_UN_SEUL,
    )

    assert apres.record.pericope_id is None
    assert apres.record.bounds_overridden is True
    assert apres.pericope_label is None, "aucune unité ne signe un sermon sur l'ensemble"
    assert [v.reference for v in apres.verses] == ["Hébreux 13:1", "Hébreux 13:2"]

    # Le rejeu repart des colonnes, pas de la décision : c'est là que les bornes se
    # reconstituent, et une reconstitution fautive ne se verrait qu'au tour suivant.
    relu = await service.get(actor_account_id=AUTEUR, study_id=dto.record.id)
    assert [v.reference for v in relu.verses] == ["Hébreux 13:1", "Hébreux 13:2"]


@pytest.mark.asyncio
async def test_choisir_une_unite_ne_sert_que_cette_unite():
    """L'autre branche, pour que la précédente prouve quelque chose.

    Si les deux options rendaient le même texte, l'écran ne proposerait qu'un choix apparent."""
    service = _service(_index_a_deux_unites())
    dto = await _ouvrir(service, "Hébreux 13")

    apres = await service.decide(
        actor_account_id=AUTEUR, study_id=dto.record.id,
        stage_code="bound_pericope", option_code=str(UNITE_2),
    )

    assert apres.record.pericope_id == UNITE_2
    assert apres.record.bounds_overridden is False
    assert [v.reference for v in apres.verses] == ["Hébreux 13:2"]
