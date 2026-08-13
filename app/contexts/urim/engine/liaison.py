"""La liaison — **de quoi le pasteur parle**, avant qu'on demande ce qu'il en veut.

Urim affiche un tour : quatre à six passages proposés, l'unité en cours et ses bornes, les dix
loci avec leur titre, les options déjà écartées. **Tout cela est à l'écran, et le moteur le
sait.** Quand le pasteur répond *« non, pas le deuxième »*, il ne formule pas une intention
nouvelle : il désigne quelque chose qui est déjà là.

Une comparaison de chaînes contre l'état courant suffit, et elle est **exacte**.

## Ce que coûtait son absence

Le scénario mesuré le 12/08 : trois refus successifs, **neuf appels de modèle**, une dizaine de
secondes, rien appris. Chaque « non, pas celui-là » repartait dans l'aiguilleur puis dans le
bloc conviction complet.

Et le coût n'était pas le pire. L'aiguilleur répond à *« que veut-il ? »* — il rend `preciser`,
ce qui est juste, et laisse le répondeur sans aucun moyen déterministe de savoir **quelle
option** était visée. Il devine, ou il redemande.

    Une intention mal aiguillée donne une réponse hors sujet.
    Une désignation manquée fait agir sur le mauvais objet.

La seconde est bien plus grave, et c'est pourquoi cet étage est déterministe.

## Le patron existe déjà, à la porte

Le détecteur d'entrée fait le même geste à l'ouverture : avant de demander au modèle ce que la
saisie veut dire, il regarde si c'est littéralement une référence — c'est lui qui lit `Hb 2v29`
et `Jn14v28`. **La liaison est au tour ce que le détecteur d'entrée est à l'ouverture.**

## Ce qu'elle ne fait pas, et c'est la règle qui la rend sûre

**Elle ne devine jamais.** Sans appariement exact, elle rend `None` et l'aiguilleur prend le
tour. *« Celui-là »* sans rang est ambigu : deux options peuvent convenir, et se tromper
d'objet coûte plus cher que de payer un appel.

**Elle ne lie qu'à ce qui est à l'écran.** Une référence absente des propositions n'est pas de
son ressort : c'est une saisie neuve, et le détecteur d'entrée la traitera à l'étage suivant.

**Elle ne conclut pas toujours au geste.** Elle reconnaît toujours la *cible* ; elle ne nomme
le *geste* que lorsqu'un marqueur explicite le porte — une négation, un verbe de retrait, un
acquiescement. Sinon le geste reste ouvert et l'aiguilleur tranche : les deux étages se
complètent, ils ne se remplacent pas.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from app.contexts.urim.engine.normalizer import normalize, tokens
from app.contexts.urim.engine.state import Reference


#: ⚠️ **Fermé**, comme les intentions et les loci. Un geste deviné serait un geste subi.
class Geste(StrEnum):
    ECARTER = "ecarter"
    ACQUIESCER = "acquiescer"
    BORNER = "borner"


@dataclass(frozen=True)
class Liaison:
    """Ce que la saisie désigne dans l'état affiché.

    Tous les champs sont facultatifs : une liaison peut porter une cible sans geste (*« le
    deuxième »*), un geste sans cible (*« oui »*), ou les deux (*« enlève le premier »*)."""

    option: int | None = None          # rang dans les passages proposés, à partir de 0
    axe: str | None = None             # code de locus
    bornes: tuple[int, int] | None = None
    geste: Geste | None = None

    def __bool__(self) -> bool:
        return any((self.option is not None, self.axe, self.bornes, self.geste))


#: L'acquiescement doit occuper **toute** la saisie : « oui mais pas celui-là » n'en est pas un.
_ACQUIESCEMENTS = frozenset({
    "oui", "ok", "okay", "daccord", "dacc", "bien", "tres bien", "parfait", "cest bon",
    "ca va", "ca me va", "oui merci", "amen", "exactement", "voila", "cest ca",
})

#: Les marqueurs de retrait. Ils portent le geste, jamais la cible.
_RETRAITS = frozenset({
    "non", "pas", "enleve", "enlever", "retire", "retirer", "ecarte", "ecarter",
    "supprime", "supprimer", "vire", "virer", "sans", "aucun", "ni",
})

#: Les rangs, écrits. Le chiffre est traité à part — « le 2 » et « le deuxième » se valent.
_RANGS = {
    "premier": 0, "premiere": 0, "un": 0, "1er": 0,
    "deuxieme": 1, "second": 1, "seconde": 1, "deux": 1, "2e": 1, "2eme": 1,
    "troisieme": 2, "trois": 2, "3e": 2, "3eme": 2,
    "quatrieme": 3, "quatre": 3, "4e": 3, "4eme": 3,
    "cinquieme": 4, "cinq": 4, "5e": 4, "5eme": 4,
    "sixieme": 5, "six": 5, "6e": 5, "6eme": 5,
}

#: ⚠️ Le dernier se compte à l'envers, donc il dépend du nombre d'options affichées — il ne peut
#: pas vivre dans la table ci-dessus.
_DERNIERS = frozenset({"dernier", "derniere"})

#: `v. 9 à 13`, `versets 9-13`, `du 9 au 13`, `9 a 13`. La notation du pasteur, pas la nôtre.
#:
#: ⚠️ Deux formes, et il en faut deux : la normalisation efface le trait d'union, si bien que
#: « versets 9-13 » arrive ici en « versets 9 13 ». Deux nombres accolés ne sont des bornes que
#: si un mot le dit — sinon « Romains 12 9 » en serait.
_BORNES = re.compile(
    r"(?:versets?|vv?)\s*(\d{1,3})\s*(?:a|au|jusqu\w*)?\s*(\d{1,3})"
    r"|(\d{1,3})\s*(?:a|au|jusqu\w*)\s*(\d{1,3})"
)


def _suite_dans(aiguille: tuple[str, ...], meule: tuple[str, ...]) -> bool:
    """`aiguille` apparaît-elle telle quelle, d'un seul tenant, dans `meule` ?

    D'un seul tenant, et c'est ce qui compte : « romains 12 » ne doit pas se reconnaître dans
    « romains 8 et hébreux 12 »."""
    if not aiguille or len(aiguille) > len(meule):
        return False
    return any(
        meule[i:i + len(aiguille)] == aiguille
        for i in range(len(meule) - len(aiguille) + 1)
    )


def _rang(mots: tuple[str, ...], combien: int) -> int | None:
    """Le rang désigné, s'il en est un **et s'il existe à l'écran**.

    🔴 Deux gardes que le banc a imposées, et la seconde était un vrai danger.

    Le rang écrit se vérifie contre le nombre d'options : « le sixième » quand quatre sont
    affichées ne désigne rien, il ne désigne pas la quatrième.

    Et un chiffre nu ne vaut comme rang **que s'il est le seul nombre de la saisie**. Sans
    cette règle, « Aggée 1:5 » — une référence que l'écran ne propose pas — se liait à la
    première option par son `1`. Une saisie neuve devenait une désignation, et le tour agissait
    sur un texte que le pasteur n'avait pas nommé."""
    chiffres = [m for m in mots if m.isdigit()]
    for mot in mots:
        if mot in _DERNIERS and combien:
            return combien - 1
        if mot in _RANGS:
            return _RANGS[mot] if _RANGS[mot] < combien else None
        if mot.isdigit() and len(chiffres) == 1 and 1 <= int(mot) <= combien:
            return int(mot) - 1
    return None


def lier(
    saisie: str,
    options: tuple[Reference, ...],
    axes: tuple[tuple[str, str], ...],
) -> Liaison:
    """Ce que cette saisie désigne parmi ce qui est affiché.

    `options` porte la référence de chaque passage proposé, **dans l'ordre de l'écran**.
    `axes` porte les couples `(code, titre)` des loci proposés.

    ⚠️ Les options arrivent **structurées**, et non en chaînes. Reconnaître « Romains 12 »
    dans la chaîne « Romains 12:9-16 » demandait d'en découper le livre et le chapitre — or
    « 1 Jean 4:7-12 » commence par un chiffre qui appartient au nom du livre. Un découpage de
    chaîne se serait trompé sur toute une famille de livres.

    Rendre une `Liaison` vide (fausse au sens booléen) signifie : *rien de ce qui est à l'écran
    n'a été désigné*. Ce n'est pas un échec, c'est le cas ordinaire d'une phrase neuve — et
    c'est le signal que l'aiguilleur doit prendre le tour.
    """
    mots = tokens(saisie)
    if not mots:
        return Liaison()

    if normalize(saisie) in _ACQUIESCEMENTS:
        return Liaison(geste=Geste.ACQUIESCER)

    geste = Geste.ECARTER if any(m in _RETRAITS for m in mots) else None

    # La référence d'abord : elle est exacte, là où un rang peut se confondre avec un numéro
    # de chapitre. Le livre et son chapitre suffisent à désigner — le pasteur écrit « Romains
    # 12 », pas « Romains 12:9-16 ».
    option = next(
        (
            i for i, reference in enumerate(options)
            if _suite_dans(tokens(f"{reference.book} {reference.chapter or ''}"), mots)
        ),
        None,
    )

    bornes = None
    if option is None:
        trouve = _BORNES.search(normalize(saisie))
        if trouve:
            paire = trouve.group(1, 2) if trouve.group(1) else trouve.group(3, 4)
            debut, fin = int(paire[0]), int(paire[1])
            if debut <= fin:
                bornes = (debut, fin)
                geste = geste or Geste.BORNER
        else:
            option = _rang(mots, len(options))

    axe = next(
        (
            code for code, titre in axes
            if titre and _suite_dans(tokens(titre), mots)
        ),
        None,
    )

    return Liaison(option=option, axe=axe, bornes=bornes, geste=geste)
