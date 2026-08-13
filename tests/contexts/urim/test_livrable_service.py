"""La validation du livrable — **l'ordre, qui est toute la protection**.

Le cœur pur (`test_livrable.py`) sait juger deux chaînes. Ce fichier garde ce qui l'entoure, et
qui décide vraiment :

1. **Rien n'est produit sans une division du plan.** C'est la règle centrale, et elle est
   arithmétique : le document met en page ce que le pasteur a écrit.
2. **Le jugement précède le fichier.** Une diapositive altérée rend `rejete` — et il n'y a rien
   à supprimer, puisque rien n'a été produit. Un contrôle d'après coup protège la base de
   données, pas l'assemblée.
3. **`conforme` est signé.** Par celui qui valide, pas par l'auteur de la préparation : c'est
   lui qui répond de ce qui sortira.
4. **Toutes les versions détenues sont consultées** (Q9), et la version reconnue est enregistrée
   — sur Romains 8:1 elle change la doctrine du verset projeté.
5. **Une référence qui n'existe pas ne bloque que sa diapositive**, avec le motif du corpus : on
   rend le dossier entier, pas la première faute.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.contexts.urim.application.ports import ElementRecord, PreparationRecord
from app.contexts.urim.deliverable.application.ports import (
    DiapositiveSoumise,
    TexteServi,
)
from app.contexts.urim.deliverable.application.service import UrimDeliverableService
from app.contexts.urim.deliverable.domain.citation import ALTERE, EXACT
from app.contexts.urim.deliverable.domain.documents import POINT_CENTRAL
from app.contexts.urim.domain.errors import LivrableSansPlanError

from .test_study_service import AUTEUR, EGLISE, MAINTENANT, UNITE, _Acces, _index

pytestmark = pytest.mark.asyncio

#: Hébreux 13:1 tel que l'index de test le sert.
HB_13_1 = "Persévérez dans l'amour fraternel."
#: La même phrase avec un mot changé — l'altération que le contrôle existe pour voir.
HB_13_1_ALTERE = "Persévérez dans l'amour du prochain."
#: Une seconde version détenue, qui porte une formulation différente et légitime.
HB_13_1_AUTRE = "Que l'amour fraternel demeure."

LSG, AUTRE_VERSION = uuid4(), uuid4()


class _Studies:
    def __init__(self, record: PreparationRecord | None, elements=()) -> None:
        self._record = record
        self._elements = list(elements)

    async def get(self, study_id):
        if self._record is not None and study_id == self._record.id:
            return self._record
        return None

    async def list_elements(self, study_id):
        return self._elements


class _Livrables:
    def __init__(self) -> None:
        self.ecrits: list[tuple] = []

    async def add(self, record, controles) -> None:
        self.ecrits.append((record, controles))

    async def get(self, deliverable_id):
        return next((r for r, _ in self.ecrits if r.id == deliverable_id), None)

    async def controles(self, deliverable_id):
        return next((c for r, c in self.ecrits if r.id == deliverable_id), [])


class _Versets:
    """Deux versions détenues — c'est le minimum pour que Q9 veuille dire quelque chose."""

    def __init__(self, *textes: TexteServi) -> None:
        self._textes = list(textes) or [
            TexteServi(LSG, "LSG", HB_13_1),
            TexteServi(AUTRE_VERSION, "Ostervald", HB_13_1_AUTRE),
        ]
        self.appels: list[tuple] = []

    async def textes(
        self, *, book_id, chapter, verse_start, verse_end, prefer_version_id=None
    ):
        self.appels.append((book_id, chapter, verse_start, verse_end))
        return list(self._textes)


def _preparation(**kw) -> PreparationRecord:
    return PreparationRecord(
        id=kw.pop("id", uuid4()),
        church_id=kw.pop("church_id", EGLISE),
        author_id=kw.pop("author_id", AUTEUR),
        raw_input="Hébreux 13:1-2",
        pericope_id=UNITE,
        version_id=LSG,
        **kw,
    )


def _service(record, *, elements=(), livrables=None, versets=None):
    return UrimDeliverableService(
        studies=_Studies(record, elements),
        livrables=livrables or _Livrables(),
        versets=versets or _Versets(),
        access=_Acces(),
        index=_index(),
        clock=lambda: MAINTENANT,
    )


_PLAN = (ElementRecord(POINT_CENTRAL, 1, "1- L'amour fraternel demeure"),)


# ============================================================ 1. rien sans son plan


async def test_sans_division_du_plan_aucun_livrable_n_est_produit():
    """**La règle centrale**, et elle est arithmétique : sans plan, il n'y a rien à imprimer.

    Le motif oriente — un refus qui n'oriente pas est une porte fermée."""
    prep = _preparation()
    depot = _Livrables()
    service = _service(prep, elements=(), livrables=depot)

    with pytest.raises(LivrableSansPlanError) as refus:
        await service.soumettre(actor_account_id=AUTEUR, study_id=prep.id)

    assert "ne l'écrit pas à votre place" in str(refus.value)
    assert depot.ecrits == []  # rien n'a été écrit, pas même un rejet


async def test_un_titre_seul_ne_suffit_pas():
    """Le couple : une étiquette n'est pas un plan."""
    prep = _preparation()
    service = _service(prep, elements=(ElementRecord("titre", 1, "L'amour fraternel"),))
    with pytest.raises(LivrableSansPlanError):
        await service.soumettre(actor_account_id=AUTEUR, study_id=prep.id)


async def test_une_division_suffit_a_ouvrir_le_livrable():
    prep = _preparation()
    service = _service(prep, elements=_PLAN)
    dto = await service.soumettre(actor_account_id=AUTEUR, study_id=prep.id, kind="note")
    assert dto.conforme
    assert dto.record.format == "docx"  # la note a son format natif


# ============================================================ 2. le jugement précède le fichier


async def test_une_diapositive_alteree_rend_rejete_et_aucun_fichier_n_existe():
    """**L'ordre est toute la protection.** Le service ne produit aucun octet : il valide.

    Un contrôle d'après coup protégerait la base de données, pas l'assemblée — un fichier
    produit est un fichier qui circule."""
    prep = _preparation()
    service = _service(prep, elements=_PLAN)

    dto = await service.soumettre(
        actor_account_id=AUTEUR,
        study_id=prep.id,
        diapositives=[DiapositiveSoumise("Le texte", "Hébreux 13:1", HB_13_1_ALTERE)],
    )

    assert dto.record.validation == "rejete"
    assert dto.controles[0].verdict == ALTERE
    # …et personne n'a signé un rejet.
    assert dto.record.validated_by is None and dto.record.validated_at is None


async def test_un_texte_fidele_rend_conforme_et_signe():
    """`conforme` est **signé**, et par celui qui valide : c'est lui qui monte en chaire."""
    prep = _preparation(author_id=uuid4())  # la préparation est d'un collègue
    service = _service(prep, elements=_PLAN)

    dto = await service.soumettre(
        actor_account_id=AUTEUR,
        study_id=prep.id,
        diapositives=[DiapositiveSoumise("Le texte", "Hébreux 13:1", HB_13_1)],
    )

    assert dto.record.validation == "conforme"
    assert dto.record.validated_by == AUTEUR
    assert dto.record.validated_at == MAINTENANT


# ============================================================ 3. toutes les versions (Q9)


async def test_le_texte_d_une_autre_version_detenue_est_reconnu_et_enregistre():
    """Q9 de bout en bout : un pasteur cite la Bible qu'il a.

    La version reconnue descend dans `citation_check.version_id` — la colonne existait et rien
    ne la remplissait."""
    prep = _preparation()
    service = _service(prep, elements=_PLAN)

    dto = await service.soumettre(
        actor_account_id=AUTEUR,
        study_id=prep.id,
        diapositives=[DiapositiveSoumise("Le texte", "Hébreux 13:1", HB_13_1_AUTRE)],
    )

    assert dto.conforme
    assert dto.controles[0].verdict == EXACT
    assert dto.controles[0].version_id == AUTRE_VERSION


async def test_la_version_de_la_preparation_est_demandee_en_premier():
    """L'ordre est une préférence, et le service la transmet — c'est la version dans laquelle
    il travaille qui doit être nommée quand deux la reconnaissent."""
    prep = _preparation()
    versets = _Versets()
    service = _service(prep, elements=_PLAN, versets=versets)

    await service.soumettre(
        actor_account_id=AUTEUR,
        study_id=prep.id,
        diapositives=[DiapositiveSoumise("Le texte", "Hébreux 13:1", HB_13_1)],
    )

    assert versets.appels == [(58, 13, 1, None)]


# ============================================================ 4. une référence illisible


async def test_une_reference_hors_bornes_ne_bloque_que_sa_diapositive():
    """`Hb 2v29` — une vraie faute des notes du Pasteur X. Le motif dit ce qui manque **au
    corpus**, et les autres diapositives sont jugées quand même : on rend le dossier entier,
    jamais la première faute."""
    prep = _preparation()
    service = _service(prep, elements=_PLAN)

    dto = await service.soumettre(
        actor_account_id=AUTEUR,
        study_id=prep.id,
        diapositives=[
            DiapositiveSoumise("Faux", "Hb 2v29", "un texte"),
            DiapositiveSoumise("Vrai", "Hébreux 13:1", HB_13_1),
        ],
    )

    assert [c.verdict for c in dto.controles] == [ALTERE, EXACT]
    assert "18 verset" in dto.controles[0].rationale
    assert dto.record.validation == "rejete"


# ============================================================ 5. la trace


async def test_le_livrable_porte_l_empreinte_de_ce_qui_a_ete_imprime():
    """*Une décision ne vaut que sur l'objet qu'elle a regardé.* Deux documents de la même
    préparation, à deux semaines d'écart, ne sont pas le même document."""
    prep = _preparation()
    service = _service(prep, elements=_PLAN)

    premier = await service.soumettre(
        actor_account_id=AUTEUR,
        study_id=prep.id,
        diapositives=[DiapositiveSoumise("Le texte", "Hébreux 13:1", HB_13_1)],
    )
    second = await service.soumettre(
        actor_account_id=AUTEUR,
        study_id=prep.id,
        diapositives=[
            DiapositiveSoumise("Le texte", "Hébreux 13:1", "Persévérez dans l'amour")
        ],
    )

    assert premier.record.content_fingerprint != second.record.content_fingerprint
    assert premier.record.corpus_snapshot == "essai"


async def test_relire_rend_le_dossier_et_garde_la_meme_garde():
    prep = _preparation()
    depot = _Livrables()
    service = _service(prep, elements=_PLAN, livrables=depot)

    ecrit = await service.soumettre(
        actor_account_id=AUTEUR,
        study_id=prep.id,
        diapositives=[DiapositiveSoumise("Le texte", "Hébreux 13:1", HB_13_1)],
    )
    relu = await service.relire(
        actor_account_id=AUTEUR, deliverable_id=ecrit.record.id
    )

    assert relu.record.id == ecrit.record.id
    assert len(relu.controles) == 1


async def test_l_horloge_du_service_date_le_livrable():
    prep = _preparation()
    service = _service(prep, elements=_PLAN)
    dto = await service.soumettre(actor_account_id=AUTEUR, study_id=prep.id, kind="note")
    assert dto.record.generated_at == datetime(2026, 8, 10, tzinfo=UTC)
