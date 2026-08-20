"""La charte des documents — **une seule définition des couleurs et des corps**.

Les deux écrivains produisent des objets qui sortent du produit : le `.pptx` monte au mur
d'une assemblée, la note part au bureau du pasteur et souvent chez l'imprimeur. Ils doivent se
ressembler, et ressembler à Urim.

## Pourquoi un module plutôt que des constantes en haut de chaque fichier

Parce qu'elles divergeraient. Le deck a déjà sa palette implicite — celle du gabarit par défaut
de `python-pptx`, blanche et bleue Office — et la note la sienne, celle de Word. Deux documents
du même travail, deux identités qui ne sont ni l'une ni l'autre celle de Dorea.

## Les polices, et pourquoi ce ne sont pas celles de l'application

L'application affiche Nova Cut, une police de titrage. Un `.pptx` ne l'embarque pas : il
**nomme** ses polices, et l'ordinateur qui projette le dimanche matin les remplace par ce
qu'il a. Une police absente se remplace par la police par défaut, et le travail de la semaine
s'affiche en Calibri.

On choisit donc des polices que Windows et Office portent partout, et on assume : Georgia pour
l'Écriture — un texte long se lit mieux en romain, y compris projeté — et une grotesque pour
les intitulés, les références, les pieds de page.

## La signature

Discrète, jamais un logo : une image embarquée triple le poids du fichier et sort floue au
vidéoprojecteur. Un mot, en petit, dans le pied de page.
"""

from __future__ import annotations

#: La brique de la charte — `#CC3C1F`, la valeur de référence.
BRIQUE = (0xCC, 0x3C, 0x1F)

#: Le marine profond des fonds — `#003049`.
MARINE = (0x00, 0x30, 0x49)

#: Le sable des longues lectures — `#F7F4E4`. Moins fatigant que le blanc pur sur un chapitre
#: entier, et il tient à la projection là où le blanc éblouit.
SABLE = (0xF7, 0xF4, 0xE4)

#: L'encre courante — `#001926`, presque noir mais jamais noir : le noir pur sur blanc pur
#: vibre à l'écran comme à l'impression.
ENCRE = (0x00, 0x19, 0x26)

#: Le gris d'accompagnement — métadonnées, motifs, pieds de page.
GRIS = (0x63, 0x66, 0x6A)

#: L'Écriture, et tout ce qui se lit longtemps.
SERIF = "Georgia"

#: Les intitulés, les références, les pieds de page.
GROTESQUE = "Segoe UI"

#: Ce qui signe le document. Pas un logo — un mot.
SIGNATURE = "Préparé avec Dorea"


def corps_du_verset(texte: str) -> int:
    """La taille d'un texte projeté, **mesurée sur sa longueur**.

    Un verset de dix mots et un paragraphe de quatre lignes ne se projettent pas au même corps,
    et un corps fixe fait déborder la diapositive — ce qui, du fond de la salle, se voit avant
    le texte. Trois paliers suffisent ; on ne cherche pas l'ajustement au caractère près, on
    cherche qu'aucune diapositive ne déborde.
    """
    longueur = len(texte)
    if longueur > 480:
        return 20
    if longueur > 260:
        return 24
    return 30
