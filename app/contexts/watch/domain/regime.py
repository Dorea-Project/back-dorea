"""Le **régime de rodage** d'une église — ce que Dorea s'autorise à dire, et quand.

Une église qui installe Dorea n'a jamais vu ses propres seuils. Lui envoyer des cas dès le premier
jour, c'est lui demander de faire confiance à des nombres que personne n'a mesurés chez elle — et
le premier faux positif coûte plus cher que les dix vrais qui suivront.

> **Toute église nouvelle démarre en `SHADOW`.** *Dorea s'accorde à votre église avant de parler.*

Trois régimes, et un seul est livré pour l'instant :

| Régime | Ce que ça change |
| :-- | :-- |
| `SHADOW` | le pipeline tourne **entier**, aucun cas n'atteint un responsable ; le pasteur
  reçoit « voici ce que Dorea aurait signalé » |
| `ASSISTED` | les cas sont émis ; une proposition de calibration attend une approbation |
| `STEADY` | comme `ASSISTED`, mais les propositions dans des bornes dures s'appliquent seules |

**Ce que `SHADOW` n'est pas.** Ce n'est pas un mode dégradé, ni un interrupteur qui éteint la
détection : tout est détecté, tout est journalisé, tout est écrit. Seule la **sortie** est retenue.
C'est la différence entre « Dorea ne fonctionne pas encore » et « Dorea observe » — et c'est aussi
pourquoi il réutilise le canal `HELD` existant plutôt que d'inventer un état : *détecté mais non
émis* est déjà un concept du moteur. La machine à états ne bouge pas ; on ajoute seulement une
**raison** de rétention, pour ne pas confondre « retenu par le plafond du responsable » avec
« retenu parce que l'église est en rodage ».
"""

from __future__ import annotations

from enum import StrEnum


class TenantRegime(StrEnum):
    SHADOW = "shadow"
    ASSISTED = "assisted"
    STEADY = "steady"

    @property
    def emits(self) -> bool:
        """Ce régime laisse-t-il un cas atteindre un responsable ?"""
        return self is not TenantRegime.SHADOW


class HeldReason(StrEnum):
    """**Pourquoi** un cas détecté n'a pas été émis. Deux causes, deux traitements opposés.

    Confondre les deux serait le pire bug possible de ce module : la passe nocturne relâche ce que
    le plafond retient — si elle relâchait aussi ce que le rodage retient, une église en `SHADOW`
    se mettrait à parler toute seule pendant la nuit."""

    CAP = "cap"  # le responsable est à son plafond ; ça sortira quand la place se libérera
    SHADOW = "shadow"  # l'église est en rodage ; ça ne sortira pas avant qu'elle le décide


# Le régime d'une église qui n'en a jamais choisi. L'absence de ligne **est** la réponse : on ne
# dépend pas d'une migration de données ni d'un provisionnement pour que le rodage soit le défaut.
DEFAULT_REGIME: TenantRegime = TenantRegime.SHADOW
