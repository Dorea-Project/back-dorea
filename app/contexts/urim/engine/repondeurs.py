"""Les répondeurs — **une phrase par intention, écrite une fois et relue**.

Sept intentions sortent de l'aiguilleur. Deux ne préparent rien (`hors_champ`,
`indechiffrable`) et sont difficiles pour cette raison même : le produit n'a rien à donner, et
tout se joue dans la façon de le dire. Les cinq autres **retombent sur des étages qui
existent** — la phrase ne fabrique rien, elle dit où regarder.

## La règle, et elle vient de la porte

**On nomme ce qu'Urim est, jamais ce que l'autre a mal fait.**

C'est la règle qui a été posée pour le banc de la porte, et elle vaut à chaque tour. *« Votre
demande est hors sujet »* juge la demande. *« Je ne sais préparer qu'une prédication à partir de
l'Écriture »* dit ce qu'on est, et laisse la personne intacte.

La distinction entre les deux codes du renvoi n'est pas *« ai-je compris ? »* mais *« me
parle-t-il ? »* :

    hors_champ      il te parle, on comprend, et l'atelier ne sait pas repondre
    indechiffrable  le message ne t'est pas adresse, ou ne porte aucune demande

## Pourquoi ces réponses sont déterministes

Le modèle n'a **aucun canal de sortie en prose** — `axes` rend des codes, `passages` rend des
références vérifiées. Faire écrire ces réponses par le modèle ouvrirait ce canal par la bande.

Et c'est cette propriété-là qui rend l'aiguillage probabiliste acceptable : **une intention mal
aiguillée donne une réponse hors sujet, jamais une réponse fausse.** Le jour où un répondeur
laisserait le modèle écrire, ce raisonnement tomberait entier.

## L'ancre, qui est la seule chose utile d'un tour qui n'avance pas

Un pasteur dont la phrase n'a pas abouti — un micro resté ouvert, une phrase interrompue — a
surtout besoin de savoir **où en est sa préparation**. Chaque réponse la rappelle.

⚠️ Une des trois formes d'`indechiffrable` n'arrive jamais ici : l'acquiescement seul (*« oui »*,
*« ok »*) est reconnu par la liaison, sans aucun appel. Ce répondeur ne voit que le micro ouvert
et le fragment.

## Les quatre réponses qui ne viennent d'aucune intention

`repondre_acquiescement`, `repondre_sans_lecture`, `repondre_panne` et
`repondre_reference_introuvable` ne correspondent à aucun code du vocabulaire : elles disent
l'état d'Urim ou celui du corpus, pas ce que le pasteur veut. Elles existent parce que **les
taire reviendrait à mentir** — un modèle en panne rend exactement ce que rend un modèle qui n'a
rien à dire, et servir *« je n'ai rien reçu qui concerne la préparation »* sur un 429 ferait
porter au pasteur une panne de réseau.

La dernière est d'une autre espèce : elle ne dit pas ce qu'Urim est, elle **transporte le
verdict du corpus**. *« Hébreux 2 compte 18 versets »* n'est pas une phrase du produit, c'est
une phrase du texte — et à ce titre elle traverse intacte, comme le motif d'un étage.
"""

from __future__ import annotations

from collections.abc import Callable

from app.contexts.urim.engine.normalizer import tokens

#: ⚠️ **Le pasteur est l'usager attendu, donc la forme pastorale est le défaut.**
#:
#: `hors_champ` recouvre deux situations très différentes : un pasteur qui demande conseil sur
#: une personne de son assemblée, et quelqu'un qui prend Urim pour un interlocuteur. La première
#: mérite de la chaleur, la seconde une limite nette.
#:
#: On ne bascule sur la seconde que si un marqueur explicite l'adresse à Urim comme à une
#: personne. Dans le doute, c'est un pasteur qui parle de son assemblée — et se tromper dans ce
#: sens-là coûte infiniment moins cher.
#: Ce qu'on ne demande qu'à une personne. **Ils se suffisent** : l'impératif s'adresse sans
#: avoir besoin d'un pronom — « prie pour moi » n'en contient aucun qui désigne Urim.
_ACTES_DE_PERSONNE = frozenset({
    "prie", "priez", "pries", "benis", "benissez", "beni", "intercede", "intercedez",
})

#: L'état intérieur. Celui-ci **exige un pronom d'adresse**, sans quoi « je crois que ce texte
#: parle du pardon » basculerait — or c'est une préparation ordinaire.
_ETATS_INTERIEURS = frozenset({
    "penses", "pense", "crois", "ressens", "sens", "aimes", "es", "etes", "existes",
})

_PRONOMS_DE_LA_PERSONNE = frozenset({"tu", "toi", "te"})


def _adresse_personnelle(saisie: str) -> bool:
    """Il ne demande pas conseil : il s'adresse à Urim comme à quelqu'un.

    🔴 Deux formes, et exiger un pronom pour les deux était faux. *« Prie pour moi »* est un
    impératif : il s'adresse à Urim sans le nommer, et le seul pronom présent — « moi » —
    désigne celui qui parle, pas celui à qui l'on parle.

    Un état intérieur, lui, a besoin du pronom : *« je crois que ce texte parle du pardon »*
    est une préparation ordinaire, *« tu crois en Dieu ? »* ne l'est pas.

    ⚠️ « vous » n'est pas dans les pronoms d'adresse : *« vous pouvez m'ouvrir Romains 12 »*
    s'adresse aussi à Urim, et c'est une demande parfaitement ordinaire."""
    mots = set(tokens(saisie))
    if mots & _ACTES_DE_PERSONNE:
        return True
    return bool(mots & _PRONOMS_DE_LA_PERSONNE) and bool(mots & _ETATS_INTERIEURS)


def situer(ancre: str | None) -> str:
    """Où en est la préparation, dit en une incise — ou rien si elle n'a pas commencé.

    ⚠️ **Publique, et utilisée hors d'ici.** Le tour s'en sert aux deux endroits où il n'a
    rien à proposer (`interface/turn.py`) : un pasteur devant un écran qui ne lui offre rien
    a le même besoin que celui dont la phrase n'a pas abouti — savoir où en est son travail.
    Deux formulations de la même incise auraient dérivé au premier correctif."""
    return f" Nous en sommes à {ancre}." if ancre else ""


#: Trois intentions sur cinq ne peuvent rien recevoir tant qu'aucun texte n'est ouvert, et la
#: bonne réponse est alors la même pour les trois. Documenté dans `_SYSTEME_AIGUILLAGE` :
#: *« Quel plan je peux tenir ? » posé avant qu'un texte soit résolu part quand même en
#: `interroger_travail`, et le répondeur dit la vérité — il faut d'abord un texte.*
_SANS_TEXTE = (
    "Aucun texte n'est encore ouvert dans cette préparation. Donnez-moi un passage, ou le "
    "sujet que vous voulez prêcher, et je pourrai répondre."
)


# ============================================================ les deux qui ne préparent rien


def repondre_hors_champ(saisie: str, ancre: str | None = None) -> str:
    """Il parle bien à Urim, on comprend, et l'atelier ne sait pas répondre.

    La réponse dit ce qu'Urim fait, puis **tend la passerelle** : un conseil sur une personne
    n'est pas de son ressort, mais un texte pour cette situation l'est. Sans cette seconde
    phrase, le tour serait une porte fermée — et le pasteur qui demandait comment annoncer un
    décès n'a rien fait de mal."""
    if _adresse_personnelle(saisie):
        return (
            "Je ne suis pas quelqu'un — je suis l'atelier où vous préparez vos prédications, "
            "à partir de l'Écriture." + situer(ancre)
        )
    return (
        "Je ne sais pas conseiller sur les personnes ni sur la conduite d'une assemblée. "
        "Ce que je sais faire, c'est ouvrir un texte avec vous : si un passage vous vient "
        "pour cette situation, donnez-le-moi." + situer(ancre)
    )


def repondre_indechiffrable(saisie: str, ancre: str | None = None) -> str:
    """Le message ne s'adresse pas à la préparation — micro ouvert, ou phrase interrompue.

    ⚠️ **On ne dit pas « je n'ai pas compris ».** Une parole captée par un micro resté ouvert a
    été parfaitement comprise ; elle ne nous était pas destinée. Faire porter l'échec à celui
    qui parlait de sa voiture serait lui reprocher un accident d'appareil."""
    return (
        "Je n'ai rien reçu qui concerne la préparation." + situer(ancre)
        + " Reprenez quand vous voulez."
    )


# ================================================ les cinq qui retombent sur ce qui existe


def repondre_preciser(saisie: str, ancre: str | None = None) -> str:
    """Il corrige la façon dont on l'a lu — et **rien n'est irréversible**, c'est tout le propos.

    Le seul service utile ici est de le dire : les options restent offertes, et celle qu'il
    écarte reste dans la liste, reléguée. Promettre autre chose — « reformulez et je reprends »
    — serait promettre une route qui abandonne la préparation au lieu de la corriger."""
    return (
        "Rien n'est figé dans cette préparation : ce qui vous est proposé reste offert, et "
        "vous pouvez écarter ce qui ne convient pas — une option écartée reste dans la liste, "
        "vous pourrez y revenir." + situer(ancre)
    )


def repondre_interroger_texte(saisie: str, ancre: str | None = None) -> str:
    """Une question sur le texte, ou sur ce qui l'entoure.

    ⚠️ **La réponse nomme les sources, elle ne répond pas à leur place.** « Les esclaves
    hébreux ne portaient pas de chaussures » est un fait historique que le corpus ne porte pas :
    une note qui l'affirmerait ne pourrait être vérifiée par personne dans l'assemblée. La
    concordance, elle, montre le texte — et c'est ce qu'on offre."""
    if not ancre:
        return _SANS_TEXTE
    return (
        "Ce que je sais de ce texte vient du corpus et de rien d'autre : le motif de l'unité, "
        "les notes de contexte, les variantes des manuscrits, et la concordance sur un mot de "
        "l'original. Ce que la curation n'a pas relu, je ne l'invente pas." + situer(ancre)
    )


def repondre_interroger_travail(saisie: str, ancre: str | None = None) -> str:
    """Une question sur sa propre préparation — et tout ce qu'on peut en dire est déjà rendu.

    Les couples plan x matière, les pesées et les textes qui résistent ailleurs voyagent dans
    la vue à chaque tour. Le répondeur ne les recalcule pas : il dit qu'ils sont là."""
    if not ancre:
        return _SANS_TEXTE
    return (
        "Ce que je peux dire de votre travail est déjà sous vos yeux : les plans que ce texte "
        "peut tenir et ceux qu'il refuse, ce qu'il porte, et les textes qui lui résistent "
        "ailleurs." + situer(ancre)
    )


def repondre_demander_production(saisie: str, ancre: str | None = None) -> str:
    """Il demande qu'on lui fabrique quelque chose — et **la moitié est verrouillée**.

    Le thème existe ; les diapositives et la fiche de chaire n'ont aucune route tant qu'une
    citation projetée n'est pas contrôlée (trou 3). Le dire au moment où il le demande vaut
    mieux qu'un bouton grisé et muet — *un bouton grisé muet est un mensonge poli*."""
    if not ancre:
        return _SANS_TEXTE
    return (
        "Je propose un thème pour ce texte, jamais un titre — le titre, c'est votre voix. Les "
        "diapositives et la fiche de chaire ne sont pas ouvertes : une citation projetée doit "
        "d'abord être contrôlée." + situer(ancre)
    )


def repondre_changer_de_sujet(saisie: str, ancre: str | None = None) -> str:
    """Il abandonne le texte en cours pour un autre sujet.

    ⚠️ **On propose, on n'exécute pas.** *Une intention ne déclenche jamais un acte
    irréversible* — un aiguilleur probabiliste qui fermerait une préparation sur un faux
    positif détruirait le travail d'un samedi soir. La préparation reste entière."""
    return (
        "Un autre sujet est une autre préparation : ouvrez-en une neuve, celle-ci vous "
        "attendra entière." + situer(ancre)
    )


#: Les sept codes de l'aiguilleur → leur répondeur. **Fermé**, comme le vocabulaire lui-même :
#: un code inconnu ne trouve personne ici, et `repondre` retombe alors sur `indechiffrable`.
#:
#: ⚠️ La table est tenue par un test qui la compare à `INTENTIONS_CONNUES`. Les deux listes
#: vivent dans deux couches — le vocabulaire chez l'adaptateur, la voix dans le moteur — et
#: rien d'autre ne les empêcherait de diverger en silence.
_REPONDEURS: dict[str, Callable[[str, str | None], str]] = {
    "preciser": repondre_preciser,
    "interroger_texte": repondre_interroger_texte,
    "interroger_travail": repondre_interroger_travail,
    "demander_production": repondre_demander_production,
    "changer_de_sujet": repondre_changer_de_sujet,
    "hors_champ": repondre_hors_champ,
    "indechiffrable": repondre_indechiffrable,
}


def repondre(intention: str | None, saisie: str, ancre: str | None = None) -> str:
    """L'intention aiguillée → la phrase qui lui répond.

    `None` arrive quand le modèle a rendu un code hors vocabulaire, ou rien du tout. C'est un
    tour qu'on ne sait pas lire, et le dire est plus honnête que de deviner — mais **seulement
    si le modèle a pu répondre**. L'appelant sépare la panne avant d'arriver ici."""
    return _REPONDEURS.get(intention or "", repondre_indechiffrable)(saisie, ancre)


# ============================================ ce qui ne vient d'aucune intention


def repondre_acquiescement(saisie: str, ancre: str | None = None) -> str:
    """« Oui » quand une question est posée — reconnu par la liaison, **sans aucun appel**.

    ⚠️ Il ne désigne rien, et la liaison ne devine jamais : deux options peuvent convenir, et
    agir sur la mauvaise coûte plus cher que de redemander. On redemande donc, en une ligne."""
    return (
        "Je ne sais pas encore à quoi votre accord se rapporte : nommez l'option, ou son "
        "rang, et la préparation continue." + situer(ancre)
    )


def repondre_sans_lecture(saisie: str, ancre: str | None = None) -> str:
    """Aucun modèle branché — pas de clé, ou le quota d'assistance épuisé.

    Ce n'est **pas** une panne : c'est un état de production (S12, S37). Urim entier continue —
    le corpus, les pesées, la concordance, le contrôle de référence — et seule la lecture d'une
    phrase libre manque. On le dit, et on nomme ce qui reste possible."""
    return (
        "Je ne sais pas lire une phrase libre en ce moment. Désignez ce que vous voulez dans "
        "cette préparation — une des options, ou une référence — et je continue." + situer(ancre)
    )


def repondre_reference_introuvable(motif: str, ancre: str | None = None) -> str:
    """La référence est lisible, et le corpus la refuse — **avec ses mots à lui**.

    🔴 `Hb 2v29` et `Ph 28v9` sont dans les notes du Pasteur X : Hébreux 2 compte 18 versets,
    Philippiens en a quatre chapitres. Urim savait le dire depuis le premier jour et ne l'avait
    jamais dit — la saisie repartait à l'aiguilleur, qui répondait à côté sans rien dire de
    l'erreur de référence.

    ⚠️ **Le motif traverse intact.** C'est le même partage que le filet doré du tour : ce qui
    vient du corpus n'est pas réécrit. *« Hébreux 2 compte 18 versets »* lui apprend quelque
    chose ; *« référence invalide »* le laisse chercher — et c'est S19, un refus nomme ce qui
    manque au corpus, jamais ce qui manque au pasteur.

    Le premier argument est donc le motif, et non la saisie : il n'y a rien à relire dans ce
    que le pasteur a écrit, le corpus a déjà répondu."""
    return (
        f"{motif} Donnez-moi une autre référence, ou le sujet que vous voulez prêcher — "
        "votre préparation ne bouge pas." + situer(ancre)
    )


def repondre_panne(saisie: str, ancre: str | None = None) -> str:
    """🔴 **Une panne n'est pas une réponse.**

    Un 429 rend exactement ce que rend un modèle qui n'a rien à dire. Servir alors *« je n'ai
    rien reçu qui concerne la préparation »* ferait porter au pasteur une panne de réseau — et
    ce serait la seule fois où Urim reprocherait quelque chose à quelqu'un qui n'a rien fait.

    La panne est de notre côté, donc on la nomme : c'est la même règle qu'ailleurs, appliquée
    dans l'autre sens."""
    return (
        "Je n'ai pas pu vous lire à l'instant, et c'est de mon côté. Reprenez dans un "
        "moment : rien de votre préparation n'est perdu." + situer(ancre)
    )
