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
from app.contexts.tenant.infrastructure.persistence.ownership_repo import (
    SqlOwnershipRepository,
)
from app.contexts.urim.adapters.authorization import GroupAccessPreacherAuthorization
from app.contexts.urim.adapters.mistral import build_verse_resolver
from app.contexts.urim.application.curation import UrimCuration
from app.contexts.urim.application.relecture import (
    RegistreDesRelecteurs,
    Relecteur,
    Relecture,
)
from app.contexts.urim.application.study_service import UrimStudyService
from app.contexts.urim.domain.errors import CorpusNonSemeError
from app.contexts.urim.infrastructure.corpus.index import (
    CorpusIndex,
    CorpusVideError,
    load_corpus_index,
)
from app.contexts.urim.infrastructure.persistence.curation_repository import (
    SqlCurationRepository,
)
from app.contexts.urim.infrastructure.persistence.relecture_repository import (
    SqlRegistreRepository,
    SqlRelectureRepository,
)
from app.contexts.urim.infrastructure.persistence.study_repository import (
    SqlReservationRepository,
    SqlStudyRepository,
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
    )


StudyServiceDep = Annotated[UrimStudyService, Depends(get_study_service)]


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
    return await RegistreDesRelecteurs(SqlRegistreRepository(session)).identifier(
        x_urim_relecteur
    )


RelecteurDep = Annotated[Relecteur, Depends(exiger_relecteur)]
