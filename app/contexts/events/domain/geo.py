"""La distance entre deux points — la seule géométrie du produit.

Module **pur** : aucune I/O, aucune base. Il vit dans le domaine parce que « ces deux églises
sont-elles voisines ? » est une question métier, pas une astuce de requête.

La Terre est traitée comme une sphère. L'erreur par rapport à l'ellipsoïde réel est de l'ordre de
0,3 % — trois mètres par kilomètre. Sur un rayon de voisinage de dix kilomètres, ça déplace la
frontière de trente mètres : très en dessous de la précision avec laquelle une église pointe sa
propre adresse sur une carte.
"""

from __future__ import annotations

from math import asin, cos, radians, sin, sqrt

EARTH_RADIUS_KM = 6371.0
# Un degré de latitude vaut la même distance partout ; un degré de longitude, non.
KM_PER_DEGREE_LAT = 111.19


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance orthodromique en kilomètres (haversine)."""
    phi1, phi2 = radians(lat1), radians(lat2)
    d_phi, d_lambda = phi2 - phi1, radians(lon2 - lon1)
    a = sin(d_phi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))
