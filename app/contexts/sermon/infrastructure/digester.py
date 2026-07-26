"""Digesteurs de sermon (S-1) — d'un texte → le digest (résumé, points, capsules, Q&R).

- `MistralSermonDigester` — le **moteur IA** : **un seul appel** Mistral (`json_object`) rend tout
  l'arbre. Import **paresseux** du SDK `mistralai` (dépendance optionnelle, comme pour Mission).
- `KeywordSermonDigester` — **repli sans clé, déterministe** : découpe le texte en pastilles et
  pose des questions de réflexion génériques. Le dev et les tests tournent sans appeler l'IA.

`build_sermon_digester(settings)` : Mistral si `mistral_api_key` est posée, sinon le repli
(patron OtpSender/S3 : bâti + câblé, s'active par config). Partage la clé Mistral de Mission.
"""

from __future__ import annotations

import json
import re

from app.contexts.sermon.application.ports import SermonDigester
from app.contexts.sermon.domain.digest import Capsule, CompanionQuestion, SermonDigest
from app.core.config import Settings
from app.core.logging import get_logger

_logger = get_logger("sermon.digester")

_SYSTEM = (
    "Tu es l'assistant d'un pasteur. On te donne le texte d'un sermon. Produis, FIDÈLEMENT au "
    "sermon et en français, un brouillon que le pasteur relira et validera. N'invente aucune "
    "doctrine, n'ajoute rien qui ne soit dans le texte. Réponds par un objet JSON avec exactement "
    "les clés : summary (chaîne, 2-3 phrases), key_points (tableau de 3 à 5 chaînes : les points "
    "essentiels, pour enseigner celui qui a manqué le culte), capsules (tableau de 2 à 4 objets "
    "{title, body} : de courtes pastilles à publier au fil), questions (tableau de 2 à 4 objets "
    "{prompt, guidance} : une question de réflexion et la réponse préparée qui aide à comprendre — "
    "console, ne juge pas)."
)


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


class MistralSermonDigester(SermonDigester):
    def __init__(self, *, api_key: str, model: str) -> None:
        # Import paresseux (dépendance optionnelle). SDK v2 : `mistralai.client` ; v1 : racine.
        try:
            from mistralai import Mistral
        except ImportError:
            from mistralai.client import Mistral

        self._client = Mistral(api_key=api_key)
        self._model = model

    async def digest(self, text: str, *, title: str, reference: str | None) -> SermonDigest:
        header = f"Titre : {title}\n"
        if reference:
            header += f"Passage : {reference}\n"
        response = await self._client.chat.complete_async(
            model=self._model,
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": header + "\nSermon :\n" + text},
            ],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        return _from_json(json.loads(content))


class KeywordSermonDigester(SermonDigester):
    """Repli sans IA : un digest **déterministe** tiré du texte lui-même."""

    async def digest(self, text: str, *, title: str, reference: str | None) -> SermonDigest:
        sentences = _sentences(text) or [text.strip()]
        summary = " ".join(sentences[:2])[:400]
        key_points = tuple(sentences[:4])
        # Pastilles : on découpe le corps en 2 morceaux à peu près égaux.
        mid = max(1, len(sentences) // 2)
        chunks = [" ".join(sentences[:mid]), " ".join(sentences[mid:])]
        capsules = tuple(
            Capsule(title=f"{title} — {i + 1}", body=c.strip())
            for i, c in enumerate(chunks)
            if c.strip()
        )
        questions = (
            CompanionQuestion(
                prompt="Qu'est-ce qui t'a le plus parlé dans ce message ?",
                guidance=summary,
            ),
        )
        return SermonDigest(
            summary=summary, key_points=key_points, capsules=capsules, questions=questions
        )


def _from_json(data: dict) -> SermonDigest:
    capsules = tuple(
        Capsule(title=str(c.get("title", "")).strip(), body=str(c.get("body", "")).strip())
        for c in data.get("capsules", [])
        if str(c.get("body", "")).strip()
    )
    questions = tuple(
        CompanionQuestion(
            prompt=str(q.get("prompt", "")).strip(), guidance=str(q.get("guidance", "")).strip()
        )
        for q in data.get("questions", [])
        if str(q.get("prompt", "")).strip()
    )
    key_points = tuple(str(p).strip() for p in data.get("key_points", []) if str(p).strip())
    return SermonDigest(
        summary=str(data.get("summary", "")).strip(),
        key_points=key_points,
        capsules=capsules,
        questions=questions,
    )


def build_sermon_digester(settings: Settings) -> SermonDigester:
    if settings.sermon_digester_enabled:
        _logger.info("sermon_digester_mistral", model=settings.mistral_model)
        return MistralSermonDigester(
            api_key=settings.mistral_api_key, model=settings.mistral_model
        )
    _logger.info("sermon_digester_keyword_fallback")
    return KeywordSermonDigester()
