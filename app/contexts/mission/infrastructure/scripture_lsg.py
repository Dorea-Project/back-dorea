"""Sources d'Écriture canonique (Louis Segond 1910, domaine public) + factory.

`build_scripture_source(settings)` : `JsonFileScriptureSource` si `lsg_dataset_path` pointe un
fichier existant, sinon `StaticScriptureSource` (poignée de versets embarqués — extrait dev).

**Pourquoi LSG 1910** : domaine public (les traductions modernes sont sous copyright). Le texte
est la source de vérité de la carte ; il ne vient JAMAIS de la mémoire de l'IA (garde-fou M9-1).

**Le stock embarqué est un extrait dev** : en production, `lsg_dataset_path` porte le dataset LSG
complet (~31 000 versets) — même patron que l'OtpSender/S3 (bâti + câblé, s'active par config).
"""

from __future__ import annotations

import json
from pathlib import Path

from app.contexts.mission.application.ports import ScriptureSource
from app.contexts.mission.domain.scripture import VerseReference
from app.core.config import Settings

# Extrait dev — quelques versets phares (LSG 1910). Clé = (livre, chapitre, verset).
# À remplacer par le dataset complet via `lsg_dataset_path`.
_LSG_SAMPLE: dict[tuple[str, int, int], str] = {
    ("Jean", 3, 16): (
        "Car Dieu a tant aimé le monde qu'il a donné son Fils unique, afin que quiconque "
        "croit en lui ne périsse point, mais qu'il ait la vie éternelle."
    ),
    ("Jean", 14, 6): (
        "Jésus lui dit : Je suis le chemin, la vérité, et la vie. Nul ne vient au Père que "
        "par moi."
    ),
    ("Psaumes", 23, 1): "L'Éternel est mon berger : je ne manquerai de rien.",
    ("Matthieu", 11, 28): (
        "Venez à moi, vous tous qui êtes fatigués et chargés, et je vous donnerai du repos."
    ),
    ("Philippiens", 4, 13): "Je puis tout par celui qui me fortifie.",
    ("Romains", 8, 28): (
        "Nous savons, du reste, que toutes choses concourent au bien de ceux qui aiment "
        "Dieu, de ceux qui sont appelés selon son dessein."
    ),
    ("Proverbes", 3, 5): (
        "Confie-toi en l'Éternel de tout ton cœur, et ne t'appuie pas sur ta sagesse."
    ),
    ("Ésaïe", 41, 10): (
        "Ne crains rien, car je suis avec toi ; ne promène pas des regards inquiets, car je "
        "suis ton Dieu ; je te fortifie, je viens à ton secours, je te soutiens de ma droite "
        "triomphante."
    ),
}


class StaticScriptureSource(ScriptureSource):
    """Bible embarquée (extrait dev). Clés normalisées pour un rapprochement robuste."""

    def __init__(self, entries: dict[tuple[str, int, int], str] | None = None) -> None:
        source = entries if entries is not None else _LSG_SAMPLE
        # Index par clé normalisée + conserve le libellé d'affichage du livre.
        self._by_key: dict[tuple[str, int, int], str] = {}
        self._refs: list[VerseReference] = []
        for (book, chapter, verse), text in source.items():
            ref = VerseReference(book=book, chapter=chapter, verse=verse)
            self._by_key[ref.key] = text
            self._refs.append(ref)

    async def text_of(self, ref: VerseReference) -> str | None:
        return self._by_key.get(ref.key)

    def all_references(self) -> list[VerseReference]:
        return list(self._refs)


def _parse_label(label: str) -> tuple[str, int, int] | None:
    """« Jean 3.16 » ou « 1 Corinthiens 13:4 » → (livre, chapitre, verset)."""
    label = label.strip()
    if not label:
        return None
    ref_part = label.rsplit(" ", 1)
    if len(ref_part) != 2:
        return None
    book, locator = ref_part[0].strip(), ref_part[1].replace(":", ".")
    parts = locator.split(".")
    if len(parts) != 2 or not (parts[0].isdigit() and parts[1].isdigit()):
        return None
    return (book, int(parts[0]), int(parts[1]))


class JsonFileScriptureSource(StaticScriptureSource):
    """LSG depuis un fichier JSON `{ "Jean 3.16": "texte", ... }` (dataset de production)."""

    def __init__(self, path: str) -> None:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        entries: dict[tuple[str, int, int], str] = {}
        for label, text in raw.items():
            parsed = _parse_label(label)
            if parsed is not None:
                entries[parsed] = text
        super().__init__(entries)


def build_scripture_source(settings: Settings) -> ScriptureSource:
    path = settings.lsg_dataset_path
    if path and Path(path).is_file():
        return JsonFileScriptureSource(path)
    return StaticScriptureSource()


__all__ = [
    "JsonFileScriptureSource",
    "StaticScriptureSource",
    "build_scripture_source",
]
