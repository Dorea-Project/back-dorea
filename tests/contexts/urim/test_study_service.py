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
    Temoin,
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
