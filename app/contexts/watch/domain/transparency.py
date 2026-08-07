"""Ce que le membre peut lire de ce que le moteur retient de lui — **une frontière, pas une liste
d'exceptions**.

Deux promesses du produit étaient incompatibles, et le document les a longtemps posées côte à côte :

- *« le membre peut lister tout ce que le moteur sait de lui »* ;
- *« la personne n'apprend jamais qu'un tiers a parlé d'elle »*.

Ajouter une seconde exception (« sauf les notes du référent, et sauf le signalement ») aurait
transformé la transparence en liste d'exceptions — et une liste d'exceptions n'est plus une
promesse, c'est un aveu qui grandit.

La refondation, décidée le 30/07/2026 :

> **Le membre peut lister tout ce que le moteur retient de lui qui découle de ses propres actes :**
> ses présences, ses absences déclarées, ses demandes de rendez-vous, ses engagements, ses
> annonces, ses dépôts au Compagnon.
>
> **Il ne peut pas lister ce qu'un tiers a ressenti à son sujet** : cette donnée décrit
> l'engagement du tiers, pas la personne.
>
> **En contrepartie, il dispose d'un droit absolu et sans motif : `DO_NOT_CONTACT`, qui arrête
> tout — sans qu'il ait besoin de savoir ce qui existait.**

C'est la dernière clause qui tient l'éthique, et c'est pourquoi elle n'est pas facultative : le
membre n'a pas besoin de voir le dossier pour être protégé, puisqu'il a un arrêt d'urgence
inconditionnel et absorbant. Sans ce bouton, la frontière ne serait qu'une opacité de plus.

Ce n'est pas une exception à la transparence — c'est une frontière, et elle est cohérente avec ce
que le dépôt écrit déjà de son côté : le signalement par un tiers est *« un dispositif d'engagement
que le responsable se pose à lui-même »*, et son escalade remonte au pasteur **à propos du
responsable**, jamais du membre.
"""

from __future__ import annotations

from app.contexts.watch.domain.facts import CASE_ACTS, Fact, FactKind

# Ce qu'un tiers a dit ou fait **au sujet** de quelqu'un. Ces faits décrivent l'engagement de celui
# qui les a posés — pas la personne — et ne sont donc pas les siens à lire.
_ABOUT_HIM_BY_SOMEONE_ELSE: frozenset[FactKind] = frozenset(
    {
        # « Je m'en occupe cette semaine. » L'intuition d'un responsable, ou le souci d'un membre
        # pour un autre. La personne concernée n'apprendra jamais que quelqu'un a parlé d'elle —
        # c'est la condition pour que ce canal existe sans devenir une délation.
        FactKind.THIRD_PARTY_CONCERN,
        # Une qualification d'absence posée par un responsable : son jugement, pas son geste à elle.
        FactKind.QUALIFICATION_SET,
        # Le geste qu'un autre a posé. La personne sait très bien qu'on lui a rendu visite — ce
        # n'est pas un secret qu'on lui cache. Ce que ce fait décrit, c'est **l'engagement de
        # celui qui est venu**, exactement comme l'inquiétude : la règle positive dit que lui
        # appartient ce qui découle de ses propres actes, et recevoir n'est pas agir.
        FactKind.GESTURE_DONE,
        # Le compagnon collectif : un agrégat de groupe, qui n'appartient à aucun de ses membres.
        FactKind.GROUP_TEMPERATURE,
        *CASE_ACTS,  # les gestes du responsable **sur** un cas : son travail, pas la vie du membre
    }
)


def is_listable_to_subject(fact: Fact) -> bool:
    """Ce fait est-il listable par la personne qu'il concerne ?

    La règle est **positive** : ce qui découle de ses propres actes lui appartient. Tout ce qu'un
    tiers a posé à son sujet décrit ce tiers, et reste hors de sa vue.

    La fonction est ici, en domaine, plutôt que dans la route qui n'existe pas encore : le jour où
    l'écran « ce que Dorea retient de moi » sera écrit, il ne pourra pas se tromper de règle."""
    return fact.kind not in _ABOUT_HIM_BY_SOMEONE_ELSE
