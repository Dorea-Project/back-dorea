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


DEFAULTS: dict[WatchParam, int] = {
    WatchParam.OPEN_CASES_CAP: 5,
    WatchParam.RELAY_DELAY_HOURS: 48,
    WatchParam.RELAY_ATTEMPTS_BEFORE_GAP: 2,
    WatchParam.COVERAGE_AGGREGATION_THRESHOLD: 3,
    WatchParam.CONCERN_ESCALATION_DAYS: 10,
    WatchParam.CONCERN_WINDOW_DAYS: 30,
    WatchParam.CONCERN_VOLUME_FLOOR: 5,
    WatchParam.CONCERN_CONTACT_RATE_FLOOR_PERCENT: 30,
}
