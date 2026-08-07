"""Le normaliseur — **partagé**, et c'est tout l'intérêt (S21).

Il appartenait naturellement à l'étage 1 : casse, accents, apostrophes, ponctuation. Mais la
conviction **saute l'étage 1** (chemin inversé, Architecture §7), et le détecteur d'entrée
(S33) travaille **avant** tout le monde. Trois consommateurs, donc un utilitaire de domaine —
pas une méthode privée d'un étage.

Le pasteur tape sur une tablette un vendredi soir. Exiger l'orthographe, c'est refuser le
terrain : « nexiiste », « leglise » doivent rencontrer « n'existe », « l'Église ».

---

**Pourquoi l'apostrophe est *supprimée* et non remplacée par une espace.** C'est la décision qui
fait marcher le cas de S21, et elle mérite d'être écrite plutôt que découverte :

    « l'Église »  →  apostrophe → espace  →  {l, eglise}      ← « leglise » ne rencontre rien
    « l'Église »  →  apostrophe supprimée →  {leglise}         ← « leglise » rencontre

L'élision est justement ce que l'on tape sans apostrophe quand on va vite. La coller au mot suivant
fait converger la faute et la forme correcte.

**Le prix, assumé :** « l'homme » devient `lhomme`, et quelqu'un qui tape « homme » ne le rencontre
pas. Le détecteur ne s'en sert que pour des **proportions** de tokens connus, jamais pour une
égalité stricte — il encaisse ce bruit. Un résolveur qui aurait besoin de l'égalité devra ajouter
sa propre variante, sans toucher à celle-ci.

Fonctions **pures**, sans dépendance : ni corpus, ni horloge, ni configuration.
"""

from __future__ import annotations

import re
import unicodedata

#: Ce qui disparaît sans laisser d'espace : l'élision colle au mot suivant. Les points de code
#: sont écrits en échappement — sur un clavier, ces quatre glyphes sont indiscernables, et une
#: relecture ne verrait pas qu'il en manque un.
_ELISION = re.compile(
    "['"        # apostrophe droite — celle des claviers
    "\u2019"    # apostrophe typographique — celle des traitements de texte
    "\u02bc"    # lettre modificatrice, fréquente dans les corpus importés
    "\u02bb"    # sa jumelle tournée
    "`]"        # accent grave, tapé par erreur à la place de l'apostrophe
)

#: Tout le reste de la ponctuation devient une frontière de mot.
_NON_MOT = re.compile(r"[^0-9a-z]+")

_ESPACES = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Minuscules, sans accents, sans apostrophes, ponctuation réduite à des espaces.

    Le résultat est **stable** : deux saisies qui ne diffèrent que par la casse, les accents ou
    la ponctuation rendent exactement la même chaîne. C'est ce qui permet au déterminisme du
    moteur de tenir sur une entrée humaine."""
    sans_accent = "".join(
        caractere
        for caractere in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(caractere)
    )
    colle = _ELISION.sub("", sans_accent.lower())
    return _ESPACES.sub(" ", _NON_MOT.sub(" ", colle)).strip()


def tokens(text: str) -> tuple[str, ...]:
    """Les mots comparables de cette saisie, dans l'ordre — vide si rien n'est lisible.

    L'ordre est conservé : le détecteur d'entrée en a besoin pour reconnaître « 1 Rois », où le
    chiffre appartient au nom du livre et non au chapitre."""
    normalise = normalize(text)
    return tuple(normalise.split()) if normalise else ()
