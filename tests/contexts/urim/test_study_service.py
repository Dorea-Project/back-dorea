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
5. **la saisie stylisée** — les caractères mathématiques envoyés tels quels au modèle.

Aucun ne demande de base ni de réseau. C'est le point : ils auraient tous pu exister avant.
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
from app.contexts.urim.engine.state import AxisGloss, PassageSuggestion, Reference
from app.contexts.urim.infrastructure.corpus.index import (
    CorpusIndex,
    OriginalWord,
    PericopeRow,
    VerseRow,
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


def _index(*, bearings=(), couples=()) -> CorpusIndex:
    unite = PericopeRow(
        UNITE, 58, 13, 1, 13, 2, "Exhortations", "L'unité tient du v. 1 au v. 2.", "ia-mistral"
    )
    return CorpusIndex(
        snapshot="essai", fallback_version_id=uuid4(), metered_versions=frozenset(),
        books_by_form={("hebreux",): (58,)}, forms_by_length=(("hebreux",),),
        label_by_book={58: "Hébreux"}, book_by_label={"Hébreux": 58},
        osis_by_book={58: "Heb"},
        chapters_held={58: frozenset({13})}, max_verse_held={(58, 13): 2},
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
    )


class _Studies:
    """Le dépôt, **avec la signature exacte du port**.

    ⚠️ C'est tout l'enjeu du fichier : une doublure plus permissive que le vrai dépôt ne
    prouve rien. Le 500 en production venait d'un `record_attempt` appelé sans `chosen_ref`,
    et aucun test ne pouvait l'attraper puisqu'aucun test n'appelait ce chemin."""

    def __init__(self) -> None:
        self.records: dict[UUID, PreparationRecord] = {}
        self.attempts: list[dict] = []

    async def add(self, record): self.records[record.id] = record

    async def get(self, study_id): return self.records.get(study_id)

    async def save(self, record): self.records[record.id] = record

    async def record_attempt(
        self, *, study_id, input_hash, candidates, chosen_ref, chosen_by, at
    ) -> None:
        self.attempts.append({"chosen_ref": chosen_ref, "chosen_by": chosen_by})

    async def set_elements(self, study_id, elements): ...

    async def list_elements(self, study_id): return []

    async def recently_preached_axes(self, author_id, since): return []


class _Reservations:
    def __init__(self) -> None:
        self.recles: list[str] = []

    async def reserve(self, *, church_id, author_id, pericope_key, at): return uuid4()

    async def rekey_for(self, *, church_id, author_id, provisional_key, pericope_key, at):
        self.recles.append(pericope_key)

    async def usage(self, church_id, at): return UsageSnapshot()


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
