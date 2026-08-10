"""Lire une référence **telle qu'un pasteur l'écrit dans ses notes**.

    Hb 2v29     Jn14v28     Eph 1v20-22     1Jn2v1-2     Ps 110 v1

Aucune de ces cinq formes n'était lue. Le lecteur du moteur attend `Livre chapitre:verset` ;
les notes du Pasteur X n'en contiennent pas une seule de cette forme. Une garantie qui ne lit
pas la notation de celui qu'elle protège ne protège personne.

## Pourquoi ici, et pas dans le lecteur du moteur

`parse_reference_candidates` sert la **porte d'entrée**, et sa sévérité y est une fonctionnalité :
elle exige que le nom de livre forme un bloc contigu avec ses chiffres (S35), faute de quoi
« ma voiture 406 » deviendrait une référence. L'assouplir ouvrirait cette porte-là.

Ici le contexte est l'inverse : le pasteur a **déclaré** qu'il saisissait une liste de textes.
Il n'y a rien à deviner, seulement à lire — et on peut donc être bien plus permissif sans
risque, parce que l'ambiguïté ne porte plus sur *l'intention* mais sur *l'orthographe*.

## Ce qu'on ne fait pas

**On ne corrige pas.** `Hb 2v29` se lit « Hébreux 2:29 », et c'est `check_reference` qui dira
qu'il n'y a pas de verset 29 — avec son motif. Deviner que le pasteur voulait 2:9 serait
décider à sa place sur la seule foi d'une touche voisine.

**On ne tranche pas les homonymes.** `Jn` désigne Jean, 1, 2 et 3 Jean : on rend les quatre,
et le pasteur choisit. C'est S24, appliqué à sa liste.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.contexts.urim.engine.normalizer import normalize
from app.contexts.urim.engine.state import Reference
from app.contexts.urim.infrastructure.corpus.index import CorpusIndex

#: Ce qui sépare un nom de livre de ses chiffres quand rien ne les sépare — `jn14v28`. On
#: insère l'espace **aux frontières lettre/chiffre**, ce qui suffit à défaire toutes les
#: formes collées sans toucher aux formes déjà espacées.
_FRONTIERE = re.compile(r"(?<=\d)(?=[a-z])|(?<=[a-z])(?=\d)")

#: Les lettres isolées qui ne sont pas un nom de livre mais un séparateur de verset : `2v29`
#: une fois défait donne `2 v 29`. `v` pour *verset*, `c` pour *chapitre*.
_SEPARATEURS = frozenset({"v", "vs", "c", "ch"})


@dataclass(frozen=True, slots=True)
class LectureLibre:
    """Ce qu'on a compris d'une saisie — et ce qu'on n'a pas compris.

    `references` peut en contenir plusieurs (`Jn` en désigne quatre) ou aucune. `motif` dit
    alors **pourquoi**, dans les termes du corpus : *« je ne connais pas de livre nommé… »*
    plutôt que *« référence invalide »*."""

    references: tuple[Reference, ...] = ()
    motif: str = ""


def lire(brut: str, index: CorpusIndex) -> LectureLibre:
    """`Hb 2v29` → `Hébreux 2:29`. La validité, c'est `check_reference` qui la dit."""
    mots = _defaire(brut)
    if not mots:
        return LectureLibre(motif="Saisie vide.")

    livres, reste = _nom_de_livre(mots, index)
    if not livres:
        return LectureLibre(
            motif=f"Je ne connais pas de livre nommé « {brut.strip()} »."
        )

    chiffres = [int(mot) for mot in reste if mot.isdigit()]
    if not chiffres:
        # Le livre entier — un choix légitime (S23), pas une saisie incomplète.
        return LectureLibre(tuple(Reference(nom) for nom in livres))

    chapitre = chiffres[0]
    debut = chiffres[1] if len(chiffres) > 1 else None
    fin = chiffres[2] if len(chiffres) > 2 else None
    return LectureLibre(
        tuple(Reference(nom, chapitre, debut, fin) for nom in livres)
    )


def _defaire(brut: str) -> list[str]:
    """`Eph 1v20-22` → `['eph', '1', 'v', '20', '22']`.

    `normalize` replie les accents, la casse et la ponctuation ; il ne sait pas défaire
    `1v20`, parce que rien dans un texte biblique ne l'exige. C'est propre à la notation
    abrégée, et donc propre à cette lecture."""
    return [mot for mot in _FRONTIERE.sub(" ", normalize(brut)).split() if mot]


def _nom_de_livre(
    mots: list[str], index: CorpusIndex
) -> tuple[tuple[str, ...], list[str]]:
    """Le nom de livre le plus **long** qui commence la saisie, et ce qui reste après lui.

    Du plus long au plus court, comme partout : `1 jean` avant `jean`, faute de quoi `1Jn2v1`
    se lirait « Jean » avec un `1` égaré devant."""
    for forme in index.forms_by_length:
        longueur = len(forme)
        if tuple(mots[:longueur]) == forme:
            livres = index.books_by_form.get(forme, ())
            noms = tuple(
                nom for livre in livres if (nom := index.label_by_book.get(livre))
            )
            if noms:
                # Les séparateurs de verset ne sont ni un nom ni un chiffre : ils disparaissent
                # ici plutôt que de polluer la lecture des nombres.
                return noms, [
                    mot for mot in mots[longueur:] if mot not in _SEPARATEURS
                ]
    return (), mots
