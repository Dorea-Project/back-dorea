"""Le code morphologique du grec, **rendu lisible** — une table, aucun modèle.

`2FAI-S--` ne dit rien à personne. *« 2ᵉ personne · futur · actif · indicatif · singulier »*
dit tout, et c'est le genre de chose qu'un pasteur veut voir en cliquant sur `Ἀγαπήσεις` :
non pas ce que le mot signifie — le lexique n'est pas là — mais **ce que sa forme fait**. Un
futur à l'indicatif n'est pas un impératif, et prêcher « tu aimeras » comme un ordre ou comme
une promesse ne donne pas le même sermon.

## Pourquoi c'est une table et pas une invite

Le décodage est **total et sans jugement** : chaque position du code a un sens fixé par la
grammaire, pas par le contexte. Un modèle n'apporterait qu'une chance de se tromper là où
une table ne le peut pas, et l'erreur serait invisible — personne ne relit une glose
grammaticale, on la croit.

## Le format MorphGNT

    2FAI-S--
    │││││││└─ degré        (comparatif, superlatif)
    ││││││└── genre        (masculin, féminin, neutre)
    │││││└─── cas          (nominatif, génitif, datif, accusatif, vocatif)
    ││││└──── nombre       (singulier, pluriel)
    │││└───── mode         (indicatif, impératif, subjonctif, optatif, infinitif, participe)
    ││└────── voix         (active, moyenne, passive)
    │└─────── temps        (présent, imparfait, futur, aoriste, parfait, plus-que-parfait)
    └──────── personne     (1, 2, 3)

Un tiret signifie *« sans objet pour cette forme »* — un nom n'a pas de personne. On ne
l'affiche donc pas : une liste de « — » ferait passer une forme simple pour une forme
incomplète.
"""

from __future__ import annotations

#: La nature du mot, première colonne de MorphGNT. Les codes composés (`RA`, `RD`…) sont là
#: parce qu'ils désignent des choses que le français ne distingue pas d'un seul mot.
NATURES = {
    "N-": "nom",
    "V-": "verbe",
    "A-": "adjectif",
    "RA": "article",
    "RD": "pronom démonstratif",
    "RI": "pronom interrogatif ou indéfini",
    "RP": "pronom personnel",
    "RR": "pronom relatif",
    "C-": "conjonction",
    "P-": "préposition",
    "D-": "adverbe",
    "I-": "interjection",
    "X-": "particule",
}

_PERSONNE = {"1": "1ʳᵉ personne", "2": "2ᵉ personne", "3": "3ᵉ personne"}
_TEMPS = {
    "P": "présent", "I": "imparfait", "F": "futur",
    "A": "aoriste", "X": "parfait", "Y": "plus-que-parfait",
}
_VOIX = {"A": "actif", "M": "moyen", "P": "passif"}
_MODE = {
    "I": "indicatif", "D": "impératif", "S": "subjonctif",
    "O": "optatif", "N": "infinitif", "P": "participe",
}
_NOMBRE = {"S": "singulier", "P": "pluriel"}
_CAS = {
    "N": "nominatif", "G": "génitif", "D": "datif",
    "A": "accusatif", "V": "vocatif",
}
_GENRE = {"M": "masculin", "F": "féminin", "N": "neutre"}
_DEGRE = {"C": "comparatif", "S": "superlatif"}

#: Les huit positions, dans l'ordre du code. Le tableau **est** l'algorithme : ajouter une
#: dimension revient à ajouter une ligne, jamais à toucher au décodeur.
#:
#: ⚠️ **Le cas vient AVANT le nombre**, et je l'avais écrit dans l'autre sens. `κύριον`
#: (`----ASM-`) ne rendait alors que « masculin » : le `A` était cherché dans les nombres et
#: le `S` dans les cas, donc les deux tombaient à côté sans que rien ne le signale. C'est le
#: mode de panne propre à un décodage positionnel — il ne casse pas, il appauvrit, et un mot
#: analysé à moitié ressemble à un mot dont la forme est simple.
_POSITIONS = (_PERSONNE, _TEMPS, _VOIX, _MODE, _CAS, _NOMBRE, _GENRE, _DEGRE)


def decrire(code: str | None) -> str:
    """`2FAI-S--` → « 2ᵉ personne · futur · actif · indicatif · singulier ».

    Rend une chaîne vide plutôt qu'un « inconnu » quand le code est absent ou illisible : sur
    cet écran, le silence se comprend, et une étiquette d'erreur ferait douter du texte lui-même.

    Les positions sans objet — un tiret — sont **omises**, pas rendues vides. Un nom n'a pas de
    personne, et afficher « — » huit fois ferait passer une forme simple pour une forme
    incomplète."""
    if not code:
        return ""
    lu = [
        table[caractere]
        for caractere, table in zip(code, _POSITIONS, strict=False)
        if caractere in table
    ]
    return " · ".join(lu)


def nature(code: str | None) -> str:
    """`V-` → « verbe ». Vide si la nature est absente — même règle que `decrire`."""
    return NATURES.get((code or "").strip(), "")
