"""La boucle conversationnelle — **la liaison d'abord, le modèle seulement si elle rend la main**.

C'est le trou 2 du contrat (`docs/Urim_Conversation.md` §6) : du texte libre **en cours de**
préparation. Jusqu'ici `raw_input` n'existait qu'à l'ouverture ; après, il n'y avait que
`POST /decisions` avec un code d'option — et le tour 5 de la maquette montre le pasteur qui
tape *« Quel plan je peux tenir sur ce texte ? »*.

Toutes les pièces existaient. Aucune n'était appelée.

## L'ordre, et il n'est pas négociable

    1. la liaison    exacte, deterministe, zero appel
    2. l'aiguilleur  un appel, sept codes — SEULEMENT si la liaison rend la main
    3. le repondeur  deterministe, selon le code
    4. le tour       comme partout

🔴 **Un tour qui atteint le modèle alors que la liaison pouvait répondre est un défaut, pas une
inefficacité.** Le scénario mesuré le 12/08 : trois refus successifs, **neuf appels** et une
dizaine de secondes, pour n'apprendre rien. Chaque « non, pas celui-là » repartait dans
l'aiguilleur puis dans le bloc conviction complet.

Et le coût n'était pas le pire. L'aiguilleur répond à *« que veut-il ? »* — il rend `preciser`,
ce qui est juste, et laisse le répondeur sans aucun moyen de savoir **quelle option** était
visée. Une intention mal aiguillée donne une réponse hors sujet ; une désignation manquée fait
agir sur le mauvais objet.

## Ce que la liaison consomme, et ce qu'elle laisse passer

Sur les six tours de la maquette, **quatre sont des liaisons** : « Ecclésiologie », « L'unité »,
« Expositif » désignent une option déjà offerte, et se résolvent par comparaison de chaînes. Les
deux tiers du fil ne coûtent rien et ne peuvent pas se tromper.

⚠️ **Une cible sans geste n'est une décision que si le moteur attend une décision.** La liaison
est aveugle à l'issue : elle reconnaît toujours la cible, et ne nomme le geste que sur un
marqueur explicite. C'est ici qu'on tranche, parce que c'est ici qu'on sait si une question est
posée. Hors attente, une désignation nue n'a pas de geste évident — et l'aiguilleur prend le
tour, comme la liaison le prévoit.

## Ce qui n'est jamais exécuté

Aucune intention n'agit. Elles **proposent** : `changer_de_sujet` ne ferme pas la préparation,
`demander_production` ne fabrique rien. Un aiguilleur probabiliste n'a aucun pouvoir
d'exécution — et c'est ce qui autorise à s'en servir devant des répondeurs déterministes.

Les deux seuls gestes exécutés viennent de la liaison, qui est exacte : décider, et écarter.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.contexts.urim.application.ports import NullVerseResolver
from app.contexts.urim.application.reference_libre import lire
from app.contexts.urim.engine.liaison import RETRAITS, Geste, Liaison, lier
from app.contexts.urim.engine.normalizer import est_une_civilite, tokens
from app.contexts.urim.engine.repondeurs import (
    repondre,
    repondre_acquiescement,
    repondre_civilite,
    repondre_indechiffrable,
    repondre_panne,
    repondre_reference_introuvable,
    repondre_sans_lecture,
)
from app.contexts.urim.engine.state import Reference
from app.contexts.urim.infrastructure.corpus.index import CorpusIndex
from app.contexts.urim.infrastructure.corpus.readers import IndexedCorpusReader


@dataclass(frozen=True, slots=True)
class Notation:
    """Ce que la notation du pasteur a donné — **et ce que le corpus en dit**.

    Les deux voyagent ensemble parce qu'ils viennent d'une seule lecture : relire la saisie une
    seconde fois pour la contrôler laisserait les deux résultats diverger le jour où le lecteur
    change."""

    #: Les références comprises, dans l'ordre rendu par le lecteur — les quatre candidats de
    #: `Jn` quand l'abréviation est ambiguë.
    lues: tuple[Reference, ...] = ()

    #: Le motif du corpus quand **aucune** des lectures n'existe : *« Hébreux 2 compte 18
    #: versets — il n'y a pas de verset 29. »* Vide le reste du temps, y compris quand rien
    #: n'a été lu du tout.
    introuvable: str = ""


def lire_la_notation(saisie: str, index: CorpusIndex) -> Notation:
    """La notation du pasteur → des références, ou rien.

    `Hb 2v29`, `Jn14v28`, `Eph 1v20-22`, `jn 2:3` : ses quatre saisies attestées, et pas une
    seule de la forme `Livre chapitre:verset`. Le lecteur qui les comprend existe depuis la
    chaîne de textes d'appui ; il ne parlait à personne dans le tour, si bien qu'une référence
    **affichée à l'écran** partait quand même au modèle.

    ⚠️ **Le nom de livre doit ouvrir la saisie, et c'est la garde qui rend ceci sûr.** Balayer
    la phrase entière rendrait « Marc a quitté l'église » ou « il y a des actes qui parlent »
    équivalents à une référence — Marc, Actes, Juges et Nombres sont des mots français avant
    d'être des livres. C'est la sévérité de S35, et l'assouplir ici rouvrirait exactement la
    porte que le détecteur d'entrée tient fermée.

    Un seul préfixe est retiré : les **marqueurs de retrait**, parce qu'ils forment un
    vocabulaire fermé que la liaison possède déjà. « non, pas Hb 2v29 » écarte donc, là où
    « prends Hb 2v29 » n'est pas lu et repart au modèle. Un tour de plus contre une
    désignation inventée : c'est l'asymétrie de tout cet étage.

    ## Le contrôle de référence, et les deux gardes qui l'encadrent

    Urim sait depuis le premier jour dire *« Hébreux 2 compte 18 versets »*. Il ne le disait
    qu'aux textes d'appui — au tour, `Hb 2v29` repartait à l'aiguilleur, qui répondait à côté
    **sans rien dire de l'erreur de référence**. C'est ce que ce contrôle ferme.

    ⚠️ **Le motif du lecteur n'est jamais rendu.** *« Je ne connais pas de livre nommé
    « bonjour » »* est juste, et absurde : toute phrase ordinaire le déclencherait. Seul le
    verdict du **corpus** sur un livre déjà reconnu sort d'ici.

    ⚠️ **Et seulement quand la saisie EST la référence.** « Nombres 500 personnes sont venues »
    est une phrase où un nom de livre passe par hasard ; lui répondre que le chapitre 500
    n'existe pas serait répondre à une question qu'il n'a pas posée. Le surplus de mots
    l'interdit — alors qu'il n'interdit pas de *désigner* (« Romains 12 s'il te plaît » vise
    bien une option). Désigner est réversible ; contredire ne l'est pas.
    """
    mots = list(tokens(saisie))
    while mots and mots[0] in RETRAITS:
        mots.pop(0)
    if not mots:
        return Notation()

    # `lire` normalise ce qu'on lui donne, et `normalize` est idempotent : lui rendre des
    # jetons déjà normalisés ne lui retire rien — il refait seulement sa coupe `1v20`.
    lu = lire(" ".join(mots), index)
    if not lu.references:
        return Notation()

    lecteur = IndexedCorpusReader(index)
    verdicts = [lecteur.check_reference(reference) for reference in lu.references]
    if lu.surplus or any(verdict.exists for verdict in verdicts):
        return Notation(lu.references)

    # Le premier motif énoncé — même choix que la chaîne de textes d'appui. Sur `Jn 99:1` les
    # quatre candidats échouent de la même façon ; en aligner quatre phrases n'apprendrait rien
    # de plus au pasteur.
    return Notation(
        lu.references,
        next((v.rationale for v in verdicts if v.rationale), ""),
    )


@dataclass(frozen=True, slots=True)
class Ecran:
    """Ce que le pasteur a sous les yeux — **dans l'ordre où il le voit**.

    Les trois listes sont parallèles : un rang y désigne la même option partout. C'est ce qui
    permet de rendre un *code* d'option à partir d'un « le deuxième », et l'ordre est celui du
    tour, pas celui du moteur (voir `rang_a_l_ecran`).

    Une option qui n'est pas une référence porte `Reference("")` : la liaison compare des
    jetons, et un livre vide n'apparaît dans aucune saisie. La place reste tenue, donc les
    rangs restent justes."""

    codes: tuple[str, ...] = ()
    references: tuple[Reference, ...] = ()
    libelles: tuple[str, ...] = ()
    #: Le passage en cours, tel qu'on l'affiche — *« Nous en sommes à Romains 12:9-16 »*. C'est
    #: le seul service qu'un tour qui n'avance pas puisse rendre.
    ancre: str | None = None
    #: Le moteur attend-il une décision ? Sans cette attente, une désignation nue n'a pas de
    #: geste, et il n'y a d'ailleurs rien à décider.
    attend: bool = False


@dataclass(frozen=True, slots=True)
class Tour:
    """Ce que le tour a conclu — **un geste à exécuter, ou une phrase à dire**, jamais les deux.

    `appels` n'est pas de la télémétrie : c'est la mesure du défaut. Un tour que la liaison
    pouvait résoudre et qui compte un appel est le bogue même que ce module vient corriger, et
    le banc s'en sert comme critère."""

    decision: str | None = None
    refus: str | None = None
    reponse: str | None = None
    appels: int = 0

    #: L'intention que l'aiguilleur a lue, quand il a été consulté.
    #:
    #: ⚠️ **Elle n'agit toujours pas.** Ce module n'exécute que ce que la liaison a reconnu —
    #: c'est ce qui autorise un aiguilleur probabiliste devant des répondeurs déterministes.
    #: Elle voyage parce qu'un appelant en sait plus que nous : le service, lui, connaît l'état
    #: de la préparation, et `changer_de_sujet` n'a pas le même sens sur un travail commencé
    #: que sur une page blanche.
    intention: str | None = None


def _cible(lu: Liaison, ecran: Ecran) -> str | None:
    """Le **code d'option** que cette liaison désigne, s'il y en a un.

    L'ordre des trois lectures suit leur exactitude. Le rang et la référence passent par le
    même champ — la liaison a déjà tranché entre eux, et elle donne la référence gagnante parce
    qu'elle est exacte là où un rang peut se confondre avec un numéro de chapitre.

    Les bornes arrivent en dernier et ne valent que si une option affichée les porte
    **exactement**. Il n'existe aucune route pour poser des bornes neuves : en fabriquer une
    ici serait inventer un geste, et « versets 9 à 13 » qui ne correspond à rien à l'écran est
    une demande que l'aiguilleur doit lire."""
    if lu.option is not None and lu.option < len(ecran.codes):
        return ecran.codes[lu.option]
    if lu.axe:
        return lu.axe
    if lu.bornes:
        debut, fin = lu.bornes
        return next(
            (
                code
                for code, ref in zip(ecran.codes, ecran.references, strict=True)
                if ref.verse_start == debut and (ref.verse_end or ref.verse_start) == fin
            ),
            None,
        )
    return None


#: Le tour d'un appelant qui n'a pas de corpus sous la main — les tests, et le banc quand la
#: base est absente. Immuable, donc partageable sans risque.
_RIEN_LU = Notation()


async def conduire(
    saisie: str, ecran: Ecran, assiste, notation: Notation = _RIEN_LU
) -> Tour:
    """Un tour de texte libre → un geste, ou une phrase.

    `notation` porte ce que `lire_la_notation` a compris — les références du pasteur écrites
    dans sa notation, et le verdict du corpus sur elles. Le paramètre plutôt que l'index : la
    boucle reste éprouvable sans corpus, et l'appelant est déjà celui qui connaît la saisie.

    ⚠️ **La liaison passe toujours en premier, et son résultat est sans appel.** Elle ne devine
    jamais : sans appariement exact elle rend une liaison vide, et c'est seulement à ce
    moment-là que le modèle coûte quelque chose.

    ⚠️ **Une panne n'est pas une réponse.** `MistralAssistant.echecs` est monotone : un 429 rend
    `None` exactement comme un modèle qui ne sait pas classer. Les confondre ferait servir
    *« je n'ai rien reçu qui concerne la préparation »* à un pasteur dont la seule faute est
    d'avoir écrit pendant une coupure — le seul cas où Urim reprocherait quelque chose à
    quelqu'un qui n'a rien fait. On prend donc une photo du compteur avant, une après."""
    if not tokens(saisie):
        # Ni mot ni chiffre — « ... », de la ponctuation, une barre d'espace restée enfoncée.
        # C'est le fragment d'`indechiffrable`, et il se reconnaît **sans modèle** : il n'y a
        # littéralement rien à classer. Payer un appel pour l'apprendre serait le payer pour
        # rien.
        return Tour(reponse=repondre_indechiffrable(saisie, ecran.ancre))

    if notation.introuvable:
        # ⚠️ **Avant la liaison, et c'est le seul ordre défendable.** Une référence que le
        # corpus rejette pourrait quand même désigner une option — `Hb 2v29` tombe dans une
        # option « Hébreux 2 » affichée en chapitre entier. Décider silencieusement lui
        # cacherait la seule chose utile de ce tour : *il n'y a pas de verset 29*. Et ce que
        # le corpus sait, il le sait sans le modèle.
        return Tour(reponse=repondre_reference_introuvable(notation.introuvable, ecran.ancre))

    lu = lier(
        saisie,
        ecran.references,
        tuple(zip(ecran.codes, ecran.libelles, strict=True)),
        notation.lues,
    )
    cible = _cible(lu, ecran)

    if lu.geste is Geste.ACQUIESCER:
        # Il ne désigne rien, et la liaison ne devine pas. Hors attente, un « ok » ne demande
        # rien non plus : le tour se repose tel quel, sans phrase et sans appel.
        return Tour(
            reponse=repondre_acquiescement(saisie, ecran.ancre) if ecran.attend else None
        )

    if cible is not None:
        if lu.geste is Geste.ECARTER:
            return Tour(refus=cible)
        if ecran.attend:
            return Tour(decision=cible)

    # ⚠️ **Après la liaison, jamais avant.** « oui », « non », « d'accord » appartiennent aussi
    # au vocabulaire de la politesse, et ce sont des **gestes** quand une option est à l'écran.
    # Intercepter plus haut ferait répondre « bonjour » à un pasteur qui vient d'écarter un
    # texte. Ici, la liaison a déjà dit qu'elle ne reconnaissait rien : il ne reste qu'un
    # salut, et il se reconnaît sans modèle.
    if est_une_civilite(tokens(saisie)):
        return Tour(reponse=repondre_civilite(saisie, ecran.ancre))

    if isinstance(assiste, NullVerseResolver):
        # Pas de clé, ou quota d'assistance épuisé — **un état de production, pas une panne**
        # (S12, S37). Tout le reste d'Urim continue ; seule la lecture d'une phrase libre
        # manque, et la liaison vient de dire qu'elle ne suffisait pas.
        return Tour(reponse=repondre_sans_lecture(saisie, ecran.ancre))

    echecs = getattr(assiste, "echecs", 0)
    intention = await assiste.aiguiller(saisie)
    if getattr(assiste, "echecs", 0) != echecs:
        return Tour(reponse=repondre_panne(saisie, ecran.ancre), appels=1)
    return Tour(
        reponse=repondre(intention, saisie, ecran.ancre),
        appels=1,
        intention=intention,
    )
