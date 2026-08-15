"""Les règles d'Urim qui vivent **dans la base**, et la preuve qu'elles mordent.

Une contrainte qu'aucun test ne fait échouer est indiscernable d'un commentaire. Chaque cas
ci-dessous présente le **couple** : la ligne légitime, que la base accepte, et sa jumelle fautive,
qu'elle refuse. C'est le couple qui prouve quelque chose — une contrainte qui rejette tout est
aussi inutile qu'une contrainte absente.

Six règles produit sont écrites ici en SQL plutôt qu'en Python, et ce n'est pas un raffinement :

- une garde applicative tombe dès qu'un second chemin d'écriture apparaît — un import, un script
  de reprise, un correctif de nuit ;
- deux requêtes concurrentes la franchissent toutes les deux.

Le seuil de cinq personnes est l'exemple qui décide : il tient **même si un développeur se trompe
dans l'adaptateur**.
"""

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.contexts.urim.infrastructure.persistence.corpus_models import (
    CorpusCollisionWitnessModel,
    CorpusDoctrinalBearingModel,
    CorpusDoctrinalCaveatModel,
    CorpusHomileticFeasibilityModel,
    CorpusVersionModel,
)
from app.contexts.urim.infrastructure.persistence.models import (
    UrimAggregateSignalSnapshotModel,
    UrimEcclesialEventSnapshotModel,
    UrimReflectionModel,
    UrimTranscriptSegmentModel,
)
from app.core.database import Base

_NOW = datetime(2026, 8, 6, tzinfo=UTC)
_RELU = {"reviewed_by": "curateur", "reviewed_at": _NOW}


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as opened:
        yield opened
    await engine.dispose()


def _version(**kw):
    base = {
        "id": uuid4(), "code": f"V{uuid4().hex[:6]}", "language": "fra", "label": "Segond",
        "translation_kind": "formelle", "license_kind": "domaine_public",
        "offline_allowed": True, "metered": False, "versification": "standard",
    }
    return CorpusVersionModel(**{**base, **kw})


def _agregat(**kw):
    base = {
        "id": uuid4(), "church_id": uuid4(), "topic": "deuil", "headcount": 5,
        "window_days": 30, "fetched_at": _NOW,
    }
    return UrimAggregateSignalSnapshotModel(**{**base, **kw})


def _faisabilite(**kw):
    base = {
        "pericope_id": uuid4(), "plan_source": "expositif", "subject_matter": "doctrinal",
        "feasible": True, "refusal_reason": None, "proof_text_risk": "faible", **_RELU,
    }
    return CorpusHomileticFeasibilityModel(**{**base, **kw})


def _caveat(**kw):
    base = {
        "id": uuid4(), "pericope_id": uuid4(), "axis_code": "soteriologie",
        "body": "le texte ne tranche pas la question de la persévérance",
        "caveat_kind": "exegetique", "tradition_scope": None, "source_ref": "Cranfield",
        **_RELU,
    }
    return CorpusDoctrinalCaveatModel(**{**base, **kw})


def _retour(**kw):
    base = {
        "id": uuid4(), "capture_id": uuid4(), "author_id": uuid4(),
        "synthesis_state": "proposee", "validated_by": None, "validated_at": None,
        "computed_at": _NOW,
    }
    return UrimReflectionModel(**{**base, **kw})


def _segment(**kw):
    base = {
        "capture_id": uuid4(), "ordinal": 1, "body": "…", "started_ms": 1000,
        "ended_ms": 4000, "confidence": 0.9,
    }
    return UrimTranscriptSegmentModel(**{**base, **kw})


def _evenement(**kw):
    base = {
        "id": uuid4(), "church_id": uuid4(), "kind": "EVANGELISM",
        "occurs_on": date(2026, 9, 1), "label": None, "fetched_at": _NOW,
    }
    return UrimEcclesialEventSnapshotModel(**{**base, **kw})


def _lecture(**kw):
    base = {
        "collision_id": uuid4(), "version_code": "DARBY", "stance": "diverge",
        "reading": "rassemblement", "body": "Et Dieu appela le sec Terre…",
    }
    return CorpusCollisionWitnessModel(**{**base, **kw})


#: Chaque cas : ce que la base doit accepter, et la jumelle qu'elle doit refuser.
COUPLES = [
    pytest.param(
        _version, {}, {"metered": True},
        id="ce qui ne coute rien a servir n'est jamais plafonne",
    ),
    pytest.param(
        _agregat, {}, {"headcount": 4},
        id="aucun agregat sous cinq personnes",
    ),
    pytest.param(
        _faisabilite,
        {"feasible": False, "refusal_reason": "ce passage ne porte aucun personnage"},
        {"feasible": False, "refusal_reason": None},
        id="un refus qu'on ne peut pas contester n'est pas un refus",
    ),
    pytest.param(
        _caveat,
        {"caveat_kind": "confessionnel", "tradition_scope": ["reformee"]},
        {"caveat_kind": "confessionnel", "tradition_scope": None},
        id="un caveat confessionnel ne fuit pas hors de sa tradition",
    ),
    pytest.param(
        _retour,
        {"synthesis_state": "validee", "validated_by": uuid4(), "validated_at": _NOW},
        {"synthesis_state": "validee"},
        id="une parole validee porte le nom de qui l'a signee",
    ),
    pytest.param(
        _segment, {}, {"started_ms": 4000, "ended_ms": 1000},
        id="un segment ne finit pas avant de commencer",
    ),
    pytest.param(
        _evenement, {}, {"kind": "FUNDRAISER"},
        id="un type de plus est invisible par defaut",
    ),
    pytest.param(
        _lecture,
        {"stance": "muet", "reading": None},
        {"stance": "muet", "reading": "rassemblement"},
        # Un témoin muet ne tient pas le verset, ou l'a reformulé d'un bout à l'autre : lui
        # prêter un mot est la façon exacte dont cet écran deviendrait menteur, et le pasteur
        # citerait en chaire une lecture que personne n'a faite.
        id="un temoin qui ne se prononce pas n'a pas de lecture",
    ),
]


@pytest.mark.parametrize(("build", "licite", "fautif"), COUPLES)
async def test_la_base_accepte_l_un_et_refuse_l_autre(session, build, licite, fautif):
    """La garde est **dans la base**, pas seulement dans le cas d'usage.

    C'est ce qui distingue « l'application vérifie avant d'écrire » de « aucun chemin d'écriture
    ne peut produire cette ligne »."""
    session.add(build(**licite))
    await session.flush()

    session.add(build(**fautif))
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_une_pericope_peut_resister_a_un_axe(session):
    """`resiste` est la valeur qui distingue Urim d'un moteur de proof-texting.

    Elle manquait au schéma d'origine, et sans elle le mode conviction était inconstructible :
    `absent` — le texte ne dit rien de cet axe — et `resiste` — le texte le complique ou le
    contredit — sont **opposés**, pas voisins. Seule la seconde protège le pasteur du passage
    qu'on lui aurait servi parce qu'il allait dans le bon sens."""
    session.add(
        CorpusDoctrinalBearingModel(
            pericope_id=uuid4(), axis_code="soteriologie", strength="resiste",
            rationale="l'avertissement de He 6 complique la persévérance inconditionnelle",
            source_ref="Cranfield", **_RELU,
        )
    )
    await session.flush()  # la base l'accepte — c'était le point


async def test_le_repli_du_domaine_public_ne_peut_pas_etre_lui_meme_bloque(session):
    """Le filet ne peut pas céder — et c'est une propriété du **schéma**, pas du code.

    `public_domain_fallback()` promet une version jamais plafonnée. `licence_coherente` rend cette
    promesse increvable : il n'existe aucun état de la base où une version du domaine public soit
    `metered`. Le test précédent prouve le refus ; celui-ci nomme ce qu'il achète."""
    session.add(_version(license_kind="domaine_public", offline_allowed=True, metered=False))
    await session.flush()

    session.add(
        _version(license_kind="sous_licence", provider="acme", offline_allowed=False,
                 metered=True)
    )
    await session.flush()  # une version facturée est licite ; c'est le domaine public qui est tenu
