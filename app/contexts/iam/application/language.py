"""Poser sa langue — **ou reprendre celle de son église**, ce qui est un choix et non un vide.

`accounts.language` existait depuis L-0 et personne ne pouvait l'écrire : tout le monde héritait
encore de son église. Ce service est la porte qui manquait.

**Ce qu'il refuse, et pourquoi c'est l'essentiel :**

- **Il n'accepte que sa propre langue.** Comme `SetMyBirthday`. Un responsable ne décide pas dans
  quelle langue on parle à quelqu'un d'autre — c'est un réglage de personne, pas d'encadrement.
  Le membre sans smartphone passe par la saisie assistée de l'onboarding, avec son accord, comme
  le reste de son profil.
- **Il ne touche jamais `tenants.language`.** Poser sa langue, c'est parler pour soi. Changer
  celle de l'église est un acte de gouvernance, sur une autre surface.

🔴 **`None` n'est pas l'absence de réponse : c'est la réponse *« celle de mon église »*.** La
distinction porte tout le modèle à deux étages. Un membre qui a mis l'anglais puis revient à
`None` ne « efface » pas un réglage — il redit qu'il suit son assemblée, y compris le jour où
elle change de langue. C'est pourquoi la route accepte `null` comme une valeur ordinaire et non
comme un champ omis.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from uuid import UUID

from app._shared.domain.locale import Locale


class LanguageStore(ABC):
    @abstractmethod
    async def set_language(self, *, account_id: UUID, language: Locale | None) -> None:
        """Écrit (ou efface) la langue **de ce compte**. Aucun autre identifiant n'entre ici."""
        ...


@dataclass(frozen=True, slots=True)
class MyLanguage:
    """Les deux moitiés de la réponse, et elles ne disent pas la même chose.

    `chosen` est le réglage — `None` quand la personne suit son église. `resolved` est ce que
    Dorea **utilise vraiment**, une fois la chaîne parcourue. Le client a besoin des deux : le
    premier pour cocher la bonne case, le second pour savoir dans quelle langue il parlera si
    jamais il rend quelque chose lui-même."""

    chosen: Locale | None
    resolved: Locale


class SetMyLanguage:
    def __init__(self, store: LanguageStore, locales) -> None:
        self._store = store
        self._locales = locales

    async def execute(self, *, actor_account_id: UUID, language: Locale | None) -> MyLanguage:
        await self._store.set_language(account_id=actor_account_id, language=language)
        # On relit la chaîne plutôt que de déduire : quand la personne repasse à `None`, seule
        # la résolution sait quelle église prend le relais — et le client doit l'apprendre tout
        # de suite, pas au prochain rafraîchissement.
        return MyLanguage(
            chosen=language, resolved=await self._locales.resolve(actor_account_id)
        )
