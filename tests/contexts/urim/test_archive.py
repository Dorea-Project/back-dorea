"""L'archive du prédicateur — **la table qui était lue et que personne n'écrivait**.

`urim_preached` alimente l'étage du thème (« vous avez déjà prêché cet axe récemment ») depuis
le premier jour, et aucun code ne l'avait jamais écrite : la phrase n'a atteint personne. Ce
fichier garde les cinq propriétés qui font qu'une archive dit la vérité — et chacune vient
d'une décision, pas d'une commodité.

1. **Rien ne s'archive parce qu'une date est passée.** Le Pasteur X a prêché le Psaume 125,
   absent des six passages proposés : une archive remplie par le calendrier aurait menti dès
   la première semaine.
2. **Un pasteur sans église archive.** `preached.church_id` était `NOT NULL` alors que la
   préparation ne l'est plus — l'antichambre était cassée à la sortie.
3. **Prêché deux fois = deux faits, un seul lieu.** La couverture compte des passages
   distincts, la distribution compte des prédications.
4. **« Non rangé » est un rayon**, pas une ligne absente (S38).
5. **Une référence qui n'existe pas est refusée avec le motif du corpus** — « Hébreux 2 compte
   18 versets », jamais « saisie invalide » (S19).
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from app.contexts.urim.application.archive_service import UrimArchiveService
from app.contexts.urim.application.ports import (
    AxisTally,
    BookCoverage,
    PreachedRecord,
    PreparationRecord,
)
from app.contexts.urim.domain.errors import (
    ArchiveIllisibleError,
    PreparationIntrouvableError,
)

from .test_study_service import AUTEUR, EGLISE, MAINTENANT, UNITE, _Acces, _index

pytestmark = pytest.mark.asyncio

AUTRE = uuid4()


class _Archive:
    """Le dépôt en mémoire — **avec les deux lectures calculées comme le SQL les calcule**.

    Une doublure qui compterait les lignes là où la base compte des passages distincts ferait
    passer pour vrai exactement le défaut qu'on veut interdire."""

    def __init__(self) -> None:
        self.lignes: list[PreachedRecord] = []

    async def add(self, record: PreachedRecord) -> None:
        self.lignes.append(record)

    async def list_for(self, author_id, *, limit):
        return [r for r in self.lignes if r.author_id == author_id][:limit]

    async def coverage(self, author_id):
        par_livre: dict[int, list[PreachedRecord]] = {}
        for r in self.lignes:
            if r.author_id == author_id and r.book_id is not None:
                par_livre.setdefault(r.book_id, []).append(r)
        return [
            BookCoverage(
                book_id=livre,
                passages=len({(r.start_ch, r.start_v, r.end_ch, r.end_v) for r in rs}),
                preachings=len(rs),
                last_preached_on=max(r.preached_on for r in rs),
            )
            for livre, rs in sorted(par_livre.items())
        ]

    async def distribution(self, author_id):
        par_axe: dict[str | None, list[PreachedRecord]] = {}
        for r in self.lignes:
            if r.author_id == author_id:
                par_axe.setdefault(r.axis_code, []).append(r)
        return [
            AxisTally(
                axis_code=axe,
                preachings=len(rs),
                last_preached_on=max(r.preached_on for r in rs),
            )
            for axe, rs in par_axe.items()
        ]


class _Studies:
    def __init__(self, *records: PreparationRecord) -> None:
        self.records = {r.id: r for r in records}

        self.squelettes: dict = {}
    #: **Le plan propose, garde par empreinte.** Une doublure qui rendrait toujours
    #: `None` ferait rappeler le modele a chaque rejeu — donc mesurerait un service
    #: que la production n'a pas.
    async def save_skeleton(self, study_id, input_hash, squelette, at):
        self.squelettes[study_id] = (input_hash, squelette)

    async def get_skeleton(self, study_id, input_hash=None):
        garde = self.squelettes.get(study_id)
        if garde is None or (input_hash is not None and garde[0] != input_hash):
            return None
        return garde[1]

    async def get(self, study_id):
        return self.records.get(study_id)

    async def save(self, record) -> None:
        """⚠️ **Le double garde**, et il le faut depuis D57 : archiver **ferme** la
        préparation de son auteur. Une doublure qui avalerait l'écriture sans la conserver
        laisserait passer une fermeture faite au nom du mauvais pasteur."""
        self.records[record.id] = record


def _preparation(*, church_id=EGLISE, author_id=AUTEUR, **kw) -> PreparationRecord:
    return PreparationRecord(
        id=kw.pop("id", uuid4()),
        church_id=church_id,
        author_id=author_id,
        raw_input="Hébreux 13:1-2",
        resolved_ref=kw.pop("resolved_ref", "Hébreux|13|1|2"),
        pericope_id=kw.pop("pericope_id", UNITE),
        axis_code=kw.pop("axis_code", "ecclesiologie"),
        theme=kw.pop("theme", "ecclesiologie"),
        **kw,
    )


def _service(*records: PreparationRecord, archive: _Archive | None = None):
    return UrimArchiveService(
        archive=archive or _Archive(),
        studies=_Studies(*records),
        access=_Acces(),
        index=_index(),
        clock=lambda: MAINTENANT,
    )


# ============================================================ 1. le geste, jamais la date


async def test_rien_ne_s_archive_tant_que_personne_ne_le_dit():
    """**La propriété centrale** : préparer n'archive pas.

    Le Pasteur X avait six passages proposés et en a prêché un septième. Aucun calendrier ne
    peut savoir cela — seul celui qui était en chaire le sait."""
    prep = _preparation()
    depot = _Archive()
    service = _service(prep, archive=depot)

    assert depot.lignes == []  # la préparation existe, l'archive est vide

    await service.record_from_study(actor_account_id=AUTEUR, study_id=prep.id)

    assert len(depot.lignes) == 1  # …et elle ne s'est remplie que sur un geste


async def test_la_date_par_defaut_est_aujourd_hui_pas_le_dimanche_prevu():
    """`service_date` dit *quand je compte prêcher*. L'archive dit *ce qui a eu lieu*.

    Prendre la date de service ferait entrer une prédication future dans un registre de faits
    — et la couverture du canon compterait un texte que personne n'a encore ouvert."""
    prep = _preparation(service_date=date(2026, 12, 25))
    service = _service(prep)

    entree = await service.record_from_study(actor_account_id=AUTEUR, study_id=prep.id)

    assert entree.record.preached_on == MAINTENANT.date()


async def test_une_preparation_qui_n_existe_pas_ne_s_archive_pas():
    service = _service()
    with pytest.raises(ArchiveIllisibleError):
        await service.record_from_study(actor_account_id=AUTEUR, study_id=uuid4())


# ============================================================ 2. l'antichambre


async def test_un_pasteur_sans_eglise_archive():
    """`preached.church_id` était `NOT NULL` quand la préparation ne l'était plus.

    On pouvait donc préparer sans église et **pas archiver** : la porte se refermait sur le
    premier utilisateur de l'application, celui qui n'a encore rejoint personne."""
    prep = _preparation(church_id=None)
    service = _service(prep)

    entree = await service.record_from_study(actor_account_id=AUTEUR, study_id=prep.id)

    assert entree.record.church_id is None
    assert entree.reference == "Hébreux 13:1-2"


async def test_la_preparation_personnelle_d_un_autre_reste_invisible():
    """Le couple du test précédent : sans église, la propriété est la seule garde.

    Et le refus dit *« cette préparation n'existe pas »* — sur un objet privé, confirmer
    l'existence dirait déjà que cette personne prépare, sur quoi, et quand."""
    prep = _preparation(church_id=None)
    service = _service(prep)

    with pytest.raises(PreparationIntrouvableError):
        await service.record_from_study(actor_account_id=AUTRE, study_id=prep.id)


async def test_l_archive_est_celle_de_qui_archive():
    """Deux pasteurs d'une même église se relisent (la garde d'église le permet).

    Si le second prêche à partir du travail du premier, c'est **sa** prédication : `author_id`
    est l'acteur. Sans quoi n'importe quel collègue pourrait salir la couverture d'un autre —
    et l'écran cesserait d'être digne de foi."""
    prep = _preparation(author_id=AUTEUR)
    service = _service(prep)

    entree = await service.record_from_study(actor_account_id=AUTRE, study_id=prep.id)

    assert entree.record.author_id == AUTRE
    assert entree.record.preparation_id == prep.id


# ================================================== 2-bis. archiver ferme (D57)


@pytest.mark.asyncio
async def test_archiver_ferme_la_preparation_de_son_auteur():
    """**Un geste, une réalité.** « J'ai prêché celle-ci » écrivait l'archive et laissait la
    préparation ouverte : le pasteur devait dire deux fois la même chose, et le fil montrait
    « en cours » un travail déjà passé en chaire."""
    prep = _preparation(author_id=AUTEUR, status="ouverte")
    service = _service(prep)

    await service.record_from_study(actor_account_id=AUTEUR, study_id=prep.id)

    assert prep.status == "close"
    assert prep.closed_at == MAINTENANT


@pytest.mark.asyncio
async def test_un_lecteur_qui_archive_ne_ferme_pas_la_preparation_de_l_auteur():
    """🔴 **Le test qui garde la garde.**

    Cette route passe par `ensure_may_read`, pas `ensure_may_prepare` : deux pasteurs d'une
    même église se relisent, et le second qui prêche enregistre **sa** prédication. Fermer
    sans regarder `author_id` clôturerait donc le travail du premier **parce qu'un confrère
    l'a prêché**.

    Sans ce test, la garde disparaîtra au premier remaniement et personne ne le verra : fermer
    une préparation ne lève aucune erreur."""
    prep = _preparation(author_id=AUTEUR, status="ouverte")
    service = _service(prep)

    await service.record_from_study(actor_account_id=AUTRE, study_id=prep.id)

    assert prep.status == "ouverte", "le travail de l'auteur ne se ferme pas sans lui"
    assert prep.closed_at is None


@pytest.mark.asyncio
async def test_une_preparation_rangee_reste_rangee():
    """Seulement depuis `ouverte`. Ranger et clore sont deux intentions, et `rangee` a été
    ajouté précisément pour ne pas les confondre."""
    prep = _preparation(author_id=AUTEUR, status="rangee")
    service = _service(prep)

    await service.record_from_study(actor_account_id=AUTEUR, study_id=prep.id)

    assert prep.status == "rangee"


# ============================================================ 3. prêché deux fois


async def test_deux_predications_du_meme_texte_font_un_seul_lieu_et_deux_faits():
    """A-Q1, et c'est la lecture qui tranche, pas la table.

    Deux lignes : le second dimanche a eu lieu, et l'effacer serait perdre un fait. Mais un
    canon ne s'élargit pas en repassant au même endroit — sinon un pasteur qui reprend son
    sermon dans l'annexe paraîtrait avoir couvert deux fois plus d'Écriture."""
    prep = _preparation()
    depot = _Archive()
    service = _service(prep, archive=depot)

    await service.record_from_study(
        actor_account_id=AUTEUR, study_id=prep.id, preached_on=date(2026, 8, 2)
    )
    await service.record_from_study(
        actor_account_id=AUTEUR, study_id=prep.id, preached_on=date(2026, 8, 9)
    )

    vue = await service.coverage(actor_account_id=AUTEUR)
    (_, hebreux), = vue.books
    assert (hebreux.passages, hebreux.preachings) == (1, 2)

    # …et la distribution, elle, compte les deux : deux assemblées ont entendu cet axe.
    (axe,) = vue.axes
    assert (axe.axis_code, axe.preachings) == ("ecclesiologie", 2)


# ============================================================ 4. le rayon « non rangé »


async def test_un_sermon_sans_axe_apparait_dans_un_rayon_nomme():
    """S38 appliqué au rangement : *aucun sermon rangé ici* ≠ *il n'a jamais prêché cela*.

    Hors des unités curées — la quasi-totalité de l'Écriture — il n'y a aucun axe à retenir.
    Faire disparaître ces sermons du graphique donnerait une distribution qui a l'air
    complète alors qu'elle ignore l'essentiel du travail."""
    prep = _preparation(axis_code=None, pericope_id=None)
    depot = _Archive()
    service = _service(prep, archive=depot)

    await service.record_from_study(actor_account_id=AUTEUR, study_id=prep.id)

    vue = await service.coverage(actor_account_id=AUTEUR)
    assert [a.axis_code for a in vue.axes] == [None]


async def test_les_livres_jamais_prêchés_se_comptent_sans_se_reprocher():
    """Le nombre existe — c'est un fait. Ce qui n'existe pas, et ne doit pas exister, c'est
    une proposition de sermon pour le combler."""
    prep = _preparation()
    service = _service(prep)
    await service.record_from_study(actor_account_id=AUTEUR, study_id=prep.id)

    vue = await service.coverage(actor_account_id=AUTEUR)
    # L'index de test ne connaît qu'Hébreux : il est touché, il n'en reste aucun.
    assert vue.books_untouched == 0
    assert not hasattr(vue, "suggestion")  # rien qui propose quoi que ce soit


# ============================================================ 5. la saisie libre


async def test_un_sermon_sans_preparation_s_archive():
    """« On peut prêcher sans avoir préparé » — une archive qui ne mesurerait que ce qui est
    passé par l'outil ne mesurerait pas le ministère de quelqu'un."""
    service = _service()

    entree = await service.record_manually(
        actor_account_id=AUTEUR,
        reference="Hb 13v1-2",  # sa notation, pas la nôtre
        preached_on=date(2026, 7, 5),
        church_id=None,
    )

    assert entree.reference == "Hébreux 13:1-2"
    assert entree.record.capture_kind == "import"


async def test_une_reference_hors_bornes_est_refusee_avec_le_motif_du_corpus():
    """Le couple du test précédent — et **le motif nomme ce qui manque au corpus**.

    `Hb 2v29` est une vraie faute des notes du Pasteur X. Le refus doit lui dire « Hébreux 2
    compte 18 versets », pas « saisie invalide » : la première phrase lui rend son verset, la
    seconde le laisse chercher."""
    service = _service()

    with pytest.raises(ArchiveIllisibleError) as refus:
        await service.record_manually(
            actor_account_id=AUTEUR, reference="Hb 2v29", preached_on=date(2026, 7, 5)
        )

    assert "18 verset" in str(refus.value)


async def test_une_origine_inconnue_est_refusee():
    """La liste des trois origines est fermée en base ; le service la referme avant l'insert,
    pour que le refus soit une phrase et non une violation de contrainte."""
    service = _service()
    with pytest.raises(ArchiveIllisibleError):
        await service.record_manually(
            actor_account_id=AUTEUR,
            reference="Hébreux 13:1",
            preached_on=date(2026, 7, 5),
            capture_kind="devine",
        )


# ============================================================ la phrase enfin atteignable


async def test_le_vrai_depot_rend_les_memes_nombres_que_la_doublure():
    """⚠️ **Le seul test de ce fichier qui touche une base**, et il existe pour une raison
    précise : les deux lectures sont du SQL, et une doublure Python ne prouve rien du SQL.

    La rédaction évidente — `COUNT(DISTINCT (start_ch, start_v, end_ch, end_v))` — passe en
    Postgres et **échoue en SQLite**, qui refuse plus d'un argument dans un agrégat
    `DISTINCT`. Écrite ainsi, la requête n'aurait cassé qu'en production. C'est le mode de
    panne que le dépôt connaît déjà (`confessionnel_borne`, corrigé par `none_as_null`) :
    *une garde qui n'existe que là où personne ne la vérifie.*"""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.contexts.urim.infrastructure.persistence.archive_repository import (
        SqlArchiveRepository,
    )
    from app.core.database import Base

    moteur = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with moteur.begin() as connexion:
        await connexion.run_sync(Base.metadata.create_all)
    fabrique = async_sessionmaker(moteur, expire_on_commit=False)

    async with fabrique() as session:
        depot = SqlArchiveRepository(session)
        commun = {
            "author_id": AUTEUR, "church_id": None, "book_id": 58,
            "start_ch": 13, "start_v": 1, "end_ch": 13, "end_v": 2,
            "axis_code": "ecclesiologie",
        }
        # Le même texte, deux dimanches — un lieu, deux faits.
        await depot.add(PreachedRecord(id=uuid4(), preached_on=date(2026, 8, 2), **commun))
        await depot.add(PreachedRecord(id=uuid4(), preached_on=date(2026, 8, 9), **commun))
        # Un autre passage du même livre, sans axe retenu — le rayon « non rangé ».
        await depot.add(PreachedRecord(
            id=uuid4(), preached_on=date(2026, 8, 16),
            **{**commun, "start_v": 5, "end_v": 6, "axis_code": None},
        ))

        (hebreux,) = await depot.coverage(AUTEUR)
        assert (hebreux.passages, hebreux.preachings) == (2, 3)
        assert hebreux.last_preached_on == date(2026, 8, 16)

        rangement = {a.axis_code: a.preachings for a in await depot.distribution(AUTEUR)}
        assert rangement == {"ecclesiologie": 2, None: 1}

    await moteur.dispose()


async def test_l_axe_archive_est_celui_que_le_pasteur_a_retenu():
    """On range sous **sa** décision, jamais sous le dominant calculé.

    Tout ce qui est curé porte aujourd'hui la signature `ia-mistral` : classer le travail d'un
    homme d'après une pesée qu'aucun humain n'a relue serait ranger sous une machine."""
    prep = _preparation(axis_code="soteriologie")
    service = _service(prep)

    entree = await service.record_from_study(actor_account_id=AUTEUR, study_id=prep.id)

    assert entree.record.axis_code == "soteriologie"
    assert entree.record.pericope_id == UNITE  # l'unité voyage, pour le rangement
