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

#: ⚠️ **L'ordre dans lequel le tour affiche les unités pesées** — et donc l'ordre dans lequel
#: un rang se compte.
#:
#: 🔴 Le rang est la seule chose que la liaison lit sans pouvoir la vérifier. Une référence est
#: exacte, un titre est exact ; « le deuxième » ne veut dire quelque chose que par rapport à ce
#: que le pasteur **voit**. Or le tour ne rend pas les options dans l'ordre du moteur : il les
#: groupe par ce qu'elles font du sujet, *en fait son sujet* avant *le soutient* avant *lui
#: résiste*. Une liste rangée autrement ferait désigner à « le deuxième » la troisième option —
#: c'est-à-dire agir sur le mauvais objet, ce que cet étage existe précisément pour éviter.
#:
#: La constante vit ici et non dans la présentation : c'est le **compteur de rangs** qui en
#: dépend, l'affichage n'en est que l'autre lecteur.
ORDRE_DES_FORCES = ("dominant", "porte", "resiste")


def rang_a_l_ecran(force: str | None) -> int:
    """Où cette option tombe dans l'ordre du tour, d'après ce que le texte fait de l'axe.

    Les options sans force viennent **après** les unités pesées : le tour en fait des
    pastilles, sous le bloc des unités — *« allez droit à un texte » n'a rien de relu, et le
    mêler aux unités le laisserait croire*."""
    return (
        ORDRE_DES_FORCES.index(force) if force in ORDRE_DES_FORCES else len(ORDRE_DES_FORCES)
    )


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
#:
#: ⚠️ **Public**, parce que le lecteur de notation en a besoin lui aussi. Il exige que le nom de
#: livre **ouvre** la saisie — sans quoi « Marc a quitté l'église » deviendrait une référence —
#: et « non, pas Hb 2v29 » ne s'ouvre pas par un livre. Retirer ce préfixe-là est sûr parce que
#: c'est un vocabulaire **fermé** : on ne saute pas de la prose, on saute des mots qui n'ont
#: qu'un sens ici. Le recopier ailleurs aurait laissé les deux listes diverger.
RETRAITS = frozenset({
    "non", "pas", "enleve", "enlever", "retire", "retirer", "ecarte", "ecarter",
    "supprime", "supprimer", "vire", "virer", "sans", "aucun", "ni",
})

#: Les rangs, écrits. Le chiffre est traité à part — « le 2 » et « le deuxième » se valent.
#:
#: 🔴 **Les cardinaux écrits n'y sont plus, et c'est le banc du tour qui l'a exigé.**
#:
#: « un », « deux », « trois » y figuraient. Quatre saisies sur vingt et une désignaient alors
#: une option **sans que personne ne l'ait voulu** :
#:
#:     « je veux faire un culte sur l'adultère dans »   → « un » → la 1re option, decidee
#:     « Propose-moi un theme. »                        → « un » → la 1re option, decidee
#:     « y a un risque de proof texting ? »             → « un » → la 1re option, decidee
#:     « attends deux minutes je arrive euh »           → « deux » → la 2e option, decidee
#:
#: « un » est un article avant d'être un rang, et aucun pasteur n'écrit « prends deux » pour
#: désigner la deuxième option — il écrit « le deuxième » ou « le 2 », qui restent tous deux
#: lus. L'ordinal n'est jamais ambigu ; le cardinal l'est presque toujours.
#:
#: L'asymétrie tranche : un rang manqué coûte un appel de modèle, un rang inventé fait agir
#: sur le mauvais objet.
_RANGS = {
    "premier": 0, "premiere": 0, "1er": 0,
    "deuxieme": 1, "second": 1, "seconde": 1, "2e": 1, "2eme": 1,
    "troisieme": 2, "3e": 2, "3eme": 2,
    "quatrieme": 3, "4e": 3, "4eme": 3,
    "cinquieme": 4, "5e": 4, "5eme": 4,
    "sixieme": 5, "6e": 5, "6eme": 5,
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


def _empan_de(aiguille: tuple[str, ...], meule: tuple[str, ...]) -> range | None:
    """**Où** `aiguille` apparaît d'un seul tenant dans `meule` — ou rien.

    D'un seul tenant, et c'est ce qui compte : « romains 12 » ne doit pas se reconnaître dans
    « romains 8 et hébreux 12 ».

    🔴 **Elle rend la position, et non plus un simple oui.** Le banc du tour a montré pourquoi :
    « La charité sans hypocrisie » — l'intitulé d'unité de la maquette — contient « sans », qui
    est un marqueur de retrait. Désigner l'unité **l'écartait**. C'est exactement le défaut que
    cet étage existe pour empêcher : agir sur le bon objet, avec le mauvais geste.

    Connaître l'empan permet de chercher le geste **hors de ce qui a été désigné** : les mots
    d'un intitulé appartiennent à l'intitulé, pas à la phrase du pasteur."""
    if not aiguille or len(aiguille) > len(meule):
        return None
    return next(
        (
            range(i, i + len(aiguille))
            for i in range(len(meule) - len(aiguille) + 1)
            if meule[i:i + len(aiguille)] == aiguille
        ),
        None,
    )


def _designe(lue: Reference, affichee: Reference) -> bool:
    """La référence **lue dans la notation du pasteur** vise-t-elle celle qui est à l'écran ?

    C'est une comparaison de structures, non de chaînes : `Hb 2v29` est arrivé ici sous la
    forme `Hébreux 2:29`, avec le libellé canonique du corpus. La notation a été absorbée par
    le lecteur ; il ne reste que deux passages à confronter.

    ⚠️ **Un nom de livre nu ne désigne rien.** `lire` rend volontiers un livre entier — c'est
    S23, et c'est juste à la porte d'entrée où le pasteur a *déclaré* saisir une référence.
    Ici, rien n'est déclaré : « Marc a quitté l'église » se lirait comme l'Évangile de Marc et
    choisirait un texte que personne n'a nommé. Le chapitre est donc exigé, exactement comme
    dans l'appariement par jetons — *le pasteur écrit « Romains 12 », pas « Romains »*.

    Les versets se **recoupent**, ils ne s'égalent pas : le pasteur qui écrit `Ga 5v13` désigne
    l'unité qui contient ce verset, pas une unité dont les bornes seraient 13-13."""
    if lue.chapter is None or normalize(lue.book) != normalize(affichee.book):
        return False
    if affichee.chapter is None:
        return True  # l'option est un livre entier : le chapitre lu tombe dedans
    if lue.chapter != affichee.chapter:
        return False
    if lue.verse_start is None or affichee.verse_start is None:
        return True  # un chapitre entier désigne ce qui en vient, des deux côtés
    return (
        lue.verse_start <= (affichee.verse_end or affichee.verse_start)
        and (lue.verse_end or lue.verse_start) >= affichee.verse_start
    )


def _par_reference_lue(
    lues: tuple[Reference, ...], options: tuple[Reference, ...]
) -> int | None:
    """Le rang de l'option que la notation désigne — **une seule, ou aucune**.

    ⚠️ L'homonymie se résout par l'écran, et c'est le bénéfice inattendu de cet appariement.
    `Jn` désigne quatre livres, et `lire` les rend tous les quatre parce qu'il refuse de
    trancher (S24). Confrontés aux options affichées, trois d'entre eux ne visent rien : il
    reste Jean, sans que personne n'ait deviné.

    Quand plusieurs options restent visées, la liaison rend la main. C'est la règle de tout
    l'étage — *deux options peuvent convenir, et se tromper d'objet coûte plus cher qu'un
    appel de modèle*."""
    vises = {
        rang
        for rang, affichee in enumerate(options)
        for lue in lues
        if _designe(lue, affichee)
    }
    return vises.pop() if len(vises) == 1 else None


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
    lues: tuple[Reference, ...] = (),
) -> Liaison:
    """Ce que cette saisie désigne parmi ce qui est affiché.

    `options` porte la référence de chaque passage proposé, **dans l'ordre de l'écran**.
    `axes` porte les couples `(code, titre)` des loci proposés.

    `lues` porte ce que **le lecteur de notation** a compris de la saisie — `Hb 2v29` devenu
    `Hébreux 2:29`, et les quatre candidats de `Jn` quand l'abréviation est ambiguë. Vide par
    défaut : la liaison reste utilisable, et testable, sans corpus.

    ⚠️ **La notation ne peut pas être lue ici, et c'est délibéré.** Reconnaître `Hb` comme
    Hébreux demande les 356 formes du corpus ; cet étage est pur et n'a pas d'index. Le
    lecteur qui les connaît existe depuis la chaîne de textes d'appui (`reference_libre`), et
    il rend des `Reference` — donc la seule chose qui manquait était de les lui demander. La
    notation est absorbée avant d'arriver ; ici on ne compare que des passages.

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

    #: Les jetons **consommés par une désignation**. Ils appartiennent à ce qui est à l'écran,
    #: pas à la phrase du pasteur, et ne portent donc aucun geste — voir `_empan_de`.
    pris: set[int] = set()

    # La référence d'abord : elle est exacte, là où un rang peut se confondre avec un numéro
    # de chapitre. Le livre et son chapitre suffisent à désigner — le pasteur écrit « Romains
    # 12 », pas « Romains 12:9-16 ».
    #
    # ⚠️ **La notation passe avant les jetons**, parce qu'elle en sait plus : elle porte les
    # versets, donc elle sait choisir entre trois unités du même chapitre là où « Ga 5 » les
    # désignerait toutes les trois — et l'appariement par jetons prendrait alors la première.
    option: int | None = _par_reference_lue(lues, options)
    if option is None:
        for rang, reference in enumerate(options):
            empan = _empan_de(tokens(f"{reference.book} {reference.chapter or ''}"), mots)
            if empan is not None:
                option = rang
                pris.update(empan)
                break

    bornes = None
    if option is None:
        trouve = _BORNES.search(normalize(saisie))
        if trouve:
            paire = trouve.group(1, 2) if trouve.group(1) else trouve.group(3, 4)
            debut, fin = int(paire[0]), int(paire[1])
            if debut <= fin:
                bornes = (debut, fin)
        else:
            option = _rang(mots, len(options))

    axe = None
    for code, titre in axes:
        empan = _empan_de(tokens(titre), mots) if titre else None
        if empan is not None:
            axe = code
            pris.update(empan)
            break

    # ⚠️ **Le geste se cherche hors de ce qui a été désigné.** « La charité sans hypocrisie »
    # porte un « sans » qui appartient à l'intitulé : le compter ferait écarter l'unité que le
    # pasteur vient de choisir. « pas la charité sans hypocrisie », lui, garde son « pas » —
    # il est hors de l'empan, donc il est bien du pasteur.
    geste = (
        Geste.ECARTER
        if any(mot in RETRAITS for i, mot in enumerate(mots) if i not in pris)
        else None
    )
    if bornes is not None:
        geste = geste or Geste.BORNER

    return Liaison(option=option, axe=axe, bornes=bornes, geste=geste)
