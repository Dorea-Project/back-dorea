"""Poser sa date, et voir celles du jour — **calculé à la lecture**, sans échéance ni worker.

Deux services minuscules, et l'essentiel de leur travail est de **refuser** :

- `SetMyBirthday` n'accepte que sa propre date. Un responsable ne renseigne pas celle d'un autre —
  le cas du membre sans smartphone passe par la saisie assistée de l'onboarding, avec son accord,
  comme le reste de son profil.
- `BirthdaysToday` n'affiche que ce que chacun a accepté de montrer, et **jamais l'année**.

Ce qu'ils ne font pas, et qui est écrit ici pour que ça se voie :

- **pas de push.** L'encart attend qu'on ouvre l'application. Un anniversaire poussé à 7 h du matin
  est le début d'une boucle d'habitude — et le contraire d'un geste ;
- **pas de bouton « souhaiter ».** Aucun message ne part de Dorea, ni en son nom, ni au nom de
  quiconque. L'encart porte le bouton d'appel standard, celui de partout ailleurs ;
- **pas d'agrégation rétrospective.** Aucun écran « anniversaires du mois », aucune liste
  exportable. La liste des dates de naissance d'un groupe est une donnée de fichier ; l'encart du
  jour est une attention. On livre la seconde.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from uuid import UUID

from app.contexts.iam.domain.birthday import Birthday, BirthdayScope


@dataclass(frozen=True)
class BirthdayOfTheDay:
    """Ce qui s'affiche : un nom, et le fait que c'est aujourd'hui ou demain.

    **Aucune année, aucun âge.** Le DTO n'a pas de champ pour le dire."""

    account_id: UUID
    first_name: str | None
    last_name: str | None
    is_today: bool  # False = demain, réservé au référent (J-1)


class BirthdayDirectory(ABC):
    """Ce que la lecture des anniversaires a besoin de savoir du reste du produit."""

    @abstractmethod
    async def candidates(self, *, viewer_account_id: UUID, tenant_id: UUID) -> list:
        """Les personnes dont le viewer pourrait voir l'anniversaire : celles de ses groupes.

        Renvoie des tuples `(account_id, first_name, last_name, day, month, scope)` — **jamais
        l'année** : elle ne sort pas de la base."""
        ...

    @abstractmethod
    async def referent_of(self, account_id: UUID, tenant_id: UUID) -> UUID | None:
        """Qui veille sur cette personne — pour le réglage `REFERENT_ONLY`."""
        ...


class SetMyBirthday:
    """Sa date, posée par elle. Le service ne prend pas d'identifiant de sujet."""

    def __init__(self, accounts, *, clock=None) -> None:
        self._accounts = accounts
        self._clock = clock

    async def execute(
        self,
        *,
        actor_account_id: UUID,
        day: int,
        month: int,
        year: int | None = None,
        scope: BirthdayScope = BirthdayScope.GROUPS,
    ) -> Birthday:
        birthday = Birthday(day=day, month=month)  # lève si la date n'existe pas
        await self._accounts.set_birthday(
            account_id=actor_account_id,
            day=birthday.day,
            month=birthday.month,
            year=year,
            scope=scope.value,
        )
        return birthday


class BirthdaysToday:
    """L'encart, calculé à la lecture : une requête sur les dates du jour, rien de plus."""

    def __init__(self, directory: BirthdayDirectory, *, clock) -> None:
        self._directory = directory
        self._clock = clock

    async def execute(
        self, *, viewer_account_id: UUID, tenant_id: UUID
    ) -> list[BirthdayOfTheDay]:
        today = self._clock().date()
        tomorrow = date.fromordinal(today.toordinal() + 1)
        rows = await self._directory.candidates(
            viewer_account_id=viewer_account_id, tenant_id=tenant_id
        )

        found: list[BirthdayOfTheDay] = []
        for account_id, first_name, last_name, day, month, scope in rows:
            if day is None or month is None:
                continue  # ne pas renseigner sa date équivaut à `HIDDEN`
            visibility = BirthdayScope(scope or BirthdayScope.GROUPS.value)
            if visibility is BirthdayScope.HIDDEN:
                continue  # absolu : ni l'encart, ni le pasteur, ni l'assistant
            birthday = Birthday(day=day, month=month)

            is_today = birthday.falls_on(today)
            # **J-1 est réservé au référent.** Prévenir la veille est utile à celui qui prépare un
            # geste ; à tout le groupe, ça devient un rappel de plus.
            is_referent = await self._is_referent(viewer_account_id, account_id, tenant_id)
            shows_tomorrow = is_referent and birthday.falls_on(tomorrow)
            if not (is_today or shows_tomorrow):
                continue
            if visibility is BirthdayScope.REFERENT_ONLY and not is_referent:
                continue
            if account_id == viewer_account_id:
                continue  # on ne se souhaite pas son propre anniversaire

            found.append(
                BirthdayOfTheDay(
                    account_id=account_id,
                    first_name=first_name,
                    last_name=last_name,
                    is_today=is_today,
                )
            )
        return found

    async def _is_referent(self, viewer: UUID, subject: UUID, tenant_id: UUID) -> bool:
        return await self._directory.referent_of(subject, tenant_id) == viewer
