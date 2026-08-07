"""Les **politiques sont des données**, jamais des constantes.

Durées, seuils, plafonds, délais : tout ce qui se calibre vit ici, par église, avec une valeur
par défaut. C'est une exigence du moteur, pas une commodité — une mise à jour de calibrage ne
doit pas toucher au code, et ne peut donc rien contredire.

Deux conséquences pratiques :

- une église peut allonger son délai de relais sans qu'on livre une version ; 48 h est long dans
  une grande église, et dans une petite, deux jours de déplacement ne sont pas un oubli ;
- les valeurs de départ sont **des paris**, pas des vérités. Les nommer ici, ensemble, rend
  visible ce qu'on n'a pas encore mesuré.
"""

from __future__ import annotations

from enum import StrEnum


class WatchParam(StrEnum):
    """Le catalogue fermé des paramètres calibrables. Ajouter = ajouter une ligne ici."""

    # Plafond de cas ouverts par responsable. Un responsable noyé ne traite pas plus de cas.
    OPEN_CASES_CAP = "open_cases_cap"
    # Délai avant de faire relayer une demande de rendez-vous sans réponse (heures).
    RELAY_DELAY_HOURS = "relay_delay_hours"
    # Nombre de relais infructueux au-delà duquel ce n'est plus un problème de délai mais un
    # **défaut de dispositif** : l'église n'a personne pour recevoir.
    RELAY_ATTEMPTS_BEFORE_GAP = "relay_attempts_before_gap"
    # Personnes sans référent dans un même groupe à partir desquelles on agrège en un seul
    # signal de couverture — sinon une cellule sans responsable pulvériserait le plafond.
    COVERAGE_AGGREGATION_THRESHOLD = "coverage_aggregation_threshold"
    # Jours au bout desquels une inquiétude signalée sans aucun contact remonte au pasteur —
    # **à propos du responsable**, pas du membre.
    CONCERN_ESCALATION_DAYS = "concern_escalation_days"
    # Fenêtre d'observation du garde-fou anti-déversoir, et ses deux bornes. Le tell est le
    # ratio : en dessous de ce nombre de signalements, il n'y a rien à lire.
    CONCERN_WINDOW_DAYS = "concern_window_days"
    CONCERN_VOLUME_FLOOR = "concern_volume_floor"
    # Taux de contact **en pourcentage** — un entier, parce que tout le catalogue l'est et
    # qu'un paramètre qui change de type est un paramètre qu'on finit par mal lire.
    CONCERN_CONTACT_RATE_FLOOR_PERCENT = "concern_contact_rate_floor_percent"
    # **Le garde anti-orage.** Si le cron ne tourne pas pendant trois jours, toutes les échéances
    # dues partent d'un coup : le responsable ouvre l'application sur cinquante lignes et
    # n'ouvre plus rien du tout. On en tire un nombre borné par passe, les plus anciennes
    # d'abord ; le reste **reste dû** et sortira à la passe suivante. Rien n'est perdu, tout est
    # étalé — la panne de cron devient un retard, pas une avalanche.
    CHECK_BURST_CAP = "check_burst_cap"
    # **Le seuil de la détection d'absence**, en occurrences **tenues** du groupe — jamais en
    # jours. Trois semaines de silence dans une cellule hebdomadaire et un trimestre dans une
    # commission mensuelle ne disent pas la même chose ; compter les rencontres réellement tenues
    # est la seule mesure qui veuille dire quelque chose dans les deux cas. Et une semaine sans
    # rencontre ne compte pour personne : il n'y a pas d'occurrence à manquer.
    ABSENCE_OCCURRENCES_THRESHOLD = "absence_occurrences_threshold"
    # La marge après la rencontre attendue avant de regarder. Sans elle, l'échéance tombe pendant
    # que le responsable est encore en train de saisir sa feuille de présence.
    ABSENCE_CHECK_GRACE_DAYS = "absence_check_grace_days"
    # **Au bout de combien de jours un cas non ouvert est un cas ignoré**, et non un cas récent.
    # Une seule définition pour les deux lectures qui s'en servent — le défaut de couverture qui
    # nomme le responsable, et la mesure agrégée de la boucle froide. Deux constantes auraient
    # divergé, et l'une aurait fini par contredire l'autre sur le même écran.
    CASE_UNOPENED_AFTER_DAYS = "case_unopened_after_days"
    # Ses deux bornes, même patron que le garde anti-déversoir : un plancher de lisibilité (en
    # dessous, le ratio porte sur trop peu pour vouloir dire), et le taux au-delà duquel on
    # consigne. Le tell est le **ratio** — un responsable qui porte trente cas et en ouvre
    # vingt-huit travaille bien, et un seuil sur le volume le punirait.
    UNOPENED_VOLUME_FLOOR = "unopened_volume_floor"
    UNOPENED_RATE_FLOOR_PERCENT = "unopened_rate_floor_percent"
    # **Au bout de combien de jours on propose à quelqu'un de redonner un mot** à une personne
    # vers qui il était allé. Le compte porte sur **son geste à lui**, jamais sur le silence de
    # l'autre — c'est ce qui fait que la proposition n'apprend rien à personne.
    REACT_AFTER_DAYS = "react_after_days"
    # Combien de propositions au plus par ouverture. Douze noms d'un coup, c'est une liste de
    # tâches ; deux, c'est une invitation. Et une invitation qu'on ne peut pas honorer devient
    # une dette, ce que le produit s'interdit de fabriquer.
    REACT_SUGGESTIONS_CAP = "react_suggestions_cap"


DEFAULTS: dict[WatchParam, int] = {
    WatchParam.OPEN_CASES_CAP: 5,
    WatchParam.RELAY_DELAY_HOURS: 48,
    WatchParam.RELAY_ATTEMPTS_BEFORE_GAP: 2,
    WatchParam.COVERAGE_AGGREGATION_THRESHOLD: 3,
    WatchParam.CONCERN_ESCALATION_DAYS: 10,
    WatchParam.CONCERN_WINDOW_DAYS: 30,
    WatchParam.CONCERN_VOLUME_FLOOR: 5,
    WatchParam.CONCERN_CONTACT_RATE_FLOOR_PERCENT: 30,
    WatchParam.CHECK_BURST_CAP: 20,
    WatchParam.ABSENCE_OCCURRENCES_THRESHOLD: 3,
    WatchParam.ABSENCE_CHECK_GRACE_DAYS: 2,
    WatchParam.CASE_UNOPENED_AFTER_DAYS: 7,
    WatchParam.UNOPENED_VOLUME_FLOOR: 4,
    WatchParam.UNOPENED_RATE_FLOOR_PERCENT: 50,
    WatchParam.REACT_AFTER_DAYS: 21,  # trois semaines — le pari, comme tous les autres ici
    WatchParam.REACT_SUGGESTIONS_CAP: 2,
}
