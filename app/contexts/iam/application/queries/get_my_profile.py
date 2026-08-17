"""Use case (requête) : **qui suis-je ?** — le profil et les appartenances en un appel.

Le premier écran d'une application mobile dit *« Continuer en tant que Kouassi »*. Pour cela
il lui fallait jusqu'ici deux appels et une devinette : `me/memberships` donne les églises et
rien de la personne, et le prénom ne se lisait nulle part.

## Ce que cette requête refuse de faire

**Elle ne compose pas un profil Urim.** La règle de placement du domaine utilisateur est
qu'une donnée vraie de la personne vit dans le noyau, et qu'une donnée qui n'a de sens que
pour préparer vit dans Urim. Le prénom, le téléphone, la date de naissance sont vrais de la
personne : ils sont ici, et Urim les **lit** sans jamais les recopier. Une seconde source de
vérité sur quelqu'un divergerait au premier changement de nom.

**Elle n'expose pas l'âge.** `birth_year` existe en base, optionnelle, et n'est affichée nulle
part — l'âge de quelqu'un n'est pas une donnée d'église. On rend le jour et le mois, qui
suffisent à souhaiter.

**Une liste d'appartenances vide est une réponse.** Un compte sans église est un état normal :
Urim s'installe seul, et le pasteur qui ne rejoint aucune église prépare quand même.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app._shared.domain.locale import Locale, parse_locale
from app.contexts.iam.application.dtos import MembershipStatusDTO
from app.contexts.iam.application.ports import LocaleResolver, ProfileReader
from app.contexts.iam.application.queries.get_my_memberships import GetMyMemberships


@dataclass(frozen=True, slots=True)
class MyProfileDTO:
    """La personne, et où elle appartient.

    `birthday_scope` voyage avec la date parce qu'un réglage de visibilité qu'on ne voit pas
    est un réglage qu'on croit ne pas avoir posé."""

    account_id: UUID
    first_name: str | None
    last_name: str | None
    phone_number: str
    email: str | None
    birth_day: int | None
    birth_month: int | None
    birthday_scope: str
    #: Le **réglage** — `None` quand la personne suit son église.
    language: Locale | None = None
    #: Ce que Dorea **utilise vraiment**, chaîne parcourue. Les deux voyagent ensemble parce
    #: qu'ils ne disent pas la même chose : sans le premier, l'écran de réglage ne sait pas
    #: quelle case cocher ; sans le second, personne ne peut dire *pourquoi* c'est cette
    #: langue-là — et « je n'ai rien choisi » se confondrait avec « on m'a mis en français ».
    resolved_language: Locale = Locale.FR
    memberships: tuple[MembershipStatusDTO, ...] = ()


class GetMyProfile:
    def __init__(
        self,
        profiles: ProfileReader,
        memberships: GetMyMemberships,
        locales: LocaleResolver | None = None,
    ) -> None:
        self._profiles = profiles
        self._memberships = memberships
        self._locales = locales

    async def execute(self, *, account_id: UUID) -> MyProfileDTO | None:
        profil = await self._profiles.read(account_id)
        if profil is None:
            return None
        appartenances = await self._memberships.execute(account_id=account_id)
        return MyProfileDTO(
            account_id=profil.account_id,
            first_name=profil.first_name,
            last_name=profil.last_name,
            phone_number=profil.phone_number,
            email=profil.email,
            birth_day=profil.birth_day,
            birth_month=profil.birth_month,
            birthday_scope=profil.birthday_scope,
            language=parse_locale(profil.language),
            resolved_language=(
                await self._locales.resolve(account_id)
                if self._locales is not None
                else Locale.FR
            ),
            memberships=tuple(appartenances),
        )
