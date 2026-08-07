"""`EcclesialContextPort` — la seule porte vers le reste du système.

⚠️ **AFFICHAGE SEUL.** Ce port est passé à la couche de présentation, **jamais consommé par
un étage du moteur**. Un texte se choisit sur le texte, pas sur les tourments de l'assemblée :
le jour où un étage lit ce port, Dorea propose un thème à partir de la veille — exactement ce
que le produit refuse. Un test l'interdit par inspection du bytecode
(`test_aucun_etage_ne_lit_le_contexte_ecclesial`).

Ce qui traverse : des événements d'une **liste blanche** de huit types, et des agrégats
**non nominatifs** au-dessus du seuil de cinq. Ce qui ne traverse **jamais** : un cas pastoral,
sous quelque forme que ce soit. Et rien ne repart : une préparation ne crée ni fait, ni cas,
ni signal.

Seul `calendar/adapters/` a le droit d'importer hors de `urim`.

---

**La frontière porte sur l'initiative de la MACHINE, pas sur la parole du pasteur** (S11).

Le pasteur peut écrire « il y a trop de malades dans l'église, malgré les prières rien ne va » :
il porte lui-même la situation de son assemblée dans sa conviction, et c'est **légitime** — il en
est l'auteur, il en répond. Ce qui est **interdit**, c'est que le moteur aille **corroborer** cette
phrase dans les agrégats (« effectivement, douze signalements maladie ce mois-ci ») pour pondérer
ses propositions. Le moteur prend la parole du pasteur comme point de départ, **sans la vérifier**.

**Le cas d'école — « la veille annonce 30 décisions »** (S13). Après une évangélisation, trente
personnes décident de suivre Jésus. Dans le système, ce sont **trente cas nominatifs** (`mission`
écrit dans `watch`). Ce qui franchit la frontière est un agrégat : *30, décisions de foi, 7 jours*.
Urim l'**affiche à côté du texte**. Aucun étage ne le lit.

C'est le test le plus dur de la règle, **parce qu'ici l'usage serait bon** : « trente convertis →
proposons les fondements, la nouvelle naissance » est ce qu'un bon pasteur ferait. Et c'est
précisément pour ça qu'il faut refuser : le jour où le moteur propose un texte à partir de ce que
la veille sait, il n'y a plus de ligne — trente conversions aujourd'hui, douze maladies demain,
quatre divorces la semaine suivante. **Le sermon deviendrait une fonction de la donnée pastorale.**

Le résultat est pourtant le même : le pasteur **voit** « 30 décisions », en tire lui-même la
conclusion, et saisit `1 Pierre 2:2` ou une conviction. L'information a traversé — **par un homme
qui en répond**, pas par un mapping dont personne n'est l'auteur.

> **Le signal informe l'homme. L'homme commande la machine.**
> **Jamais le signal ne commande la machine.**
>
> Le mur ne rend pas l'information inutile : il rend le pasteur **responsable de ce qu'il en fait**.
"""

from __future__ import annotations

from datetime import date
from typing import Protocol
from uuid import UUID

from app.contexts.urim.calendar.domain.models import AggregateSignal, EcclesialEvent


class EcclesialContextPort(Protocol):
    """Le contexte de l'église, pour **montrer** — jamais pour décider."""

    def events_between(
        self, church_id: UUID, start: date, end: date
    ) -> tuple[EcclesialEvent, ...]:
        """Événements déclarés (liste blanche de sept types)."""
        ...

    def aggregate_signals(self, church_id: UUID) -> tuple[AggregateSignal, ...]:
        """Agrégats non nominatifs, au-dessus du seuil de cinq."""
        ...


class NullEcclesialContext:
    """Adaptateur nul — le défaut. Aucun contexte, aucune fuite, aucune dépendance.

    C'est lui qui tourne tant qu'aucun adaptateur réel n'est câblé : Urim fonctionne
    entièrement sans le reste du système."""

    def events_between(
        self, church_id: UUID, start: date, end: date
    ) -> tuple[EcclesialEvent, ...]:
        return ()

    def aggregate_signals(self, church_id: UUID) -> tuple[AggregateSignal, ...]:
        return ()
