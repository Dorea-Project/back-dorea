"""Use case **générateur de carte** (M9-1) : d'un verset flou → une carte designée.

Le cœur du garde-fou, en quatre temps :
1. **Reconnaître** — l'IA (`VerseResolver`) lit la citation floue et rend la **référence**
   (livre/chapitre/verset), *jamais* le texte.
2. **Puiser** — la Bible **canonique** (`ScriptureSource`, LSG 1910) donne le **texte exact** de
   cette référence. Zéro hallucination sur l'Écriture : le texte ne vient jamais de l'IA.
3. **Composer** — `CardRenderer` dessine la carte (fond + typo du verset + référence).
4. **Ranger** — la carte est déposée dans le stockage média ; son URL devient le média du lien.

L'IA **retrouve**, elle n'**invente** pas.
"""

from __future__ import annotations

from app.contexts.media.application.media_store import MediaStore
from app.contexts.mission.application.dtos import VerseCardDTO
from app.contexts.mission.application.ports import (
    CardRenderer,
    ScriptureSource,
    VerseResolver,
)
from app.contexts.mission.domain.errors import (
    VerseNotFoundError,
    VerseTextUnavailableError,
)


class GenerateVerseCard:
    def __init__(
        self,
        resolver: VerseResolver,
        scripture: ScriptureSource,
        renderer: CardRenderer,
        media: MediaStore,
    ) -> None:
        self._resolver = resolver
        self._scripture = scripture
        self._renderer = renderer
        self._media = media

    async def execute(self, *, query: str) -> VerseCardDTO:
        ref = await self._resolver.resolve(query)
        if ref is None:
            raise VerseNotFoundError(
                "Impossible de reconnaître un verset dans cette citation.",
                details={"query": query},
            )
        text = await self._scripture.text_of(ref)
        if text is None:
            raise VerseTextUnavailableError(
                "Verset reconnu mais absent de la Bible disponible.",
                details={"reference": ref.label},
            )
        image, content_type = self._renderer.render(
            reference_label=ref.label, verse_text=text
        )
        url = await self._media.put(image, content_type=content_type)
        return VerseCardDTO(reference=ref.label, text=text, image_url=url)
