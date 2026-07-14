"""Tests for the per-character glyph bitmap cache."""

from __future__ import annotations

import pytest
from PIL import Image, ImageDraw

from writerdeck.display.fonts import get_font
from writerdeck.display.glyph_cache import (
    _glyph_cache,
    clear_glyph_cache,
    draw_text_cached,
    text_width_cached,
)


@pytest.fixture(autouse=True)
def isolate_glyph_cache():
    clear_glyph_cache()
    yield
    clear_glyph_cache()


def test_text_width_cached_is_stable_and_positive():
    font = get_font("Hack", 14)
    w1 = text_width_cached("width test", font)
    w2 = text_width_cached("width test", font)
    assert w1 == w2
    assert w1 > 0


def test_clear_glyph_cache_empties_cache():
    # id(font)-keyed entries must be droppable on a font change; otherwise a
    # reused id() after LRU eviction could render stale glyphs.
    font = get_font("Hack", 14)
    text_width_cached("hello", font)
    assert len(_glyph_cache) > 0
    clear_glyph_cache()
    assert len(_glyph_cache) == 0


def test_draw_text_cached_produces_ink():
    # Regression guard for the _THRESHOLD behavior: compositing an antialiased
    # mask onto a 1-bit target must not silently drop all ink. A drawn glyph
    # should leave black pixels. This failure mode was invisible on desktop
    # until it showed up as broken text on the real e-ink panel.
    img = Image.new("1", (200, 48), 1)  # all white
    draw = ImageDraw.Draw(img)
    font = get_font("Hack", 24)
    end_x = draw_text_cached(draw, (2, 2), "Hg", font, fill=0)
    black = sum(1 for p in img.getdata() if p == 0)
    assert black > 0
    assert end_x > 2  # advanced past the start x
