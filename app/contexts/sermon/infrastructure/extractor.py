"""Extracteurs de texte de sermon (S-5) — un fichier déposé → du **texte** pour la digestion.

Un seul port (`SermonTextExtractor`), plusieurs adaptateurs derrière un **dispatcher** par format :
- texte : décodage UTF-8 ;
- **PDF** : `pypdf` (import paresseux) ;
- **PPTX** : `python-pptx` (import paresseux) ;
- **audio** : non pris en charge ici (S-6) → erreur claire.

L'IA (S-1) ne voit jamais que le texte qui sort d'ici. Ajouter un format = ajouter un adaptateur,
sans toucher au domaine ni au pipeline.
"""

from __future__ import annotations

from io import BytesIO

from app.contexts.sermon.application.ports import SermonTextExtractor
from app.contexts.sermon.domain.enums import SermonSourceKind
from app.contexts.sermon.domain.errors import UnsupportedSermonFormatError


def _extract_text(data: bytes) -> str:
    return data.decode("utf-8", errors="replace").strip()


def _extract_pdf(data: bytes) -> str:
    from pypdf import PdfReader  # import paresseux (dépendance de S-5)

    reader = PdfReader(BytesIO(data))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(p.strip() for p in pages if p.strip()).strip()


def _extract_pptx(data: bytes) -> str:
    from pptx import Presentation  # import paresseux (dépendance de S-5)

    deck = Presentation(BytesIO(data))
    lines: list[str] = []
    for slide in deck.slides:
        for shape in slide.shapes:
            if shape.has_text_frame:
                text = shape.text_frame.text.strip()
                if text:
                    lines.append(text)
    return "\n".join(lines).strip()


class CompositeTextExtractor(SermonTextExtractor):
    """Aiguille vers l'extracteur du format ; l'audio (S-6) n'est pas encore branché."""

    async def extract(self, data: bytes, *, kind: SermonSourceKind) -> str:
        if kind is SermonSourceKind.TEXT:
            return _extract_text(data)
        if kind is SermonSourceKind.PDF:
            return _extract_pdf(data)
        if kind is SermonSourceKind.PPTX:
            return _extract_pptx(data)
        raise UnsupportedSermonFormatError(
            "Ce format de sermon n'est pas encore pris en charge.",
            details={"kind": kind.value},
        )


def build_text_extractor() -> SermonTextExtractor:
    return CompositeTextExtractor()
