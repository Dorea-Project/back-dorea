"""La **phonétique** d'un mot d'origine — et pourquoi elle est permise là où la traduction ne
l'est pas.

Un pasteur qui lit `πρῶτος` sans connaître l'alphabet grec ne peut ni le dire en chaire, ni le
retenir, ni le chercher ailleurs. Le mot lui reste étranger même quand il est sous ses yeux.

> **Translittérer n'est pas traduire.** C'est une transformation **mécanique** des lettres :
> aucune affirmation sur le sens, donc rien à inventer et rien à vérifier. La règle qui interdit
> la glose produite par un modèle ne s'y applique pas — et c'est pourquoi cette pièce peut
> exister aujourd'hui, alors que le sens attend un lexique.

## Ce que la table fait, et ne fait pas

Elle rend une **prononciation d'usage**, celle des lexiques et des manuels — `prôtos`,
`logos`, `agapè`. Elle ne prétend pas restituer la phonologie du grec du Ier siècle, qui est un
débat de spécialistes et n'aiderait personne à dire le mot à voix haute.

Deux points qui se voient si on les rate :

- **l'esprit rude** (῾) devient un `h` initial — `ἑορτή` → `heortè`. Il est porté par un
  caractère combinant qu'on lit **avant** de replier les accents, sinon il disparaît sans
  laisser de trace ;
- **γ devant une gutturale** se dit `n` — `ἄγγελος` → `angelos`, jamais `aggelos`. C'est la
  règle que tout le monde connaît par un seul mot, et l'oublier rend le résultat risible
  exactement là où il sera le plus lu.
"""

from __future__ import annotations

import unicodedata

#: L'esprit rude, combinant. Lu avant que `NFD` ne soit replié.
_ESPRIT_RUDE = "̔"

_GREC = {
    "α": "a", "β": "b", "γ": "g", "δ": "d", "ε": "e", "ζ": "z", "η": "è", "θ": "th",
    "ι": "i", "κ": "k", "λ": "l", "μ": "m", "ν": "n", "ξ": "x", "ο": "o", "π": "p",
    "ρ": "r", "σ": "s", "ς": "s", "τ": "t", "υ": "u", "φ": "ph", "χ": "ch", "ψ": "ps",
    "ω": "ô",
}

#: Les diphtongues, résolues **avant** les lettres seules — sinon `ου` donnerait `ou` par
#: hasard et `ευ` donnerait `eu` par erreur.
_DIPHTONGUES = {
    "ου": "ou", "ευ": "eu", "αυ": "au", "ηυ": "èu",
    "αι": "ai", "ει": "ei", "οι": "oi", "υι": "ui",
}

#: γ + gutturale = `n`. La règle d'ἄγγελος.
_GUTTURALES = {"γ", "κ", "χ", "ξ"}


def phonetique(mot: str, langue: str = "grc") -> str:
    """`πρῶτος` → `prôtos`. **Vide** pour une langue qu'on ne sait pas transcrire.

    ⚠️ Rendre une chaîne approximative pour l'hébreu serait pire que ne rien rendre : un
    pasteur qui prononce de travers devant son assemblée ne peut pas le savoir, et personne ne
    le corrigera."""
    if langue != "grc" or not mot:
        return ""

    decompose = unicodedata.normalize("NFD", mot)
    rude = _ESPRIT_RUDE in decompose[:3]
    nu = "".join(
        c for c in decompose if unicodedata.category(c) != "Mn"
    ).casefold().strip(",.;·:!?")

    sortie: list[str] = []
    i = 0
    while i < len(nu):
        paire = nu[i:i + 2]
        if paire in _DIPHTONGUES:
            sortie.append(_DIPHTONGUES[paire])
            i += 2
            continue
        lettre = nu[i]
        if lettre == "γ" and nu[i + 1:i + 2] in _GUTTURALES:
            sortie.append("n")
        else:
            sortie.append(_GREC.get(lettre, lettre))
        i += 1

    rendu = "".join(sortie)
    return f"h{rendu}" if rude else rendu
