"""Rendu de la **carte designée** (M9-1) — fond nuit + typographie du verset, en SVG.

Choix figé : carte **designée** (pas d'image générée par IA). Le SVG est une simple chaîne — zéro
dépendance, entièrement testable (on peut asserter que le verset et la référence y figurent). La
taille de police s'adapte à la longueur du verset pour qu'il tienne dans le cadre.
"""

from __future__ import annotations

from app.contexts.mission.application.ports import CardRenderer

_CONTENT_TYPE = "image/svg+xml"
_SIZE = 1080
_CENTER = _SIZE // 2

# Paliers (longueur du verset) → (police, caractères par ligne). Le verset long rétrécit.
_STEPS = [
    (90, 60, 24),
    (170, 50, 28),
    (280, 42, 32),
    (10_000, 34, 38),
]


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _wrap(text: str, max_chars: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def render_verse_card(reference_label: str, verse_text: str) -> str:
    font_size, max_chars = next(
        (fs, cpl) for limit, fs, cpl in _STEPS if len(verse_text) <= limit
    )
    lines = _wrap(verse_text, max_chars)
    line_height = int(font_size * 1.4)
    block_height = line_height * len(lines)
    # Centre le bloc de texte, en laissant le tiers bas à la référence.
    start_y = _CENTER - block_height // 2 - 40 + font_size

    tspans = "".join(
        f'<tspan x="{_CENTER}" y="{start_y + i * line_height}">{_escape(line)}</tspan>'
        for i, line in enumerate(lines)
    )
    ref_y = _CENTER + block_height // 2 + 120

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_SIZE}" height="{_SIZE}" '
        f'viewBox="0 0 {_SIZE} {_SIZE}">'
        "<defs>"
        '<radialGradient id="glow" cx="50%" cy="38%" r="75%">'
        '<stop offset="0%" stop-color="#1b2c4d"/>'
        '<stop offset="100%" stop-color="#070c17"/>'
        "</radialGradient>"
        "</defs>"
        f'<rect width="{_SIZE}" height="{_SIZE}" fill="url(#glow)"/>'
        f'<text text-anchor="middle" font-family="Georgia, \'Times New Roman\', serif" '
        f'font-size="{font_size}" fill="#F2ECDD" font-style="italic">{tspans}</text>'
        f'<line x1="{_CENTER - 70}" y1="{ref_y - 48}" x2="{_CENTER + 70}" '
        f'y2="{ref_y - 48}" stroke="#C9A24B" stroke-width="2"/>'
        f'<text x="{_CENTER}" y="{ref_y}" text-anchor="middle" '
        f'font-family="Georgia, \'Times New Roman\', serif" font-size="40" '
        f'letter-spacing="3" fill="#C9A24B">{_escape(reference_label)}</text>'
        "</svg>"
    )


class SvgCardRenderer(CardRenderer):
    def render(self, *, reference_label: str, verse_text: str) -> tuple[bytes, str]:
        svg = render_verse_card(reference_label, verse_text)
        return svg.encode("utf-8"), _CONTENT_TYPE
