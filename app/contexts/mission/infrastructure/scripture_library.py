"""Quelle Bible répond, pour quelle langue — **et la décision est prise une seule fois**.

🔴 Le défaut que ce fichier existe pour empêcher : *un prompt anglais devant une Bible française*.
Le nom de livre que l'IA rend n'est pas un libellé, c'est la **clé** de recherche du texte
(`VerseReference.key`). Une carte demandée en anglais fait reconnaître « John 3:16 » ; interrogée
sur un index français, la Bible ne trouve rien et l'appelant lève `VerseTextUnavailableError` —
c'est-à-dire que l'anglophone perd la carte française qu'il avait avant le bilingue.

D'où la forme : `serving()` répond **une** langue, et cette langue vaut pour les deux moitiés du
geste. Elle n'est jamais devinée deux fois.

**Le repli est un service dégradé, pas une panne.** Tant que `web_dataset_path` n'est pas déployé,
la bibliothèque ne sert que l'extrait dev anglais ; et si l'on retirait la langue anglaise
entièrement, une demande `en` obtiendrait le français — une carte juste dans la mauvaise langue,
ce qui vaut mieux qu'une erreur.
"""

from __future__ import annotations

from app._shared.domain.locale import DEFAULT_LOCALE, Locale
from app.contexts.mission.application.ports import ScriptureLibrary, ScriptureSource
from app.contexts.mission.infrastructure.scripture_lsg import build_scripture_source
from app.contexts.mission.infrastructure.scripture_web import build_web_source
from app.core.config import Settings


class LocaleScriptureLibrary(ScriptureLibrary):
    def __init__(self, sources: dict[Locale, ScriptureSource]) -> None:
        if DEFAULT_LOCALE not in sources:
            # Sans la langue de repli, `serving` n'aurait nulle part où retomber et la carte
            # deviendrait impossible pour toute langue non couverte.
            raise ValueError(f"la bibliothèque doit au moins servir {DEFAULT_LOCALE}")
        self._sources = sources

    def serving(self, locale: Locale) -> Locale:
        return locale if locale in self._sources else DEFAULT_LOCALE

    def source(self, locale: Locale) -> ScriptureSource:
        return self._sources[self.serving(locale)]


def build_scripture_library(settings: Settings) -> ScriptureLibrary:
    return LocaleScriptureLibrary(
        {
            Locale.FR: build_scripture_source(settings),
            Locale.EN: build_web_source(settings),
        }
    )
