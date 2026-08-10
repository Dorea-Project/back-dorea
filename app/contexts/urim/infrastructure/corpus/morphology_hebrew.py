"""Le code morphologique de l'hébreu, **rendu lisible** — une table, comme pour le grec.

`HR/Ncfsa` ne dit rien à personne. *« préposition · nom commun féminin singulier absolu »* dit
que `בְּרֵאשִׁית` n'est pas un mot mais deux morphèmes collés : la préposition *be-* et le nom
*rechit*. C'est ce qu'un pasteur veut voir en cliquant, et c'est ce qu'aucune traduction ne
lui montre.

## Ce que ce format a de différent du grec

Le grec range huit dimensions à **position fixe** — un tiret quand la dimension ne s'applique
pas. L'hébreu, lui, **empile des morphèmes** : un seul mot écrit porte souvent une conjonction,
un article, un nom et un suffixe possessif, séparés par `/`. Le décodage est donc une boucle
sur les morphèmes, et chacun commence par sa nature.

    H  C/Td/Ncbsa
    │  │ │  └──── nom commun, féminin-ou-masculin, singulier, absolu
    │  │ └─────── article défini
    │  └───────── conjonction
    └──────────── la langue (H hébreu, A araméen)

## La même règle que partout : une table, jamais un modèle

Un modèle glosant une morphologie de mémoire produit des erreurs qu'un pasteur répète en chaire
avec assurance, parce que personne ne relit une analyse grammaticale. Ce qui n'est pas dans la
table rend une chaîne vide — le silence se comprend, une étiquette d'erreur ferait douter du
texte lui-même.
"""

from __future__ import annotations

#: La nature, première lettre de chaque morphème.
_NATURES = {
    "A": "adjectif", "C": "conjonction", "D": "adverbe", "N": "nom",
    "P": "pronom", "R": "préposition", "S": "suffixe", "T": "particule",
    "V": "verbe",
}

#: Le second caractère précise la nature — un nom **commun** n'est pas un nom **propre**, et
#: une particule interrogative n'est pas une négation.
_SOUS_NATURES = {
    ("A", "a"): "adjectif", ("A", "c"): "adjectif cardinal",
    ("A", "g"): "adjectif gentilé", ("A", "o"): "adjectif ordinal",
    ("N", "c"): "nom commun", ("N", "p"): "nom propre",
    ("P", "d"): "pronom démonstratif", ("P", "f"): "pronom indéfini",
    ("P", "i"): "pronom interrogatif", ("P", "p"): "pronom personnel",
    ("P", "r"): "pronom relatif",
    ("T", "a"): "particule affirmative", ("T", "d"): "article défini",
    ("T", "e"): "particule exhortative", ("T", "i"): "particule interrogative",
    ("T", "j"): "particule interjective", ("T", "m"): "particule démonstrative",
    ("T", "n"): "négation", ("T", "o"): "marqueur d'objet direct",
    ("T", "r"): "particule relative",
    ("S", "d"): "suffixe directionnel", ("S", "h"): "suffixe paragogique",
    ("S", "n"): "suffixe pronominal", ("S", "p"): "suffixe pronominal",
}

#: Les racines verbales — c'est **la** dimension propre à l'hébreu, et celle qui change le sens.
#: Un piel n'est pas un qal intensifié par hasard : « briser » y devient « fracasser ».
_RACINES = {
    "q": "qal", "N": "nifal", "p": "piel", "P": "poual", "h": "hifil",
    "H": "hofal", "t": "hitpael", "o": "polel", "O": "polal", "r": "hitpolel",
    "m": "poel", "M": "poal", "k": "palel", "K": "pulal", "Q": "qal passif",
    "l": "pilpel", "L": "polpal", "f": "hitpalpel", "D": "nitpael",
    "j": "pealal", "i": "pilel", "u": "hotpaal", "c": "tifil", "v": "histafel",
    "w": "nitpalel", "y": "nitpoel", "z": "hitpoel",
}

#: Le temps ou le mode du verbe.
_ASPECTS = {
    "p": "parfait", "q": "parfait consécutif", "i": "inaccompli",
    "w": "inaccompli consécutif", "h": "cohortatif", "j": "jussif",
    "v": "impératif", "r": "participe actif", "s": "participe passif",
    "a": "infinitif absolu", "c": "infinitif construit",
}

_PERSONNES = {"1": "1ʳᵉ personne", "2": "2ᵉ personne", "3": "3ᵉ personne"}
_GENRES = {"b": "masculin ou féminin", "c": "commun", "f": "féminin", "m": "masculin"}
_NOMBRES = {"s": "singulier", "p": "pluriel", "d": "duel"}
_ETATS = {"a": "absolu", "c": "construit", "d": "déterminé"}


def _un_morpheme(code: str) -> str:
    """Un morphème → sa description, ou une chaîne vide s'il est illisible."""
    if not code:
        return ""
    nature = code[0]
    if nature == "V":
        return _un_verbe(code)

    lu = [_SOUS_NATURES.get((nature, code[1:2])) or _NATURES.get(nature, "")]
    # Après la nature et sa précision, ce qui reste décrit la forme : genre, nombre, état.
    for caractere in code[2:]:
        for table in (_GENRES, _NOMBRES, _ETATS, _PERSONNES):
            if caractere in table:
                lu.append(table[caractere])
                break
    return " ".join(part for part in lu if part)


def _un_verbe(code: str) -> str:
    """Le verbe, à part — sa **racine** vient avant son aspect, et elle change le sens.

    `Vqp3ms` : qal, parfait, 3ᵉ personne masculin singulier. La racine d'abord parce que c'est
    elle qu'un pasteur cherche : un piel n'est pas un qal plus fort, c'est un autre verbe."""
    lu = ["verbe"]
    if len(code) > 1 and code[1] in _RACINES:
        lu.append(_RACINES[code[1]])
    if len(code) > 2 and code[2] in _ASPECTS:
        lu.append(_ASPECTS[code[2]])
    for caractere in code[3:]:
        for table in (_PERSONNES, _GENRES, _NOMBRES, _ETATS):
            if caractere in table:
                lu.append(table[caractere])
                break
    return " ".join(lu)


def decrire(code: str | None) -> str:
    """`HR/Ncfsa` → « préposition · nom commun féminin singulier absolu ».

    Les morphèmes sont séparés par ` · ` comme les dimensions du grec : le pasteur lit une
    suite de précisions, peu lui importe que l'une vienne d'une position et l'autre d'un
    morphème."""
    if not code:
        return ""
    corps = code[1:] if code[:1] in ("H", "A") else code
    lus = [_un_morpheme(morpheme) for morpheme in corps.split("/")]
    return " · ".join(part for part in lus if part)


def nature(code: str | None) -> str:
    """La nature du **dernier** morphème — celui qui porte le mot.

    `HC/Td/Ncbsa` est un nom : la conjonction et l'article sont des préfixes collés. Rendre
    « conjonction » ferait passer le mot pour ce qu'il n'est pas."""
    if not code:
        return ""
    corps = code[1:] if code[:1] in ("H", "A") else code
    dernier = corps.split("/")[-1]
    return _SOUS_NATURES.get((dernier[:1], dernier[1:2])) or _NATURES.get(dernier[:1], "")
