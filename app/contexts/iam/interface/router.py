"""Routes HTTP du contexte IAM (surface mobile — lecture, et sa propre date).

Le fidèle lit **sa propre** appartenance : l'`account_id` vient de l'acteur
authentifié (`CurrentActor`), jamais de l'URL. Le tenant reste en chemin (un
compte peut appartenir à plusieurs églises).

L'anniversaire suit exactement la même règle, et c'est ce qui le rend sûr : la route de saisie
**n'a pas de paramètre de sujet**. Un responsable ne peut pas renseigner la date de quelqu'un
d'autre parce qu'il n'existe aucune façon de le lui demander — le cas du membre sans smartphone
passe par la saisie assistée de l'onboarding, avec son accord, comme le reste de son profil.
"""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.contexts.auth.interface.dependencies import CurrentActor
from app.contexts.iam.interface.dependencies import (
    BirthdaysTodayDep,
    GetMembershipStatusDep,
    GetMyMembershipsDep,
    GetMyProfileDep,
    JoinChurchByCodeDep,
    SetMyBirthdayDep,
    SetMyLanguageDep,
)
from app.contexts.iam.interface.schemas import (
    BirthdayOfTheDayResponse,
    BirthdayResponse,
    JoinChurchRequest,
    JoinChurchResponse,
    MembershipStatusResponse,
    MyLanguageResponse,
    MyProfileResponse,
    SetMyBirthdayRequest,
    SetMyLanguageRequest,
)

router = APIRouter()


@router.post(
    "/join-church",
    response_model=JoinChurchResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Rejoindre une église par code d'invitation (self-service ; le code autorise)",
)
async def join_church(
    payload: JoinChurchRequest,
    actor: CurrentActor,
    command: JoinChurchByCodeDep,
) -> JoinChurchResponse:
    result = await command.execute(actor_account_id=actor.account_id, code=payload.code)
    return JoinChurchResponse.from_result(result)


@router.get(
    "/me",
    response_model=MyProfileResponse,
    summary="Qui suis-je — mon profil et mes appartenances, en un appel",
)
async def read_my_profile(
    actor: CurrentActor,
    query: GetMyProfileDep,
) -> MyProfileResponse:
    """404 seulement si le compte n'existe plus : le jeton est valide, la personne ne l'est
    plus. Un compte sans église, lui, répond 200 avec `memberships: []`."""
    dto = await query.execute(account_id=actor.account_id)
    if dto is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ACCOUNT_NOT_FOUND")
    return MyProfileResponse.from_dto(dto)


@router.get(
    "/me/memberships",
    response_model=list[MembershipStatusResponse],
    summary="Toutes mes appartenances actives (découverte post-login)",
)
async def read_my_memberships(
    actor: CurrentActor,
    query: GetMyMembershipsDep,
) -> list[MembershipStatusResponse]:
    dtos = await query.execute(account_id=actor.account_id)
    return [MembershipStatusResponse.from_dto(dto) for dto in dtos]


@router.get(
    "/me/tenants/{tenant_id}/membership",
    response_model=MembershipStatusResponse,
    summary="Mon statut d'appartenance et mes rôles actifs dans un tenant",
)
async def read_my_membership_status(
    tenant_id: UUID,
    actor: CurrentActor,
    query: GetMembershipStatusDep,
) -> MembershipStatusResponse:
    dto = await query.execute(account_id=actor.account_id, tenant_id=tenant_id)
    return MembershipStatusResponse.from_dto(dto)


@router.put(
    "/me/birthday",
    response_model=BirthdayResponse,
    summary="Poser ma date de naissance et choisir qui la voit (jamais celle d'un autre)",
)
async def set_my_birthday(
    payload: SetMyBirthdayRequest,
    actor: CurrentActor,
    command: SetMyBirthdayDep,
) -> BirthdayResponse:
    birthday = await command.execute(
        actor_account_id=actor.account_id,
        day=payload.day,
        month=payload.month,
        year=payload.year,
        scope=payload.scope,
    )
    return BirthdayResponse(
        day=birthday.day, month=birthday.month, scope=payload.scope.value
    )


@router.put(
    "/me/language",
    response_model=MyLanguageResponse,
    summary="Choisir la langue dans laquelle Dorea me parle (null = celle de mon église)",
)
async def set_my_language(
    payload: SetMyLanguageRequest,
    actor: CurrentActor,
    command: SetMyLanguageDep,
) -> MyLanguageResponse:
    """Réglage **de personne** : on ne pose jamais la langue de quelqu'un d'autre, ni celle de
    l'église (qui est un acte de gouvernance, sur une autre surface).

    La réponse rend les deux moitiés : le réglage posé, et la langue effective. Quand on revient
    à `null`, seule la seconde dit quelle église prend le relais — et le client l'apprend tout de
    suite plutôt qu'au prochain rafraîchissement."""
    result = await command.execute(
        actor_account_id=actor.account_id, language=payload.language
    )
    return MyLanguageResponse.from_result(result)


@router.get(
    "/me/tenants/{tenant_id}/birthdays",
    response_model=list[BirthdayOfTheDayResponse],
    summary="Les anniversaires du jour dans mes groupes — un encart, pas une notification",
)
async def read_birthdays_today(
    tenant_id: UUID,
    actor: CurrentActor,
    query: BirthdaysTodayDep,
) -> list[BirthdayOfTheDayResponse]:
    """**Rien n'est poussé.** L'encart attend qu'on ouvre l'application : un anniversaire notifié
    à 7 h du matin est le début d'une boucle d'habitude, et le contraire d'un geste.

    Et il n'existe aucune route « souhaiter » : aucun message ne part de Dorea, ni en son nom, ni
    au nom de quiconque."""
    return [
        BirthdayOfTheDayResponse(
            account_id=b.account_id,
            first_name=b.first_name,
            last_name=b.last_name,
            is_today=b.is_today,
        )
        for b in await query.execute(
            viewer_account_id=actor.account_id, tenant_id=tenant_id
        )
    ]
