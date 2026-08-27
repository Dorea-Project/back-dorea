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

---

🔴 **Pourquoi œ et æ sont dépliés *à la main*, alors que NFKD déplie déjà des ligatures.**

NFKD ne défait que les ligatures dites *de compatibilité* — celles qu'un typographe a nouées et
qu'Unicode n'a admises que pour la conversion : `ﬁ → fi`, `ﬂ → fl`, `ĳ → ij`. Mais `œ` et `æ` sont
des **lettres**, pas des ligatures de compatibilité : Unicode ne leur donne aucune décomposition,
et NFKD les rend intactes. Elles tombaient donc dans `_NON_MOT`, qui ne connaît que `[0-9a-z]` et
traite tout le reste en **frontière de mot**.

    « de tout son cœur »   →   `de tout son c ur`

Le dégât n'est pas un accent perdu, qui se rattraperait au rappel. C'est que le mot est **remplacé
par deux mots qui n'existent pas** : sur la Segond, `cœur` (772 versets) disparaissait au profit
d'un `c` et d'un `ur` que rien ne distingue plus d'un vrai mot rare. Or `CorpusIdfModel` existe
pour dire *« les mots fréquents ne discriminent rien »* : deux fragments à idf moyen sont
exactement le poison de cette table — ils désignent des versets au lieu de n'en désigner aucun.
Vingt-trois mots français y passaient (`œuvre`, `sœur`, `bœuf`, `œil`, `vœu`, `mœurs`…), et `œil`
gonflait au passage le pronom `il`.

`ß` n'est pas dépliée : Unicode ne la décompose pas non plus, mais aucun corpus servi ici n'en
porte, et une règle sans cas est une règle que personne ne saura relire.

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

#: Les lettres soudées qu'Unicode refuse de décomposer — dépliées **avant** tout le reste, sinon
#: `_NON_MOT` les prend pour de la ponctuation et coupe le mot en deux.
_SOUDEES = str.maketrans({"œ": "oe", "Œ": "OE", "æ": "ae", "Æ": "AE"})

#: Tout le reste de la ponctuation devient une frontière de mot.
_NON_MOT = re.compile(r"[^0-9a-z]+")

_ESPACES = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Minuscules, sans accents, sans apostrophes, lettres soudées dépliées, ponctuation réduite
    à des espaces.

    Le résultat est **stable** : deux saisies qui ne diffèrent que par la casse, les accents ou
    la ponctuation rendent exactement la même chaîne. C'est ce qui permet au déterminisme du
    moteur de tenir sur une entrée humaine."""
    sans_accent = "".join(
        caractere
        for caractere in unicodedata.normalize("NFKD", text.translate(_SOUDEES))
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


# --- La civilité (terrain, 2026-08-22) -------------------------------------------------------

#: **Le vocabulaire fermé de la politesse** — consulté avant le corpus, aux deux portes.
#:
#: 🔴 Né d'un essai sur téléphone : *« bonjour Urim »* ouvrait une préparation, et le moteur
#: rendait 1 Corinthiens. La cause n'est pas un oubli, c'est un recouvrement de vocabulaires :
#:
#:     salut   → le salut, celui qu'on prêche
#:     merci   → la miséricorde
#:     urim    → Exode 28:30
#:
#: **En français, les mots de la politesse sont aussi les mots de la doctrine**, et le nom du
#: produit est dans l'Écriture. `MOTS_RECONNUS_MINIMUM = 1` ne pouvait donc pas les séparer :
#: saluer Urim par son nom, c'est le citer. Aucun seuil de comptage ne réparera ça — il faut
#: une liste, et elle doit être **fermée**.
#:
#: ⚠️ **Ce qui borne cette liste est plus important que ce qu'elle contient.** Une règle de
#: civilité trop gourmande crée une panne pire que celle qu'elle répare : le pasteur salue
#: poliment, et son travail est jeté. D'où les deux bornes de `est_une_civilite`.
CIVILITES: frozenset[str] = frozenset({
    # saluer
    "bonjour", "bonsoir", "bonne", "soir", "matin", "salut", "coucou", "hello", "hi",
    "re", "rebonjour",
    # remercier, prendre congé
    "merci", "mercis", "beaucoup", "bien", "tres", "au", "revoir", "bye", "ciao",
    "journee", "soiree", "nuit",
    # prendre des nouvelles — le seul endroit où on accepte une question
    "ca", "va", "comment", "allez", "vas", "tu", "vous", "et", "toi",
    # l'assentiment nu, quand il n'y a rien à quoi assentir
    "ok", "oui", "non", "d", "accord", "parfait", "super",
    # ⚠️ **Le nom de l'agent, et c'est lui qui a déclenché tout ceci.** On le cite pour
    # s'adresser à lui, pas pour citer Exode 28.
    "urim", "dorea",
})

#: Au plus quatre mots — la borne de la spec entrante, et elle est la moitié de la règle.
#:
#: *« Bonjour, je veux prêcher sur le pardon dimanche »* fait huit mots dont six hors liste :
#: elle passe, et le sujet descend. C'est le scénario A2, et il compte autant que A1.
CIVILITE_MOTS_MAXIMUM: int = 4


def est_une_civilite(mots: tuple[str, ...] | list[str]) -> bool:
    """Cette saisie est-elle **seulement** une politesse ?

    Deux bornes, et il faut les deux : au plus `CIVILITE_MOTS_MAXIMUM` mots, **et** tous dans
    le vocabulaire fermé. Un seul mot hors liste rend la main au détecteur — c'est-à-dire au
    corpus, qui reste seul juge de ce qui est une intention.

    Déterministe, sans corpus, sans modèle : elle peut donc passer **avant** eux."""
    return bool(mots) and len(mots) <= CIVILITE_MOTS_MAXIMUM and all(
        mot in CIVILITES for mot in mots
    )
