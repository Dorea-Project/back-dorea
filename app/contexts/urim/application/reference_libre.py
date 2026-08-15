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

    #: Les mots qui n'étaient ni le nom du livre, ni un nombre, ni un séparateur de verset.
    #:
    #: ⚠️ **Vide signifie : la saisie EST la référence, et rien d'autre.** Le tour s'en sert
    #: pour décider s'il a le droit de contredire le pasteur. « Hb 2v29 » appelle *« Hébreux 2
    #: compte 18 versets »* ; « Nombres 500 personnes sont venues » appelle le silence — c'est
    #: une phrase où un nom de livre passe par hasard, et lui répondre que le chapitre 500
    #: n'existe pas serait répondre à une question qu'il n'a pas posée."""
    surplus: tuple[str, ...] = ()


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
    # Ce qui reste après le livre, les nombres et les séparateurs : des mots que cette lecture
    # n'a pas employés. Elle ne s'en plaint pas — elle les **rapporte**, et l'appelant décide
    # de ce qu'ils changent pour lui.
    surplus = tuple(mot for mot in reste if not mot.isdigit())

    if not chiffres:
        # Le livre entier — un choix légitime (S23), pas une saisie incomplète.
        return LectureLibre(tuple(Reference(nom) for nom in livres), surplus=surplus)

    chapitre = chiffres[0]
    debut = chiffres[1] if len(chiffres) > 1 else None
    fin = chiffres[2] if len(chiffres) > 2 else None
    return LectureLibre(
        tuple(Reference(nom, chapitre, debut, fin) for nom in livres), surplus=surplus
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


def references_dans(texte: str, index: CorpusIndex) -> list:
    """Les références écrites **dans une ligne de plan**, pas dans un champ dédié.

    Les notes réelles ne séparent pas les appuis du propos : « - il est couronné de gloire et
    d'honneur Hb 2v29 ». On balaie donc la ligne par empans — un nom de livre suivi de ses
    chiffres — avec la même lecture permissive que la chaîne de textes (`Hb 2v29`, `Jn14v28`).

    ⚠️ **On ne retient que le premier candidat de chaque empan.** `Jn` désigne quatre livres ;
    trancher ici serait décider à sa place, mais afficher les quatre noierait son point. Le
    corpus tranche par l'ordre du canon, et le contrôle de référence dira si c'est faux."""
    trouvees = []
    mots = texte.split()
    for debut in range(len(mots)):
        for taille in (4, 3, 2, 1):
            fenetre = mots[debut:debut + taille]
            if not fenetre or not _contigu(fenetre):
                continue
            # Un seul mot ne vaut que s'il **colle** lettres et chiffres — `Jn14v28`, la
            # notation réelle des notes. Sans cette exception on perd la forme la plus
            # fréquente ; sans la condition, « Jean » seul rouvrirait le piège S35.
            if len(fenetre) == 1 and not (
                any(c.isdigit() for c in fenetre[0])
                and any(c.isalpha() for c in fenetre[0])
            ):
                continue
            lu = lire(" ".join(fenetre), index)
            if lu.references and lu.references[0].chapter is not None:
                trouvees.append(lu.references[0])
                break
    # Deux empans voisins peuvent rendre la même référence ; on garde l'ordre du pasteur.
    vues, uniques = set(), []
    for reference in trouvees:
        cle = (reference.book, reference.chapter, reference.verse_start)
        if cle not in vues:
            vues.add(cle)
            uniques.append(reference)
    return uniques


def _contigu(fenetre: list[str]) -> bool:
    """🐛 **S35, et je suis tombé dedans en écrivant ce balayage.**

    Sur *« il a reçu le nom au dessus de tout nom Ph 28v9 »*, la lecture permissive a rendu
    **« Nombres 28:9 »** : `nom` est un nom de livre autant qu'un mot français, et rien
    n'exigeait qu'il soit suivi de chiffres. Job, Juges, Actes, Rois tendent le même piège.

    La règle qui referme : **tout ce qui suit le nom de livre doit être un chiffre ou un
    séparateur de verset.** « nom au dessus » tombe ; « Ph 28v9 » passe."""
    return all(
        any(caractere.isdigit() for caractere in mot)
        or mot.strip(".,;:").lower() in {"v", "vs", "c", "ch"}
        for mot in fenetre[1:]
    )


def lisible_reference(reference) -> str:
    if reference.verse_start is None:
        return f"{reference.book} {reference.chapter}"
    if reference.verse_end and reference.verse_end != reference.verse_start:
        return f"{reference.book} {reference.chapter}:{reference.verse_start}-{reference.verse_end}"
    return f"{reference.book} {reference.chapter}:{reference.verse_start}"
