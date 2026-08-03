"""Énumérations du module Event — le happening publié (la première chose qui peut dépasser
les murs d'une église). Valeurs = source de vérité (base + surfaces), stables, extensibles.
"""

from enum import StrEnum


class EventScope(StrEnum):
    """Le cercle qu'atteint l'événement — **deux axes, pas un**.

    `CHURCH` et `NEARBY` sont gratuits : le corps local, et le quartier autour du lieu. Ils
    décrivent *où* ça se passe.

    `DENOMINATION` et `PLATFORM` demandent le compte Business **et** le mandat de l'église :
    rayonner au-delà de son voisinage est un acte institutionnel, pas un geste personnel. Ils
    décrivent *au nom de qui* on parle.

    Confondre les deux axes coûtait cher : sans `NEARBY`, atteindre les églises voisines d'une
    autre dénomination exigeait `PLATFORM`, c'est-à-dire toute la plateforme."""

    CHURCH = "church"  # les membres de mon église (gratuit)
    # **Le voisinage** — les églises dans un rayon autour du lieu, quelle que soit leur
    # dénomination. Les trois autres portées sont *institutionnelles* (mon église, mon corps, la
    # plateforme) ; celle-ci est *géographique*, et elle manquait.
    #
    # Sans elle, un repas de quartier à Yopougon n'avait qu'une issue : `PLATFORM`, qui touche
    # 11 000 personnes pour en viser 662 — dix-sept fois trop large. Le pasteur avait raison de
    # refuser le mandat, et le geste légitime devenait impossible.
    #
    # Gratuite, comme `CHURCH` : c'est le corps local élargi, pas du rayonnement institutionnel.
    NEARBY = "nearby"
    DENOMINATION = "denomination"  # toutes les églises de ma dénomination (Business, à venir)
    PLATFORM = "platform"  # toute la plateforme Dorea (Business, à venir)


class EventCategory(StrEnum):
    CONVENTION = "convention"
    VIGIL = "vigil"  # veillée
    CONCERT = "concert"
    SEMINAR = "seminar"  # séminaire
    SERVICE = "service"  # culte spécial
    OUTING = "outing"
    # **Le repas fraternel.** Le catalogue disait le formel — convention, séminaire, formation,
    # culte — et rien du convivial, alors que c'est ce qu'un membre ordinaire publie le plus
    # souvent. « Agape » est le mot de l'Église pour ça, en français comme en anglais, et il dit
    # plus précisément que « repas » : on mange ensemble parce qu'on est frères, pas au restaurant.
    AGAPE = "agape"  # sortie
    TRAINING = "training"  # formation
    OTHER = "other"


class EventReaction(StrEnum):
    """Le signal léger devant l'événement — « ça résonne » (compté, pas un score de vitrine)."""

    INTERESTED = "interested"  # ça m'intéresse
    BLESSED = "blessed"  # ça m'édifie
    PRAY = "pray"  # je prie pour


class CoverKind(StrEnum):
    """De quoi la couverture est faite. **Trois formes, et la troisième compte le plus.**

    `IMAGE` et `VIDEO` supposent qu'on a de quoi filmer ou photographier. `TEXT` ne suppose rien :
    une phrase sur un aplat de couleur, et l'événement a un visage. C'est la forme qui rend le
    produit utilisable par celui qui organise un repas depuis un téléphone à faible connexion —
    et c'est pour ça qu'elle est un membre à part entière et pas un repli silencieux.
    """

    IMAGE = "image"
    TEXT = "text"
    VIDEO = "video"


class EventStatus(StrEnum):
    PUBLISHED = "published"
    CANCELLED = "cancelled"  # retiré par l'auteur
    TAKEN_DOWN = "taken_down"  # retiré par la modération (Plateforme) — le rayonnement gouverné
