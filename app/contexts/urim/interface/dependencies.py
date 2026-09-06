"""Injection de dépendances d'Urim.

Le point notable est l'**index du corpus** : il est chargé une fois par processus, pas
une fois par requête. C'est légitime parce que le corpus est immuable — versions, texte,
original et curation relue ne changent qu'au déploiement d'un nouveau corpus. Le recharger
à chaque requête coûterait cher et ne rendrait rien de plus.

Le verrou n'est pas décoratif : sans lui, une rafale de requêtes au démarrage lancerait
autant de chargements complets en parallèle.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Header

from app.api.deps import DbSession
from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.iam.infrastructure.persistence.repositories import (
    SqlAlchemyMembershipRepository,
)
from app.contexts.media.infrastructure.stores import build_media_store
from app.contexts.tenant.infrastructure.persistence.ownership_repo import (
    SqlOwnershipRepository,
)
from app.contexts.urim.adapters.authorization import GroupAccessPreacherAuthorization
from app.contexts.urim.adapters.mistral import build_verse_resolver
from app.contexts.urim.adapters.piece_audio import MediaPieceAudioStore
from app.contexts.urim.application.archive_service import UrimArchiveService
from app.contexts.urim.application.curation import UrimCuration
from app.contexts.urim.application.relecture import (
    RegistreDesRelecteurs,
    Relecteur,
    Relecture,
)
from app.contexts.urim.application.study_service import UrimStudyService
from app.contexts.urim.application.transcript_service import TranscriptService
from app.contexts.urim.capture.fragment_store import build_fragment_store
from app.contexts.urim.capture.piece_service import PieceService
from app.contexts.urim.capture.service import UrimCaptureService
from app.contexts.urim.deliverable.application.service import UrimDeliverableService
from app.contexts.urim.domain.errors import CorpusNonSemeError
from app.contexts.urim.infrastructure.corpus.index import (
    CorpusIndex,
    CorpusVideError,
    load_corpus_index,
)
from app.contexts.urim.infrastructure.persistence.archive_repository import (
    SqlArchiveRepository,
)
from app.contexts.urim.infrastructure.persistence.capture_repository import (
    SqlCaptureRepository,
)
from app.contexts.urim.infrastructure.persistence.citation_ailleurs import (
    SqlCitationAilleurs,
)
from app.contexts.urim.infrastructure.persistence.curation_repository import (
    SqlCurationRepository,
)
from app.contexts.urim.infrastructure.persistence.deliverable_repository import (
    SqlDeliverableRepository,
    SqlVerseTextReader,
)
from app.contexts.urim.infrastructure.persistence.piece_repository import (
    SqlPieceRepository,
)
from app.contexts.urim.infrastructure.persistence.relecture_repository import (
    SqlRegistreRepository,
    SqlRelectureRepository,
)
from app.contexts.urim.infrastructure.persistence.study_repository import (
    SqlReservationRepository,
    SqlStudyRepository,
)
from app.contexts.urim.infrastructure.persistence.transcript_repository import (
    SqlTranscriptRepository,
)
from app.core.config import get_settings

_index: CorpusIndex | None = None
_verrou = asyncio.Lock()


def _now() -> datetime:
    return datetime.now(UTC)


async def get_corpus_index(session: DbSession) -> CorpusIndex:
    global _index
    if _index is not None:
        return _index
    async with _verrou:
        if _index is None:
            try:
                _index = await load_corpus_index(session)
            except CorpusVideError as exc:
                # Traduit en erreur de domaine pour que la réponse dise **quoi faire**
                # plutôt que de rendre une 500 muette : sans corpus, l'installation
                # n'est simplement pas terminée.
                raise CorpusNonSemeError(str(exc)) from exc
    return _index


def reset_corpus_index() -> None:
    """Vide le cache — pour les tests, et après un nouveau semis."""
    global _index
    _index = None


def get_study_service(
    session: DbSession, index: Annotated[CorpusIndex, Depends(get_corpus_index)]
) -> UrimStudyService:
    return UrimStudyService(
        studies=SqlStudyRepository(session),
        reservations=SqlReservationRepository(session),
        access=GroupAccessPreacherAuthorization(
            GroupAccessPolicy(
                SqlOwnershipRepository(session), SqlAlchemyMembershipRepository(session)
            )
        ),
        index=index,
        clock=_now,
        resolver=build_verse_resolver(get_settings()),
        # La seconde passe sur les autres versions détenues — avant le modèle, parce
        # qu'une citation que le corpus possède n'a pas à être devinée.
        ailleurs=SqlCitationAilleurs(session, index),
    )


StudyServiceDep = Annotated[UrimStudyService, Depends(get_study_service)]


def get_capture_service(session: DbSession) -> UrimCaptureService:
    """Le service de la capture — **et il ne dépend pas de l'index du corpus**.

    Recevoir un fragment ne demande ni péricope ni lexique : c'est du transport. Le brancher
    sur `get_corpus_index` ferait échouer un dépôt d'audio sur une installation dont le
    corpus n'est pas semé, un dimanche matin, pour une raison sans rapport."""
    reglages = get_settings()

    return UrimCaptureService(
        captures=SqlCaptureRepository(session),
        fragments=build_fragment_store(reglages),
        access=GroupAccessPreacherAuthorization(
            GroupAccessPolicy(
                SqlOwnershipRepository(session), SqlAlchemyMembershipRepository(session)
            )
        ),
        clock=_now,
        campagne_ouverte=reglages.capture_audio_upload_enabled,
    )


CaptureServiceDep = Annotated[UrimCaptureService, Depends(get_capture_service)]


def get_piece_service(session: DbSession) -> PieceService:
    """Le service de la pièce — **et il ne connaît pas la campagne de mesure**.

    ⚠️ `get_capture_service` porte `campagne_ouverte` : la montée d'audio brut est datée
    (D56), elle se ferme avec la mesure. **Publier une pièce n'a pas de fin de campagne.**
    C'est le produit, pas un instrument de mesure ; le brancher sur le même interrupteur
    éteindrait la publication le jour où la mesure s'achève.

    🔴 **Et les octets vont dans le `MediaStore`, jamais dans le magasin des fragments.**
    Celui-là purge à sept jours ; une pièce ne meurt pas."""
    return PieceService(
        pieces=SqlPieceRepository(session),
        media=MediaPieceAudioStore(build_media_store(get_settings())),
        access=GroupAccessPreacherAuthorization(
            GroupAccessPolicy(
                SqlOwnershipRepository(session), SqlAlchemyMembershipRepository(session)
            )
        ),
        clock=_now,
    )


PieceServiceDep = Annotated[PieceService, Depends(get_piece_service)]


def get_transcript_service(session: DbSession) -> TranscriptService:
    """Recevoir un transcript — **et pas davantage de dépendances que ça n'en demande**.

    Ni index du corpus, ni modèle : le serveur ne transcrit rien (D52), il range du texte. Le
    brancher sur le corpus ferait échouer un dépôt sur une installation dont le corpus n'est
    pas semé, pour une raison sans rapport — même raisonnement que le service de capture."""
    return TranscriptService(
        captures=SqlCaptureRepository(session),
        transcripts=SqlTranscriptRepository(session),
        access=GroupAccessPreacherAuthorization(
            GroupAccessPolicy(
                SqlOwnershipRepository(session), SqlAlchemyMembershipRepository(session)
            )
        ),
        clock=_now,
    )


TranscriptServiceDep = Annotated[TranscriptService, Depends(get_transcript_service)]

#: L'index du corpus, pour les routes qui nomment sans faire tourner le moteur.
CorpusIndexDep = Annotated[CorpusIndex, Depends(get_corpus_index)]


def get_archive_service(
    session: DbSession, index: Annotated[CorpusIndex, Depends(get_corpus_index)]
) -> UrimArchiveService:
    return UrimArchiveService(
        archive=SqlArchiveRepository(session),
        studies=SqlStudyRepository(session),
        access=GroupAccessPreacherAuthorization(
            GroupAccessPolicy(
                SqlOwnershipRepository(session), SqlAlchemyMembershipRepository(session)
            )
        ),
        index=index,
        clock=_now,
    )


ArchiveServiceDep = Annotated[UrimArchiveService, Depends(get_archive_service)]


def get_deliverable_service(
    session: DbSession, index: Annotated[CorpusIndex, Depends(get_corpus_index)]
) -> UrimDeliverableService:
    return UrimDeliverableService(
        studies=SqlStudyRepository(session),
        # La note se bâtit sur le dossier **rejoué** — une seule définition de ce dossier,
        # et ce rejeu ne persiste rien, donc ne consomme rien.
        etude=get_study_service(session, index),
        livrables=SqlDeliverableRepository(session),
        # ⚠️ Le texte des **autres versions** ne vient pas de l'index : il n'en charge qu'une
        # (celle de repli). Q9 exige de juger contre toutes celles qu'on détient.
        versets=SqlVerseTextReader(session),
        access=GroupAccessPreacherAuthorization(
            GroupAccessPolicy(
                SqlOwnershipRepository(session), SqlAlchemyMembershipRepository(session)
            )
        ),
        index=index,
        clock=_now,
    )


DeliverableServiceDep = Annotated[UrimDeliverableService, Depends(get_deliverable_service)]


def get_curation(
    session: DbSession, index: Annotated[CorpusIndex, Depends(get_corpus_index)]
) -> UrimCuration:
    # `reset_corpus_index` passé en dépendance plutôt qu'appelé depuis le service : la purge
    # d'un cache est une affaire d'infrastructure, et le service n'a pas à savoir qu'il en
    # existe un. Sans elle, une curation signée resterait invisible jusqu'au redémarrage.
    return UrimCuration(
        repo=SqlCurationRepository(session),
        index=index,
        invalidate=reset_corpus_index,
    )


CurationDep = Annotated[UrimCuration, Depends(get_curation)]


def get_relecture(session: DbSession) -> Relecture:
    # Pas d'index ici, contrairement à la curation : relire ne crée pas d'unité, donc rien à
    # valider contre le corpus chargé — et rien à purger, tant qu'on ne fait que juger.
    return Relecture(repo=SqlRelectureRepository(session), clock=_now)


RelectureDep = Annotated[Relecture, Depends(get_relecture)]


async def exiger_relecteur(
    session: DbSession,
    x_urim_relecteur: Annotated[str | None, Header()] = None,
) -> Relecteur:
    """**Qui signe** — rendu par le registre, jamais lu dans un corps de requête.

    Le jeton de service Plateforme dit *« la Plateforme »* ; il ne dit pas *« qui »*. Tant que
    `reviewed_by` était un champ de formulaire, aucune vérification ne pouvait empêcher d'y
    écrire le nom de quelqu'un d'autre — et c'est arrivé. Cette dépendance est le point où le
    nom cesse d'être une donnée d'entrée.

    C'est aussi le seul endroit à changer le jour où la console d'administration Dorea existe :
    elle remplacera le couple identifiant/secret par une session de compte staff nominatif, et
    les routes n'en sauront rien."""
    return await RegistreDesRelecteurs(SqlRegistreRepository(session)).identifier(x_urim_relecteur)


RelecteurDep = Annotated[Relecteur, Depends(exiger_relecteur)]
