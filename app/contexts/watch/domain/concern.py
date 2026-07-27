"""Le signalement par un tiers — et pourquoi son contenu est presque vide.

Jean sait déjà. Il le sait depuis trois semaines, et il n'a rien fait — non par négligence, mais
parce que **savoir ne crée aucune obligation**. Le geste ne transporte donc aucune information
nouvelle vers le système : il convertit un savoir privé en **un cas daté, attribué, qu'il faudra
fermer**.

> L'intuition n'est pas une source de données. C'est un dispositif d'engagement que le
> responsable se pose à lui-même.

Tout ce module en découle. **Aucun texte libre** : un champ libre sur une personne devient une
fiche, et il survivra au responsable qui l'a écrite. Reste une liste **fermée** de nuances, qui
portent sur la *relation* — jamais sur la personne, et jamais sur un état intérieur supposé.

La nuance n'existe que pour un cas : si le cas est **transféré ou escaladé**, le suivant reçoit
de quoi comprendre. Sans elle il reçoit un cas muet.
"""

from __future__ import annotations

import re
from enum import StrEnum


class Nuance(StrEnum):
    """Liste **fermée**. Chaque membre décrit ce qu'on observe du lien, pas ce qu'on suppose."""

    NO_NEWS = "no_news"
    PARTICIPATES_LESS = "participates_less"
    SOMETHING_CHANGED = "something_changed"


# Les mots du déclarant, à la première personne. Ils voyagent tels quels jusqu'à l'écran, entre
# guillemets : c'est ce qui les garde du côté du témoignage et non du diagnostic.
NUANCE_LABELS: dict[Nuance, str] = {
    Nuance.NO_NEWS: "je n'ai pas eu de nouvelles",
    Nuance.PARTICIPATES_LESS: "il ne participe plus comme avant",
    Nuance.SOMETHING_CHANGED: "quelque chose a changé, je ne sais pas quoi",
}


# Le grillage — même dispositif que `FORBIDDEN_KIND_PATTERNS` du ledger, appliqué au vocabulaire
# des nuances. Un état intérieur (*m'a semblé triste*, *paraît déprimé*, *va mal*) n'est pas une
# observation : c'est une supposition, et écrite elle devient une note sur quelqu'un. La règle
# n'est pas une convention de relecture — la suite d'invariants balaie l'enum entier, donc une
# nuance de cette famille fait échouer les tests, pas la revue de code.
FORBIDDEN_NUANCE_PATTERNS: tuple[str, ...] = (
    r"(sad|depress|anxious|unwell|struggling|suffer|fragile|lonely|angry|mood|feel)",
    r"(triste|déprim|depriv|anxieu|souffr|mal_|_mal|fragile|seul|colère|humeur|ressen)",
)


def forbidden_nuance(text: str) -> bool:
    """True si ce libellé décrit un état intérieur supposé plutôt qu'une relation observée."""
    return any(re.search(p, text, re.IGNORECASE) for p in FORBIDDEN_NUANCE_PATTERNS)


def quote(nuance: Nuance | None) -> str:
    """La nuance telle qu'elle s'ajoutera au motif du cas, ou rien."""
    return f" « {NUANCE_LABELS[nuance]} »" if nuance is not None else ""
