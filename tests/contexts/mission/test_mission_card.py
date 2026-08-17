"""M9-1 — le générateur de carte IA : l'IA retrouve la référence, la Bible donne le texte exact.

Le garde-fou central est testé explicitement (`test_card_text_comes_from_scripture_not_resolver`) :
même si le résolveur « connaissait » un texte, la carte n'utilise QUE le texte canonique.
"""

import json

import pytest

from app._shared.domain.locale import DEFAULT_LOCALE, Locale
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
from app.contexts.mission.infrastructure.scripture_library import (
    LocaleScriptureLibrary,
    build_scripture_library,
)
from app.contexts.mission.infrastructure.scripture_lsg import (
    JsonFileScriptureSource,
    StaticScriptureSource,
    build_scripture_source,
)
from app.contexts.mission.infrastructure.scripture_web import build_web_source
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
        self.locales = []

    async def resolve(self, query, *, locale=DEFAULT_LOCALE):
        self.locales.append(locale)
        return self._ref


class _FakeScripture(ScriptureSource):
    def __init__(self, mapping):
        self._m = mapping

    async def text_of(self, ref):
        return self._m.get(ref.key)

    def all_references(self):
        return [VerseReference(*k) for k in []]  # non utilisé ici


def _library(source, *, locale=Locale.FR):
    """Une bibliothèque d'une seule Bible — le français reste servi, c'est le repli."""
    sources = {Locale.FR: source}
    sources[locale] = source
    return LocaleScriptureLibrary(sources)


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
    resolver = KeywordVerseResolver(_library(StaticScriptureSource()))
    query = "le verset ou Dieu a tellement aime le monde qu'il a donne son fils"
    ref = await resolver.resolve(query)
    assert ref is not None and ref.key == ("jean", 3, 16)


async def test_keyword_resolver_matches_on_reference_tokens():
    resolver = KeywordVerseResolver(_library(StaticScriptureSource()))
    ref = await resolver.resolve("psaumes 23 verset 1")
    assert ref is not None and ref.key == ("psaumes", 23, 1)


async def test_keyword_resolver_returns_none_on_gibberish():
    resolver = KeywordVerseResolver(_library(StaticScriptureSource()))
    assert await resolver.resolve("xyzzy qwerty zzz") is None


def test_build_verse_resolver_without_key_is_keyword_fallback():
    resolver = build_verse_resolver(
        Settings(mistral_api_key=None), _library(StaticScriptureSource())
    )
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
        _library(_FakeScripture({_JEAN_316.key: "Car Dieu a tant aimé le monde..."})),
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
        _library(_FakeScripture({_JEAN_316.key: canonical})),
        SvgCardRenderer(),
        media,
    )
    dto = await cmd.execute(query="quelque chose de flou")
    assert dto.text == canonical
    assert canonical in media.put_calls[0][0].decode("utf-8")  # gravé dans la carte


async def test_generate_card_unrecognized_verse_raises():
    cmd = GenerateVerseCard(
        _FakeResolver(None), _library(StaticScriptureSource()), SvgCardRenderer(), _FakeMedia()
    )
    with pytest.raises(VerseNotFoundError):
        await cmd.execute(query="ceci n'est pas un verset")


async def test_generate_card_reference_outside_canon_raises():
    cmd = GenerateVerseCard(
        _FakeResolver(VerseReference("Habacuc", 2, 4)),
        _library(StaticScriptureSource()),  # ne couvre pas Habacuc
        SvgCardRenderer(),
        _FakeMedia(),
    )
    with pytest.raises(VerseTextUnavailableError):
        await cmd.execute(query="habacuc deux quatre")


# --- L-4 : la Bible anglaise, et l'invariant qui la relie au prompt ------------------------


async def test_la_bible_anglaise_sert_les_memes_versets():
    src = build_web_source(Settings(web_dataset_path=None))
    text = await src.text_of(VerseReference("John", 3, 16))
    assert text is not None and "God so loved the world" in text
    # Même insensibilité accent/casse que côté français — l'IA écrit « john » aussi bien.
    assert await src.text_of(VerseReference("john", 3, 16)) == text


async def test_les_deux_bibles_ne_repondent_pas_aux_memes_cles():
    """Le fait qui justifie tout ce lot : « Jean » et « John » ne sont pas deux traductions
    d'un mot, ce sont **deux clés de recherche différentes**."""
    library = build_scripture_library(Settings(lsg_dataset_path=None, web_dataset_path=None))

    assert await library.source(Locale.EN).text_of(VerseReference("Jean", 3, 16)) is None
    assert await library.source(Locale.FR).text_of(VerseReference("John", 3, 16)) is None


async def test_la_carte_interroge_la_bible_dans_la_langue_du_prompt():
    """L'invariant du lot : une seule décision de langue, pour les deux moitiés du geste."""
    resolver = _FakeResolver(VerseReference("John", 3, 16))
    library = build_scripture_library(Settings(lsg_dataset_path=None, web_dataset_path=None))

    dto = await GenerateVerseCard(resolver, library, SvgCardRenderer(), _FakeMedia()).execute(
        query="the verse where God loved the world", locale=Locale.EN
    )

    assert resolver.locales == [Locale.EN]  # le prompt a bien été demandé en anglais
    assert "God so loved the world" in dto.text  # et c'est la Bible anglaise qui a répondu


async def test_une_langue_sans_bible_retombe_sur_le_francais_des_le_prompt():
    """Le repli est un service dégradé, pas une panne : la carte sort en français plutôt que
    de faire reconnaître « John 3:16 » puis de ne rien trouver."""
    resolver = _FakeResolver(_JEAN_316)
    library = LocaleScriptureLibrary({Locale.FR: StaticScriptureSource()})  # pas d'anglais

    dto = await GenerateVerseCard(resolver, library, SvgCardRenderer(), _FakeMedia()).execute(
        query="john three sixteen", locale=Locale.EN
    )

    # La bascule se fait **avant** le résolveur, sinon le prompt et la Bible divergeraient.
    assert resolver.locales == [Locale.FR]
    assert "Dieu a tant aimé le monde" in dto.text


def test_une_bibliotheque_sans_langue_de_repli_est_refusee():
    """Sans le français, `serving` n'aurait nulle part où retomber."""
    with pytest.raises(ValueError):
        LocaleScriptureLibrary({Locale.EN: build_web_source(Settings(web_dataset_path=None))})


async def test_le_repli_sans_ia_cherche_dans_la_bonne_bible():
    """Une requête anglaise rapprochée d'un texte français ne rencontrerait jamais rien."""
    library = build_scripture_library(Settings(lsg_dataset_path=None, web_dataset_path=None))
    resolver = KeywordVerseResolver(library)

    ref = await resolver.resolve("the verse where god so loved the world", locale=Locale.EN)

    assert ref is not None and ref.key == ("john", 3, 16)
