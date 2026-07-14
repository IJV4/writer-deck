"""Tests for font loading and its always-safe fallback."""

from __future__ import annotations

from PIL import ImageFont

from writerdeck.display.fonts import get_font


def test_get_font_returns_usable_font():
    font = get_font("Hack", 14)
    assert font is not None
    assert font.getlength("abc") > 0


def test_get_font_unknown_family_falls_back_not_raises():
    # An unknown family must resolve to the bundled fallback, never raise.
    font = get_font("NoSuchFontFamilyXYZ", 14)
    assert font is not None


def test_get_font_never_raises_when_truetype_unavailable(monkeypatch):
    # If every TrueType load fails (minimal Pi image with no DejaVu and no
    # bundled asset), get_font must fall back to PIL's built-in bitmap font
    # rather than raise OSError — the render loop only catches DisplayError,
    # so a raise here would crash the whole app.
    def boom(*args, **kwargs):
        raise OSError("no truetype font available")

    monkeypatch.setattr(ImageFont, "truetype", boom)
    get_font.cache_clear()
    try:
        font = get_font("AnyFamily", 12)
    finally:
        get_font.cache_clear()
    assert font is not None
