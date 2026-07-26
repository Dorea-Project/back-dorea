"""M9-1 — le générateur de carte IA : l'IA retrouve la référence, la Bible donne le texte exact.

Le garde-fou central est testé explicitement (`test_card_text_comes_from_scripture_not_resolver`) :
même si le résolveur « connaissait » un texte, la carte n'utilise QUE le texte canonique.
"""

import json

import pytest

from app.contexts.mission.application.commands.generate_card import GenerateVerseCard
from app.contexts.mission.application.ports import ScriptureSource, VerseResolver
from app.contexts.mission.domain.errors import (
    VerseNotFoundError,
    VerseTextUnavailableError,
)
from app.contexts.mission.domain.scripture import VerseReference, normalize_book
from app.contexts.mission.infrastructure.card_renderer import (
    SvgCardRenderer,
    render_verse_card,
)
from app.contexts.mission.infrastructure.scripture_lsg import (
    JsonFileScriptureSource,
    StaticScriptureSource,
    build_scripture_source,
)
from app.contexts.mission.infrastructure.verse_resolver import (
    KeywordVerseResolver,
    build_verse_resolver,
)
from app.core.config import Settings

_JEAN_316 = VerseReference(book="Jean", chapter=3, verse=16)


# --- fakes ---


class _FakeMedia:
    def __init__(self):
        self.put_calls = []

    async def put(self, content, *, content_type):
        self.put_calls.append((content, content_type))
        return f"https://cdn.test/card-{len(content)}.svg"


class _FakeResolver(VerseResolver):
    def __init__(self, ref):
        self._ref = ref

    async def resolve(self, query):
        return self._ref


class _FakeScripture(ScriptureSource):
    def __init__(self, mapping):
        self._m = mapping

    async def text_of(self, ref):
        return self._m.get(ref.key)

    def all_references(self):
        return [VerseReference(*k) for k in []]  # non utilisé ici


# --- la référence normalisée (l'os du garde-fou) ---


def test_normalize_book_is_accent_and_case_insensitive():
    assert normalize_book("Ésaïe") == normalize_book("esaie") == "esaie"
    assert normalize_book("1 Corinthiens") == "1corinthiens"


def test_verse_reference_label_and_key():
    assert _JEAN_316.label == "Jean 3.16"
    assert _JEAN_316.key == ("jean", 3, 16)


# --- la Bible canonique embarquée ---


async def test_static_scripture_returns_exact_lsg_text():
    src = StaticScriptureSource()
    text = await src.text_of(_JEAN_316)
    assert text is not None and "Dieu a tant aimé le monde" in text
    # Insensible à l'accent/casse du livre renvoyé par l'IA.
    assert await src.text_of(VerseReference("jean", 3, 16)) == text


async def test_static_scripture_unknown_reference_is_none():
    assert await StaticScriptureSource().text_of(VerseReference("Habacuc", 2, 4)) is None


async def test_json_file_scripture_loads_dataset(tmp_path):
    path = tmp_path / "lsg.json"
    path.write_text(
        json.dumps({"Jean 3.16": "texte custom", "1 Corinthiens 13:4": "la charité..."}),
        encoding="utf-8",
    )
    src = JsonFileScriptureSource(str(path))
    assert await src.text_of(_JEAN_316) == "texte custom"
    assert await src.text_of(VerseReference("1 Corinthiens", 13, 4)) == "la charité..."


def test_build_scripture_source_falls_back_to_static():
    source = build_scripture_source(Settings(lsg_dataset_path=None))
    assert isinstance(source, StaticScriptureSource)


# --- le résolveur de repli (sans IA) ---


async def test_keyword_resolver_finds_verse_from_fuzzy_query():
    resolver = KeywordVerseResolver(StaticScriptureSource())
    query = "le verset ou Dieu a tellement aime le monde qu'il a donne son fils"
    ref = await resolver.resolve(query)
    assert ref is not None and ref.key == ("jean", 3, 16)


async def test_keyword_resolver_matches_on_reference_tokens():
    resolver = KeywordVerseResolver(StaticScriptureSource())
    ref = await resolver.resolve("psaumes 23 verset 1")
    assert ref is not None and ref.key == ("psaumes", 23, 1)


async def test_keyword_resolver_returns_none_on_gibberish():
    assert await KeywordVerseResolver(StaticScriptureSource()).resolve("xyzzy qwerty zzz") is None


def test_build_verse_resolver_without_key_is_keyword_fallback():
    resolver = build_verse_resolver(Settings(mistral_api_key=None), StaticScriptureSource())
    assert isinstance(resolver, KeywordVerseResolver)


# --- la carte designée (rendu SVG) ---


def test_render_card_contains_verse_and_reference():
    svg = render_verse_card("Jean 3.16", "Car Dieu a tant aimé le monde")
    assert svg.startswith("<svg") and svg.endswith("</svg>")
    assert "Jean 3.16" in svg
    assert "Dieu a tant" in svg  # le verset est bien dessiné


def test_render_card_escapes_xml():
    svg = render_verse_card("Test 1.1", 'Il dit <fort> & "vrai"')
    assert "&lt;fort&gt;" in svg and "&amp;" in svg
    assert "<fort>" not in svg


def test_svg_renderer_returns_bytes_and_content_type():
    body, content_type = SvgCardRenderer().render(reference_label="Jean 3.16", verse_text="x")
    assert isinstance(body, bytes) and content_type == "image/svg+xml"


# --- le use case de bout en bout ---


async def test_generate_card_end_to_end():
    media = _FakeMedia()
    cmd = GenerateVerseCard(
        _FakeResolver(_JEAN_316),
        _FakeScripture({_JEAN_316.key: "Car Dieu a tant aimé le monde..."}),
        SvgCardRenderer(),
        media,
    )
    dto = await cmd.execute(query="jean 3 16")
    assert dto.reference == "Jean 3.16"
    assert dto.text == "Car Dieu a tant aimé le monde..."
    assert dto.image_url.endswith(".svg")
    # La carte a bien été rangée en tant que SVG.
    assert media.put_calls and media.put_calls[0][1] == "image/svg+xml"


async def test_card_text_comes_from_scripture_not_resolver():
    """Le garde-fou : le texte vient de la Bible canonique, JAMAIS d'ailleurs."""
    media = _FakeMedia()
    canonical = "LE TEXTE CANONIQUE EXACT"
    cmd = GenerateVerseCard(
        _FakeResolver(_JEAN_316),
        _FakeScripture({_JEAN_316.key: canonical}),
        SvgCardRenderer(),
        media,
    )
    dto = await cmd.execute(query="quelque chose de flou")
    assert dto.text == canonical
    assert canonical in media.put_calls[0][0].decode("utf-8")  # gravé dans la carte


async def test_generate_card_unrecognized_verse_raises():
    cmd = GenerateVerseCard(
        _FakeResolver(None), StaticScriptureSource(), SvgCardRenderer(), _FakeMedia()
    )
    with pytest.raises(VerseNotFoundError):
        await cmd.execute(query="ceci n'est pas un verset")


async def test_generate_card_reference_outside_canon_raises():
    cmd = GenerateVerseCard(
        _FakeResolver(VerseReference("Habacuc", 2, 4)),
        StaticScriptureSource(),  # ne couvre pas Habacuc
        SvgCardRenderer(),
        _FakeMedia(),
    )
    with pytest.raises(VerseTextUnavailableError):
        await cmd.execute(query="habacuc deux quatre")
