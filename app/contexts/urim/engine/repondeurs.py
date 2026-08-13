"""Les deux répondeurs qui ne préparent rien — **`hors_champ` et `indechiffrable`**.

Cinq intentions sur sept font avancer la préparation. Ces deux-là n'avancent rien, et c'est
précisément pour cela qu'elles sont difficiles : le produit n'a rien à donner, et tout se joue
dans la façon de le dire.

## La règle, et elle vient de la porte

**On nomme ce qu'Urim est, jamais ce que l'autre a mal fait.**

C'est la règle qui a été posée pour le banc de la porte, et elle vaut à chaque tour. *« Votre
demande est hors sujet »* juge la demande. *« Je ne sais préparer qu'une prédication à partir de
l'Écriture »* dit ce qu'on est, et laisse la personne intacte.

La distinction entre les deux codes n'est pas *« ai-je compris ? »* mais *« me parle-t-il ? »* :

    hors_champ      il te parle, on comprend, et l'atelier ne sait pas repondre
    indechiffrable  le message ne t'est pas adresse, ou ne porte aucune demande

## Pourquoi ces réponses sont déterministes

Le modèle n'a **aucun canal de sortie en prose** — `axes` rend des codes, `passages` rend des
références vérifiées. Faire écrire ces deux réponses par le modèle ouvrirait ce canal par la
bande, et pour dire quoi ? Que le produit ne sait pas répondre. On l'écrit une fois, en
français, et on le relit.

## L'ancre, qui est la seule chose utile de ces deux tours

Un pasteur dont la phrase n'a pas abouti — un micro resté ouvert, une phrase interrompue — a
surtout besoin de savoir **où en est sa préparation**. La réponse la rappelle. C'est le seul
service qu'un tour perdu puisse rendre.

⚠️ Une des trois formes d'`indechiffrable` n'arrive jamais ici : l'acquiescement seul (*« oui »*,
*« ok »*) est reconnu par la liaison, sans aucun appel. Ce répondeur ne voit que le micro ouvert
et le fragment.
"""

from __future__ import annotations

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


def _situer(ancre: str | None) -> str:
    """Où en est la préparation, dit en une incise — ou rien si elle n'a pas commencé."""
    return f" Nous en sommes à {ancre}." if ancre else ""


def repondre_hors_champ(saisie: str, ancre: str | None = None) -> str:
    """Il parle bien à Urim, on comprend, et l'atelier ne sait pas répondre.

    La réponse dit ce qu'Urim fait, puis **tend la passerelle** : un conseil sur une personne
    n'est pas de son ressort, mais un texte pour cette situation l'est. Sans cette seconde
    phrase, le tour serait une porte fermée — et le pasteur qui demandait comment annoncer un
    décès n'a rien fait de mal."""
    if _adresse_personnelle(saisie):
        return (
            "Je ne suis pas quelqu'un — je suis l'atelier où vous préparez vos prédications, "
            "à partir de l'Écriture." + _situer(ancre)
        )
    return (
        "Je ne sais pas conseiller sur les personnes ni sur la conduite d'une assemblée. "
        "Ce que je sais faire, c'est ouvrir un texte avec vous : si un passage vous vient "
        "pour cette situation, donnez-le-moi." + _situer(ancre)
    )


def repondre_indechiffrable(saisie: str, ancre: str | None = None) -> str:
    """Le message ne s'adresse pas à la préparation — micro ouvert, ou phrase interrompue.

    ⚠️ **On ne dit pas « je n'ai pas compris ».** Une parole captée par un micro resté ouvert a
    été parfaitement comprise ; elle ne nous était pas destinée. Faire porter l'échec à celui
    qui parlait de sa voiture serait lui reprocher un accident d'appareil."""
    return (
        "Je n'ai rien reçu qui concerne la préparation." + _situer(ancre)
        + " Reprenez quand vous voulez."
    )
