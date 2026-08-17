"""La Bible anglaise de Dorea — **World English Bible**, domaine public.

**Pourquoi la WEB et pas la King James.** Les deux sont dans le domaine public, seule raison pour
laquelle la LSG 1910 avait été retenue côté français : les traductions modernes sont sous
copyright, dans les deux langues. Mais la carte d'invitation est le premier texte biblique que
Dorea met sous les yeux de **quelqu'un du dehors** — et l'anglais de 1611 (« thou », « verily »)
met une distance là où l'on tendait la main. La WEB est une révision moderne de l'American
Standard Version, lisible sans effort. Basculer sur la KJV reste une ligne de configuration.

**Le stock embarqué est un extrait dev**, exactement comme `scripture_lsg` : les mêmes huit
versets phares, pour que le dev et les tests tournent sans dataset. En production,
`web_dataset_path` porte le fichier complet construit par `scripts/build_web_dataset.py` —
c'est lui qui fait foi, pas cet extrait.

⚠️ **Les noms de livres sont ceux de la WEB** (« Psalms », « Song of Solomon », « Revelation »).
Ce ne sont pas des libellés d'affichage : ce sont les **clés** que l'IA doit produire pour que la
recherche de texte aboutisse. Voir `ScriptureLibrary`.
"""

from __future__ import annotations

from pathlib import Path

from app.contexts.mission.infrastructure.scripture_lsg import (
    JsonFileScriptureSource,
    StaticScriptureSource,
)
from app.core.config import Settings

# Extrait dev — les mêmes versets que l'extrait LSG, dans la WEB. Clé = (livre, chapitre, verset).
_WEB_SAMPLE: dict[tuple[str, int, int], str] = {
    ("John", 3, 16): (
        "For God so loved the world, that he gave his one and only Son, that whoever believes "
        "in him should not perish, but have eternal life."
    ),
    ("John", 14, 6): (
        "Jesus said to him, “I am the way, the truth, and the life. No one comes to the Father, "
        "except through me."
    ),
    ("Psalms", 23, 1): "Yahweh is my shepherd; I shall lack nothing.",
    ("Matthew", 11, 28): (
        "Come to me, all you who labor and are heavily burdened, and I will give you rest."
    ),
    ("Philippians", 4, 13): "I can do all things through Christ, who strengthens me.",
    ("Romans", 8, 28): (
        "We know that all things work together for good for those who love God, for those who "
        "are called according to his purpose."
    ),
    ("Proverbs", 3, 5): (
        "Trust in Yahweh with all your heart, and don’t lean on your own understanding."
    ),
    ("Isaiah", 41, 10): (
        "Don’t you be afraid, for I am with you. Don’t be dismayed, for I am your God. I will "
        "strengthen you. Yes, I will help you. Yes, I will uphold you with the right hand of my "
        "righteousness."
    ),
}


def build_web_source(settings: Settings) -> StaticScriptureSource:
    """Le dataset complet si `web_dataset_path` pointe un fichier, l'extrait dev sinon.

    Même patron que `build_scripture_source` : bâti et câblé, s'active par configuration."""
    path = settings.web_dataset_path
    if path and Path(path).is_file():
        return JsonFileScriptureSource(path)
    return StaticScriptureSource(_WEB_SAMPLE)
