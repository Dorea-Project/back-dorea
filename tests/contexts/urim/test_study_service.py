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

La sixième section n'est pas un défaut trouvé mais une surface neuve — le **tour de parole**
(trou 2 du contrat). Elle est ici parce que c'est le même endroit qui se casse : la liaison, le
plafond et le rejeu se rencontrent dans la bordure, pas dans le moteur.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.contexts.urim.application.conversation import lire_la_notation
from app.contexts.urim.application.ports import (
    PreparationRecord,
    StudyDTO,
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

    def __init__(
        self, *, axes=(), passages=(), flags=(), resolu=None, intention=None
    ) -> None:
        self._axes, self._passages = tuple(axes), tuple(passages)
        self._flags, self._resolu = tuple(flags), resolu
        self._intention = intention
        self.recu: list[str] = []
        #: Compté à part : le tour de parole doit pouvoir prouver qu'il **n'a pas** aiguillé,
        #: et le rejeu qui l'entoure consulte le modèle par d'autres portes.
        self.aiguillages: list[str] = []

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

    async def aiguiller(self, text):
        self.aiguillages.append(text)
        return self._intention


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


# ============================================== 6. le tour de parole — le trou 2 du contrat


@pytest.mark.asyncio
async def test_une_phrase_qui_designe_un_passage_affiche_le_choisit_sans_aiguiller():
    """🔴 **Le tour que le modèle n'a pas à voir.**

    « Ecclésiologie », « L'unité », « Hébreux 13:1-2 » désignent une option déjà offerte. Un
    tour qui atteint le modèle alors que la liaison pouvait répondre est un défaut : le
    scénario du 12/08 a payé neuf appels pour trois refus, et l'aiguilleur ne savait de toute
    façon pas **quelle** option était visée."""
    modele = _Modele(passages=(
        PassageSuggestion(Reference("Hébreux", 13, 1, 2), "traite ce sujet"),
        PassageSuggestion(Reference("Hébreux", 13, 1, 1), "aussi"),
    ))
    service = _service(modele=modele)
    dto = await _ouvrir(service, "je veux prêcher sur la fraternité")

    apres = await service.dire(
        actor_account_id=AUTEUR, study_id=dto.record.id, raw_input="Hébreux 13:1-2"
    )

    assert apres.resolved_label == "Hébreux 13:1-2"
    assert modele.aiguillages == []


@pytest.mark.asyncio
async def test_un_refus_ecrit_ecarte_l_option_sans_aiguiller():
    """Écarter n'efface pas : l'option reste dans la liste, marquée et reléguée. Le geste
    écrit doit aboutir exactement où aboutit le geste touché."""
    modele = _Modele()
    service = _service(modele=modele)
    dto = await _ouvrir(service, "je veux prêcher sur la fraternité")
    (premier, *_) = [o[0] for o in dto.options]

    apres = await service.dire(
        actor_account_id=AUTEUR, study_id=dto.record.id, raw_input="non, pas le premier"
    )

    assert modele.aiguillages == []
    ecartees = [code for code, *_, dismissed, _ in apres.options if dismissed]
    assert ecartees == [premier]
    assert premier in [o[0] for o in apres.options], "une option écartée reste dans la liste"


@pytest.mark.asyncio
async def test_une_question_libre_est_aiguillee_et_n_ecrit_rien():
    """Le tour 5 de la maquette — et rien ne doit bouger dans l'enregistrement.

    ⚠️ *Une intention ne déclenche jamais un acte irréversible : elle propose.*"""
    modele = _Modele(intention="interroger_travail")
    service = _service(modele=modele)
    dto = await _ouvrir(service, "Hébreux 13:1")
    avant = replace(service.studies.records[dto.record.id])

    apres = await service.dire(
        actor_account_id=AUTEUR, study_id=dto.record.id,
        raw_input="Quel plan je peux tenir sur ce texte ?",
    )

    assert modele.aiguillages == ["Quel plan je peux tenir sur ce texte ?"]
    assert apres.reponse and "sous vos yeux" in apres.reponse
    assert service.studies.records[dto.record.id] == avant


@pytest.mark.asyncio
async def test_le_quota_epuise_ne_ferme_pas_le_tour_il_le_dit():
    """Le plafond éteint l'assistance, jamais Urim (S12/S37) — et le tour doit le **dire**
    plutôt que de traiter la phrase du pasteur comme du bruit."""
    modele = _Modele(intention="interroger_travail")
    service = UrimStudyService(
        studies=_Studies(), reservations=_Reservations(epuise=True), access=_Acces(),
        index=_index(), clock=lambda: MAINTENANT, resolver=modele,
    )
    dto = await _ouvrir(service, "Hébreux 13:1")

    apres = await service.dire(
        actor_account_id=AUTEUR, study_id=dto.record.id, raw_input="quel plan je peux tenir"
    )

    assert modele.aiguillages == []
    assert apres.reponse and "phrase libre" in apres.reponse


def test_le_rang_se_compte_dans_l_ordre_de_l_ecran_pas_dans_celui_du_moteur():
    """🔴 **Les deux lectures doivent partir de la même liste.**

    Le moteur rend les unités à plat ; le tour les groupe par ce qu'elles font du sujet — *en
    fait son sujet* avant *le soutient* avant *lui résiste*. Compter « le deuxième » sur la
    liste du moteur ferait agir sur une autre option que celle touchée, et une désignation
    manquée coûte plus cher qu'une intention mal aiguillée."""
    from app.contexts.urim.interface.schemas import StudyView
    from app.contexts.urim.interface.turn import construire_tour

    service = _service()
    dto = StudyDTO(
        record=PreparationRecord(
            id=UNITE, church_id=EGLISE, author_id=AUTEUR, raw_input="la fraternité"
        ),
        outcome="await_decision",
        rationale="Laquelle prêchez-vous ?",
        trace=(("weigh_conviction", "Lu comme une intention."),),
        options=(
            ("texte:c", "Celle qui résiste", "motif", "curation", False, "resiste"),
            ("texte:a", "Celle qui en fait son sujet", "motif", "curation", False, "dominant"),
        ),
    )

    ecran = service._ecran(dto)
    tour = construire_tour(StudyView.from_dto(dto))
    affichees = [item.code for groupe in tour.blocks[0].groups for item in groupe.items]

    assert list(ecran.codes) == affichees == ["texte:a", "texte:c"]


def test_une_option_ecartee_n_est_plus_une_cible_au_rang():
    """Elle reste dans la vue, reléguée — mais le tour ne la propose plus au toucher, donc
    elle ne compte plus dans les rangs non plus."""
    service = _service()
    dto = StudyDTO(
        record=PreparationRecord(
            id=UNITE, church_id=EGLISE, author_id=AUTEUR, raw_input="la fraternité"
        ),
        outcome="await_decision",
        rationale="Laquelle prêchez-vous ?",
        options=(
            ("axe:christologie", "Christologie", "motif", "locus", True, None),
            ("axe:ecclesiologie", "Ecclésiologie", "motif", "locus", False, None),
        ),
    )

    assert service._ecran(dto).codes == ("axe:ecclesiologie",)


# ======================================= 7. la notation du pasteur, branchee sur la liaison


@pytest.mark.parametrize(
    ("saisie", "attendue"),
    [
        ("Hb 13v1", Reference("Hébreux", 13, 1)),
        ("hb13v1", Reference("Hébreux", 13, 1)),
        ("Hb 13v1-2", Reference("Hébreux", 13, 1, 2)),
        ("non, pas Hb 13v1", Reference("Hébreux", 13, 1)),
        ("enlève Hb 13v1", Reference("Hébreux", 13, 1)),
    ],
)
def test_le_lecteur_comprend_la_notation_du_pasteur(saisie: str, attendue) -> None:
    """`Hb 2v29`, `Jn14v28`, `Eph 1v20-22` — pas une de ses saisies n'a la forme
    `Livre chapitre:verset`. Le préfixe de retrait est retiré parce qu'il vient d'un
    vocabulaire **fermé** : on ne saute pas de la prose."""
    assert lire_la_notation(saisie, _index()).lues == (attendue,)


@pytest.mark.parametrize(
    "saisie",
    [
        "prends Hb 13v1",
        "je veux prêcher sur Hb 13v1",
        "l'amour fraternel n'existe plus dans l'eglise",
        "Ma voiture 406, a besoin de reparation , jefgf Paradis",
    ],
)
def test_le_nom_de_livre_doit_ouvrir_la_saisie(saisie: str) -> None:
    """🔴 **La garde qui rend le branchement sûr.**

    Balayer la phrase entière rendrait « Marc a quitté l'église » ou « il y a des actes qui
    parlent » équivalents à une référence — Marc, Actes, Juges et Nombres sont des mots
    français avant d'être des livres. C'est la sévérité de S35, et l'assouplir rouvrirait la
    porte que le détecteur d'entrée tient fermée.

    Le prix, assumé : « prends Hb 13v1 » repart au modèle. Un appel de trop contre une
    désignation inventée."""
    assert lire_la_notation(saisie, _index()).lues == ()


# -- le contrôle de référence ---------------------------------------------------------


def test_le_corpus_dit_ce_qui_manque_a_la_reference() -> None:
    """🔴 **`Hb 2v29` est dans ses notes, et Hébreux 2 compte 18 versets.**

    Urim savait le dire depuis le premier jour et ne le disait qu'aux textes d'appui : au tour,
    la saisie repartait à l'aiguilleur, qui répondait à côté sans rien dire de l'erreur."""
    lu = lire_la_notation("Hb 2v29", _index())

    assert "il n'y a pas de verset 29" in lu.introuvable
    assert "18 versets" in lu.introuvable, "le motif porte les mots du corpus"


def test_une_reference_qui_existe_n_est_pas_contredite() -> None:
    assert lire_la_notation("Hb 13v1", _index()).introuvable == ""


def test_on_ne_contredit_pas_une_phrase_ou_un_livre_passe_par_hasard() -> None:
    """🔴 **La garde qui empêche de répondre à une question qu'il n'a pas posée.**

    « Nombres 500 personnes sont venues » est une phrase où un nom de livre passe par hasard.
    Le surplus de mots interdit de **contredire** — pas de désigner : désigner est réversible,
    contredire ne l'est pas."""
    assert lire_la_notation("Hb 2v29 enfin je crois", _index()).introuvable == ""


def test_le_motif_du_lecteur_ne_sort_jamais() -> None:
    """*« Je ne connais pas de livre nommé "bonjour" »* est juste, et absurde : toute phrase
    ordinaire le déclencherait. Seul le verdict du corpus sur un livre **déjà reconnu** sort."""
    assert lire_la_notation("bonjour, on en est où", _index()).introuvable == ""


@pytest.mark.asyncio
async def test_le_tour_rend_le_verdict_du_corpus_sans_appeler_le_modele():
    """Le contrôle de référence, de bout en bout — et **zéro appel** : le corpus sait cela
    tout seul."""
    modele = _Modele(intention="changer_de_sujet")
    service = _service(modele=modele)
    dto = await _ouvrir(service, "Hébreux 13:1")

    apres = await service.dire(
        actor_account_id=AUTEUR, study_id=dto.record.id, raw_input="Hb 2v29"
    )

    assert modele.aiguillages == []
    assert apres.reponse and "il n'y a pas de verset 29" in apres.reponse
    assert apres.resolved_label == "Hébreux 13:1", "la préparation ne bouge pas"


def _service_avec_deux_passages() -> tuple[UrimStudyService, _Modele]:
    """L'écran des axes du chemin conviction : dix loci, puis deux passages du sens.

    Les deux **se chevauchent** — 13:1-2 et 13:1 — et c'est ce qui rend le couple de tests
    ci-dessous intéressant : selon le verset écrit, la notation vise l'un des deux, ou les
    deux."""
    modele = _Modele(passages=(
        PassageSuggestion(Reference("Hébreux", 13, 1, 2), "traite ce sujet"),
        PassageSuggestion(Reference("Hébreux", 13, 1, 1), "aussi"),
    ))
    return _service(modele=modele), modele


@pytest.mark.asyncio
async def test_une_reference_en_notation_de_pasteur_choisit_l_option_sans_aiguiller():
    """🔴 **Une référence affichée à l'écran partait quand même au modèle.**

    Le lecteur qui comprend `Hb 13v2` existe depuis la chaîne de textes d'appui, et il ne
    parlait à personne dans le tour. Le verset tranche : il tombe dans 13:1-2 et hors de
    13:1."""
    service, modele = _service_avec_deux_passages()
    dto = await _ouvrir(service, "je veux prêcher sur la fraternité")

    apres = await service.dire(
        actor_account_id=AUTEUR, study_id=dto.record.id, raw_input="Hb 13v2"
    )

    assert apres.resolved_label == "Hébreux 13:1-2"
    assert modele.aiguillages == []


@pytest.mark.asyncio
async def test_une_notation_qui_vise_deux_options_rend_la_main():
    """⚠️ `Hb 13v1` tombe **dans les deux** passages proposés. La liaison ne tranche pas :
    deux options peuvent convenir, et se tromper d'objet coûte plus cher qu'un appel."""
    service, modele = _service_avec_deux_passages()
    dto = await _ouvrir(service, "je veux prêcher sur la fraternité")

    apres = await service.dire(
        actor_account_id=AUTEUR, study_id=dto.record.id, raw_input="Hb 13v1"
    )

    assert apres.resolved_label is None, "rien n'a été décidé"
    assert modele.aiguillages == ["Hb 13v1"], "l'aiguilleur a pris le tour"
