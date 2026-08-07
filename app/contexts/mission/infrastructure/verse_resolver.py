"""Résolveurs de **référence** (M9-1) : reconnaître un verset à partir d'une citation floue.

- `MistralVerseResolver` — le **moteur IA** : Mistral (bon marché) lit la citation et rend
  `{found, book, chapter, verse}`. **Aucun champ texte** dans la sortie : l'IA ne fait que
  *retrouver* la référence. Import **paresseux** du SDK `mistralai` (dépendance optionnelle,
  comme `minio` pour S3).
- `KeywordVerseResolver` — **repli sans clé** : rapproche la citation des versets connus par
  recouvrement de mots. Le dev et les tests tournent sans appeler l'IA.

`build_verse_resolver(settings, scripture)` : Mistral si `mistral_api_key` est posée, sinon le
repli par mots-clés (patron OtpSender/S3 : bâti + câblé, s'active par config).
"""

from __future__ import annotations

import json
import re
import unicodedata

from app.contexts.mission.application.ports import ScriptureSource, VerseResolver
from app.contexts.mission.domain.scripture import VerseReference
from app.core.config import Settings
from app.core.logging import get_logger

_logger = get_logger("mission.verse_resolver")

_SYSTEM = (
    "Tu es un assistant biblique. On te donne une citation approximative, mal orthographiée ou "
    "mal décrite d'un verset. Identifie UNIQUEMENT sa référence (livre, chapitre, verset) dans "
    "la Bible Louis Segond. Donne le nom du livre en français (ex. Jean, Psaumes, Ésaïe, "
    "1 Corinthiens). Ne fournis JAMAIS le texte du verset : seulement la référence. "
    "Réponds par un objet JSON avec exactement les clés : found (booléen), book (chaîne), "
    "chapter (entier), verse (entier). Si tu ne peux pas identifier une référence précise avec "
    "confiance, renvoie found=false."
)


def _tokens(text: str) -> set[str]:
    """Mots comparables : minuscules, sans accent, séparés sur tout non-alphanumérique."""
    stripped = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in stripped if not unicodedata.combining(c))
    return {t for t in re.split(r"[^0-9a-z]+", stripped.lower()) if t}


def _parse_reference(content: str) -> VerseReference | None:
    """Lit la réponse du modèle **sans lui faire confiance** (DOREA-025).

    `response_format={"type": "json_object"}` promet du JSON ; il ne promet ni la forme, ni
    les types. Un `{"chapter": "trois"}`, une liste au lieu d'un objet, une clé manquante —
    et le code levait, donc **500**. Or il existe un repli (`KeywordVerseResolver`) et
    l'appelant traite déjà `None` comme « non résolu » : échouer **doucement** est à la fois
    plus sûr et plus juste. On ne rend une référence que si tout est exactement en place.
    """
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict) or not data.get("found"):
        return None
    try:
        chapter, verse = int(data["chapter"]), int(data["verse"])
        book = str(data["book"]).strip()
    except (KeyError, TypeError, ValueError):
        return None
    if chapter < 1 or verse < 1 or not book:
        return None
    return VerseReference(book=book, chapter=chapter, verse=verse)


class MistralVerseResolver(VerseResolver):
    def __init__(self, *, api_key: str, model: str) -> None:
        # Import paresseux (dépendance optionnelle). Le SDK v2 range le client sous
        # `mistralai.client` ; v1 l'expose au niveau racine — on tolère les deux.
        try:
            from mistralai import Mistral
        except ImportError:
            from mistralai.client import Mistral

        self._client = Mistral(api_key=api_key)
        self._model = model

    async def resolve(self, query: str) -> VerseReference | None:
        response = await self._client.chat.complete_async(
            model=self._model,
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": query},
            ],
            response_format={"type": "json_object"},  # sortie JSON garantie
        )
        content = response.choices[0].message.content
        if not content:
            return None
        return _parse_reference(content)


class KeywordVerseResolver(VerseResolver):
    """Repli sans IA : le meilleur recouvrement de mots avec les versets connus."""

    def __init__(self, scripture: ScriptureSource) -> None:
        self._scripture = scripture

    async def resolve(self, query: str) -> VerseReference | None:
        wanted = _tokens(query)
        if not wanted:
            return None
        best: VerseReference | None = None
        best_score = 0
        for ref in self._scripture.all_references():
            text = await self._scripture.text_of(ref)
            haystack = _tokens(ref.label) | (_tokens(text) if text else set())
            score = len(wanted & haystack)
            if score > best_score:
                best, best_score = ref, score
        return best


def build_verse_resolver(settings: Settings, scripture: ScriptureSource) -> VerseResolver:
    if settings.verse_resolver_enabled:
        _logger.info("verse_resolver_mistral", model=settings.mistral_model)
        return MistralVerseResolver(
            api_key=settings.mistral_api_key, model=settings.mistral_model
        )
    _logger.info("verse_resolver_keyword_fallback")
    return KeywordVerseResolver(scripture)
