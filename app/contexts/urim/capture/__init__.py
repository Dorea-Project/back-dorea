"""`urim/capture/` — **le mur avant le module**.

Le module de capture n'existe pas encore : sa spec référence quatre tables que personne n'a
définies (S31), et un verrou interne impose l'étape 1 seule — capture, transport, transcript brut
**non exploité** — jusqu'à mesure du taux d'erreur dans trois églises réelles.

Ce fichier n'attend pas le module. Il porte la règle que le module devra respecter, et il la porte
**maintenant**, parce que S29 a nommé le risque avec précision :

> Elle sera « corrigée » par le premier développeur qui trouvera utile de donner le plan au
> modèle « pour qu'il comprenne mieux ».
> **Elle doit être un test, pas une phrase.**

---

## Le quatrième mur — `plan ↮ modèle`

Les trois autres murs séparent des **contextes** : `finance`, `watch`, `urim`, six directions,
toutes gardées. Celui-ci est **interne à Urim**, et il ne sépare pas deux modules — il sépare le
**module** du **modèle**.

> **Le modèle ne voit jamais la préparation.**

S'il reçoit le plan, il décrira le sermon comme ayant suivi le plan. C'est le mode d'hallucination
le plus prévisible ici, et le plus coûteux : il **fabrique la conformité**, et détruit exactement
ce que le Retour existe pour montrer — l'écart entre ce qui était préparé et ce qui a été dit.

**La nuance à ne pas perdre**, et c'est elle qui rend le mur difficile à tenir :

| Qui lit la préparation | Verdict |
| :-- | :-- |
| le **module** — alignement déterministe sur les versets d'ancrage (§6) | ✅ **légitime** |
| le **modèle** — le plan dans son contexte d'entrée | ⛔ **interdit** |

C'est le parallèle exact de S11 côté veille : le mur porte sur **l'entrée du modèle**, pas sur
l'accès du module. Quelqu'un qui lit vite conclura que « le module lit déjà le plan, autant le
passer au modèle » — et c'est précisément cette phrase que le test doit rendre impossible à écrire.
"""

from __future__ import annotations

#: Les noms d'attribut qui trahissent une préparation, et qu'**aucun constructeur de prompt** ne
#: doit lire. Source de vérité du test d'architecture — le pendant de
#: `EngineDeps.FORBIDDEN_FOR_STAGES`, qui garde le mur `watch → urim` par la même mécanique.
#:
#: Ajouter un nom ici est gratuit ; en retirer un demande de justifier pourquoi le modèle aurait
#: besoin de le voir.
FORBIDDEN_IN_MODEL_PROMPT: frozenset[str] = frozenset(
    {
        "preparation",
        "preparation_element",
        "plan",
        "outline",
        "skeleton",
        "squelette",
    }
)
